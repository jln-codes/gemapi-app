"""Run the SQL or PDF integration suite on a fresh, disposable PostGIS Demo.

See plugin/README.md for the short suites and the explicit full PDF run.
"""

import argparse
import re
import shutil
import sys
import time
import unicodedata
from collections import defaultdict
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QImage
from qgis.core import (
    QgsApplication, QgsDataSourceUri, QgsProject, QgsProviderRegistry,
    QgsVariantUtils, QgsVectorLayer,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.management import list_prestations, load_prestation
from gemapi_app.report_data import (
    build_report_query, own_totals, prepare_rows, report_warnings,
)
from gemapi_app.report_dialog import ReportDialog, _complete_pdf
from gemapi_app.report_pdf import available_photos, export_detailed_report
from gemapi_app.report_synthetic_portrait import (
    export_synthetic_portrait_report, terminal_groups,
)
from gemapi_app.session_data import SessionData
from test_postgres_integration import ROOT, command, load_demo_rows, sql


DEMO_COUNT = 100
ATTACHMENTS = (
    "cours_eau_id", "digue_id", "ah_stockage_id", "ah_ouvrage_id",
    "site_terrestre_id", "vegetation_id",
)
LONG_GROUPINGS = (
    ("cours_eau",), ("digues",), ("ah",), ("site_terrestre",), (),
    ("year", "type"), ("ah", "year", "status"), ("site_terrestre", "type", "status"),
)
MULTIPART = {
    "e0a179e2-eaaa-5417-ba45-9ef889bd21d6": "MULTIPOINT",
    "62436a03-c93c-5aa7-a134-34a888d70d27": "MULTILINESTRING",
    "e93b0ec3-7021-5f4f-adc6-1853bf64bf0a": "MULTIPOLYGON",
}


def fetched(connection, filters, *, include_geometry=False):
    raw = connection.executeSql(build_report_query(filters, include_geometry=include_geometry))
    rows = prepare_rows(raw)
    assert len(raw) == len(rows), ("UUID dupliqués dans la réponse SQL", filters)
    return rows


def check_patrimony_groups(connection, records):
    """Compare each group's members to foreign keys and qualified intersections."""
    attachments = {
        uid: tuple(None if QgsVariantUtils.isNull(value) else value for value in parents)
        for uid, *parents in connection.executeSql(
            "SELECT p.id::text,p.cours_eau_id::text,p.digue_id::text,"
            "s.ah_id::text,o.ah_id::text,COALESCE(p.site_terrestre_id,z.site_terrestre_id)::text "
            "FROM gemapi.prestations p "
            "LEFT JOIN gemapi.ah_stockage s ON s.id=p.ah_stockage_id "
            "LEFT JOIN gemapi.ah_ouvrage o ON o.id=p.ah_ouvrage_id "
            "LEFT JOIN gemapi.prestations__sites_terrestres z ON z.prestation_id=p.id")
    }
    proofs = defaultdict(lambda: defaultdict(set))
    for uid, parent, section in connection.executeSql(
        "SELECT p.id::text,s.ah_id::text,s.id::text FROM gemapi.prestations p "
        "JOIN gemapi.ah_sections_carte s ON s.cours_eau_id=p.cours_eau_id "
        "WHERE s.etat_reference='CONFORME' AND s.cours_eau_qualifie IS TRUE "
        "AND ST_Intersects(p.geom,s.geom_reference)"
    ):
        proofs[uid][parent].add(section)
    assert proofs, "La Démo doit exercer la reconnaissance AH indirecte."
    assert any(parents[2] for parents in attachments.values()), "Rattachement direct à un stockage absent."
    assert any(parents[3] for parents in attachments.values()), "Rattachement direct à un ouvrage absent."
    assert {r["id"] for r in records} == set(attachments)

    expected_groups = {group: defaultdict(set)
                       for group in ("cours_eau", "digues", "ah", "site_terrestre")}
    for record in records:
        uid = record["id"]
        river, levee, storage_ah, works_ah, site = attachments[uid]
        direct_ah = {parent for parent in (storage_ah, works_ah) if parent}
        indirect_ah = proofs.get(uid, {})
        assert record["reference_count"] == 1
        expected_parents = {(parent, True): set() for parent in direct_ah}
        expected_parents.update({(parent, False): sections for parent, sections in indirect_ah.items()})
        reported = [p for p in record["parents"] if p["kind"] == "ah"]
        assert len(reported) == len(expected_parents), (uid, reported)
        assert {(p["id"], p["direct"]): set(p["section_ids"]) for p in reported} == expected_parents
        expected_groups["cours_eau"][river].add(uid)
        expected_groups["digues"][levee].add(uid)
        expected_groups["site_terrestre"][site].add(uid)
        for parent in (direct_ah | indirect_ah.keys()) or {None}:
            expected_groups["ah"][parent].add(uid)

    for group, expected in expected_groups.items():
        terminal = terminal_groups(records, {"groups": (group,)})
        actual = {}
        for path, members in terminal:
            label = path[0][1]
            parent = None if label == "Sans rattachement" else label.rsplit(" [", 1)[1][:-1]
            assert parent not in actual, (group, parent)
            actual[parent] = {r["id"] for r in members}
            assert len(members) == path[0][2] == len(actual[parent])
        assert actual.keys() == expected.keys(), (group, actual.keys() ^ expected.keys())
        for parent in expected:
            assert actual[parent] == expected[parent], (group, parent)
        assert len(set().union(*actual.values())) == DEMO_COUNT
        print(f"Groupes {group} : {len(actual)} groupes, {DEMO_COUNT} UUID distincts", flush=True)

    for parent, expected in expected_groups["ah"].items():
        if parent is None:
            continue
        filters = {"ah": [parent]}
        rows = fetched(connection, filters)
        assert {r["id"] for r in rows} == expected, parent
        assert connection.executeSql(build_report_query(filters, count_only=True)) == [[len(expected)]]
    assert terminal_groups(records + records, {}) == [((), records)]
    print(f"AH : {sum(map(len, proofs.values()))} appartenance(s) indirecte(s), "
          f"{len(proofs)} prestation(s), sections et filtres vérifiés", flush=True)


def check_measures(connection, records):
    """Compare the report values to declared amounts and full PostGIS geometries."""
    values = {
        uid: tuple(None if QgsVariantUtils.isNull(value) else value for value in measures)
        for uid, *measures in connection.executeSql(
            "SELECT id::text,quantite::text,COALESCE(unite,''),"
            "CASE WHEN ST_Dimension(geom)=1 THEN ST_Length(geom) END,"
            "CASE WHEN ST_Dimension(geom)=2 THEN ST_Area(geom) END,"
            "CASE WHEN ST_Dimension(geom)=0 "
            "THEN ST_NumGeometries(geom) END FROM gemapi.prestations")
    }
    for row in records:
        assert tuple(row[key] for key in ("quantite", "unite", "own_length",
                                         "own_area", "own_points")) == values[row["id"]]
    for total, expected in zip(own_totals(records + records),
                               (sum(v[i] or 0 for v in values.values()) for i in (2, 3))):
        assert isclose(total, expected)
    by_id = {r["id"]: r for r in records}
    for uid, kind in MULTIPART.items():
        assert by_id[uid]["own_wkt"].startswith(kind), uid
    print(f"Mesures et quantités : {len(records)} prestations, totaux dédupliqués, "
          "trois types Multi* vérifiés", flush=True)


def check_selection_and_dialog(container, connection):
    assert not fetched(connection, {"years": [2024]})

    prestataire = sql(container, "SELECT id::text FROM gemapi.prestataires LIMIT 1").stdout.strip()
    type_prestation = sql(container, "SELECT id::text FROM gemapi.types_prestations LIMIT 1").stdout.strip()
    responsable = sql(container, "SELECT id::text FROM gemapi.techniciens LIMIT 1").stdout.strip()
    zec = sql(container, "SELECT id::text FROM gemapi.ah_stockage LIMIT 1").stdout.strip()
    fosse = sql(container, "SELECT id::text FROM gemapi.cours_eau LIMIT 1").stdout.strip()
    extended, via_only, incomplete, reference = (str(uuid4()) for _ in range(4))
    sql(container, "BEGIN; INSERT INTO gemapi.prestations "
                   "(id,intitule,type_prestation_id,prestataire_id,statut_id,technicien_id,"
                   "date_debut,date_fin,description,geom) "
                   f"VALUES ('{extended}','Élagage terminé','{type_prestation}','{prestataire}',"
                   "(SELECT id FROM gemapi.statuts_prestations WHERE code='TERMINE'),"
                   f"'{responsable}',"
                   "'2023-01-01','2025-12-31','Rivière et ZEC : été à Béthune',"
                   "ST_GeomFromText('LINESTRING(1674475 9259011,1674575 9259011)',3950)), "
                   f"('{via_only}','Via ZEC','{type_prestation}','{prestataire}',"
                   "(SELECT id FROM gemapi.statuts_prestations WHERE code='TERMINE'),"
                   f"'{responsable}',"
                   "'2024-02-01','2024-03-01','',ST_GeomFromText('POINT(1674500 9259050)',3950)), "
                   f"('{incomplete}','Non complétée','{type_prestation}','{prestataire}',"
                   "(SELECT id FROM gemapi.statuts_prestations WHERE code='PLANIFIE'),"
                   f"'{responsable}',"
                   "'2023-01-01','2025-12-31','',"
                   "ST_GeomFromText('POLYGON((1674475 9259011,1674575 9259011,1674575 9259111,1674475 9259111,1674475 9259011))',3950)), "
                   f"('{reference}','Référence patrimoniale','{type_prestation}','{prestataire}',"
                   "(SELECT id FROM gemapi.statuts_prestations WHERE code='ANNULE'),"
                   f"'{responsable}',"
                   "'2023-05-01','2023-05-31','Deux points disjoints',"
                   "ST_GeomFromText('MULTIPOINT((1674500 9259050),(1675000 9259550))',3950)); "
                   f"UPDATE gemapi.prestations SET ah_stockage_id='{zec}' WHERE id IN ('{extended}','{via_only}','{reference}'); "
                   f"UPDATE gemapi.prestations SET cours_eau_id='{fosse}' WHERE id='{incomplete}'; COMMIT;")
    all_rows = fetched(connection, {})
    assert len(all_rows) == 104
    assert len({row["id"] for row in all_rows}) == 104
    listed = list_prestations(connection)
    assert len(listed) == 104 and len({row[0] for row in listed}) == 104
    assert {extended, via_only, reference} <= {
        row[0] for row in list_prestations(connection, {"ah_stockage": [zec]})}
    assert reference not in {row[0] for row in list_prestations(
        connection, {"ah_stockage": [zec], "cours_eau": [fosse]})}
    first_row, first_links = load_prestation(connection, extended)
    second_row, second_links = load_prestation(connection, reference)
    assert first_row[0] == extended and second_row[0] == reference
    assert {(row[0], row[1]) for row in first_links} == {
        ("ah_stockage", zec)}
    assert {(row[0], row[1]) for row in second_links} == {("ah_stockage", zec)}
    by_id = {row["id"]: row for row in all_rows}
    assert round(by_id[extended]["own_length"], 1) == 100.0
    assert round(by_id[incomplete]["own_area"], 1) == 10000.0
    assert by_id[via_only]["has_geometry"] and not by_id[via_only]["own_length"]
    assert by_id[via_only]["objects"]
    assert by_id[extended]["objects"]
    assert by_id[reference]["has_geometry"] and by_id[reference]["reference_count"] == 1
    assert own_totals([by_id[reference]]) == (0, 0)
    assert not any("AMB-01" in item for item in report_warnings(all_rows, {}))
    selected = fetched(connection, {"ah_stockage": [zec]})
    assert {extended, via_only, reference} <= {row["id"] for row in selected}
    selected = fetched(connection, {"ah_stockage": [zec], "cours_eau": [fosse]})
    assert reference not in {row["id"] for row in selected}
    selected = fetched(connection, {"completion": "completed"})
    assert {extended, via_only} <= {row["id"] for row in selected}
    selected = fetched(connection, {"completion": "incomplete", "years": [2024]})
    assert not selected  # date_fin must not make the 2023 start count in 2024.
    selected = fetched(connection, {"completion": "completed", "years": [2024]})
    assert {row["id"] for row in selected} == {extended, via_only}
    selected = fetched(connection, {"years": [2024]})
    assert {row["id"] for row in selected} == {extended, via_only}
    selected = fetched(connection, {"completion": "incomplete"})
    assert len(selected) == 79 and reference in {row["id"] for row in selected}
    for criteria in ({}, {"ah_stockage": [zec]},
                     {"ah_stockage": [zec], "cours_eau": [fosse]},
                     {"completion": "completed"},
                     {"completion": "incomplete", "years": [2024]}):
        counted = connection.executeSql(build_report_query(criteria, count_only=True))
        assert counted == [[len(fetched(connection, criteria))]], (criteria, counted)

    class Interface:
        def mainWindow(self):
            return None

    session = SessionData()
    dialog = ReportDialog(Interface(), session=session)
    try:
        assert dialog.connection is not None, dialog.statusLabel.text()
        assert dialog.other_statuses == ()
        year_picker = dialog.pickers["years"]
        year_item = next(year_picker.list.item(i) for i in range(year_picker.list.count())
                         if year_picker.list.item(i).data(Qt.UserRole) == 2024)
        year_item.setCheckState(Qt.Checked)
        dialog.completionCombo.setCurrentIndex(2)
        dialog.refresh_count()
        assert dialog.match_count == 0 and not dialog.exportButton.isEnabled()
        assert "0 prestation" in dialog.summaryLabel.text()
        year_item.setCheckState(Qt.Unchecked)
        dialog.completionCombo.setCurrentIndex(0)
        dialog.refresh_count()
        assert dialog.match_count == 104
        assert dialog.exportButton.isEnabled()
        dialog.reportKindCombo.setCurrentIndex(1)
        for combo, criterion in zip(dialog.group_combos, ("type", "commune", "status")):
            combo.setCurrentIndex(combo.findData(criterion))
        assert dialog.filters()["groups"] == ("type", "commune", "status")
        assert not dialog.group2Combo.model().item(
            dialog.group2Combo.findData("type")).isEnabled()
        for combo in dialog.group_combos:
            combo.setCurrentIndex(0)
        assert set(dialog.pickers) == {"years", "technicians", "communes", "types",
                                       "statuses", "providers", "cours_eau", "digues",
                                       "ah", "site_terrestre"}
    finally:
        dialog.close()
        session.close()

    mapped = fetched(connection, {}, include_geometry=True)
    assert len(mapped) == 104
    mapped_by_id = {row["id"]: row for row in mapped}
    assert mapped_by_id[extended]["own_wkt"].startswith("LINESTRING")
    assert mapped_by_id[via_only]["own_wkt"].startswith("POINT")
    assert mapped_by_id[incomplete]["own_wkt"].startswith("POLYGON")
    assert mapped_by_id[reference]["own_wkt"].startswith("MULTIPOINT")
    assert len(mapped_by_id[reference]["reference_geometries"]) >= 1
    print("Sélection et formulaires Qt : 104 UUID distincts, mesures et filtres validés", flush=True)


def check_pdf(path, records, basemap, *, groups=None, expected_text=()):
    """Exercise the production exporter and verify every emitted page."""
    count = len(records)
    assert len({row["id"] for row in records}) == count
    print(f"PDF {path.stem} : début, {count} prestations", flush=True)
    start = time.monotonic()
    try:
        if groups is None:
            pages = export_detailed_report(
                records, path, include_photos=True, _shared_basemap=basemap)
            maps = count
            assert pages >= count
        else:
            filters = {"groups": groups}
            expected_maps = len(terminal_groups(records, filters))
            pages, maps = export_synthetic_portrait_report(
                records, filters, path, basemap_layer=basemap)
            assert pages >= maps == expected_maps
        export_duration = time.monotonic() - start
        assert _complete_pdf(path), path
        info = command("pdfinfo", str(path)).stdout
        assert int(re.search(r"^Pages:\s+(\d+)$", info, re.M)[1]) == pages, path
        extracted = command("pdftotext", "-enc", "UTF-8", "-layout", str(path), "-").stdout
        pdf_pages = [page for page in extracted.split("\f") if page.strip()]
        assert len(pdf_pages) == pages, path
        for number, page in enumerate(pdf_pages, 1):
            assert re.search(rf"\bPage\s+{number}\s*/\s*{pages}\b", page), (path, number)
        normalized = " ".join(unicodedata.normalize("NFKC", extracted).split())
        if groups is None:
            assert normalized.count("FICHE DE PRESTATION") == count, path
            assert normalized.count("LOCALISATION") == count, path
            assert "Aucune géométrie localisable" not in normalized, path
        else:
            assert f"Total général : {count} prestations" in normalized, path
        for text in expected_text:
            assert text in normalized, (path, text)
        assert not re.search(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", normalized, re.I)
    except (Exception, KeyboardInterrupt):
        print(f"PDF {path.stem} : échec à {time.monotonic() - start:.2f} s", flush=True)
        raise
    print(f"PDF {path.stem} : OK, {count} prestations, {maps} cartes, {pages} pages, "
          f"{export_duration:.2f} s d’export, {time.monotonic() - start:.2f} s avec contrôles",
          flush=True)


def six_modes(connection, records):
    by_id = {row["id"]: row for row in records}
    return [by_id[connection.executeSql(
        f"SELECT id::text FROM gemapi.prestations WHERE {field} IS NOT NULL ORDER BY id LIMIT 1"
    )[0][0]] for field in ATTACHMENTS]


def check_pdf_suite(connection, records, suite):
    output = ROOT / "audits"
    output.mkdir(exist_ok=True)
    basemap = QgsVectorLayer("Polygon?crs=EPSG:2154", "Fond de test", "memory")
    project_layers = set(QgsProject.instance().mapLayers())
    with TemporaryDirectory(prefix=f"export_lots_{suite}_", dir=output) as directory:
        out = Path(directory)
        detailed = six_modes(connection, records)
        if suite == "long":
            for groups in LONG_GROUPINGS:
                name = "_".join(groups) or "sans_groupement"
                check_pdf(out / f"synthetique_{name}.pdf", records, basemap, groups=groups)
            check_pdf(out / "detaille_six_modes.pdf", detailed, basemap)
            assert len(list(out.glob("*.pdf"))) == 9
        else:
            indirect = next(r for r in records if any(
                p["kind"] == "ah" and not p["direct"] for p in r["parents"]))
            ah = next(p["id"] for p in indirect["parents"] if p["kind"] == "ah")
            direct = next(r for r in records if any(
                p["id"] == ah and p["direct"] for p in r["parents"]))
            check_pdf(out / "synthetique_ah.pdf", [direct, indirect], basemap, groups=("ah",),
                      expected_text=("Reconnaissance indirecte",))

            groups = ("cours_eau",)
            batch = [members[0] for _, members in terminal_groups(records, {"groups": groups})][:12]
            assert len(terminal_groups(batch, {"groups": groups})) == 12
            check_pdf(out / "synthetique_douze_groupes.pdf", batch, basemap, groups=groups)

            detail_by_id = {row["id"]: dict(row) for row in detailed}
            detail_by_id.update((row["id"], dict(row)) for row in records if row["id"] in MULTIPART)
            detail_by_id[indirect["id"]] = dict(indirect)
            detailed = list(detail_by_id.values())
            first, second, third = detailed[:3]
            for number, size, color in ((1, (900, 450), "#416f91"), (2, (450, 900), "#a07545")):
                path = out / f"photo_{number}.png"
                image = QImage(*size, QImage.Format_RGB32)
                image.fill(QColor(color))
                assert image.save(str(path))
                first[f"photo_{number}"] = str(path)
                first[f"photo_{number}_commentaire"] = f"Photographie fictive {number}"
            second.update(photo_1=first["photo_1"], photo_2=str(out / "introuvable.jpg"))
            third.update(photo_1=None, photo_2=None)
            assert [len(available_photos(row)) for row in (first, second, third)] == [2, 1, 0]
            check_pdf(out / "detaille.pdf", detailed, basemap,
                      expected_text=("Photographie fictive 1", "Photographie fictive 2",
                                     "reconnaissance indirecte"))
            assert len(list(out.glob("*.pdf"))) == 3
    assert set(QgsProject.instance().mapLayers()) == project_layers


def run_suite(suite):
    container = "sig-prestations-report-" + uuid4().hex[:10]
    command("docker", "run", "--rm", "-d", "--name", container,
            "-p", "127.0.0.1::5432", "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
            "postgis/postgis:16-3.4")
    app = None
    try:
        for _ in range(60):
            if command("docker", "exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres",
                       check=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("PostGIS de test indisponible")
        sql(container, "CREATE EXTENSION IF NOT EXISTS postgis;")
        sql(container, (ROOT / "model" / "schema.sql").read_text(encoding="utf-8"))
        load_demo_rows(container)

        sql(container, "CREATE ROLE report_read LOGIN; "
                       "GRANT USAGE ON SCHEMA gemapi TO report_read; "
                       "GRANT SELECT ON ALL TABLES IN SCHEMA gemapi TO report_read;")
        mapping = command("docker", "port", container, "5432").stdout.strip()
        port = mapping.rsplit(":", 1)[-1]
        print("Port PostGIS temporaire :", mapping, flush=True)
        app = QgsApplication([], True)
        app.initQgis()
        uri = QgsDataSourceUri()
        uri.setConnection("127.0.0.1", port, "postgres", "report_read", "")
        uri.setDataSource("gemapi", "prestations_fiches", "", "", "id")
        metadata = QgsProviderRegistry.instance().providerMetadata("postgres")
        connection = metadata.createConnection(uri.connectionInfo(False), {})
        assert connection.executeSql("SELECT 1") == [[1]]
        layer = QgsVectorLayer(uri.uri(False), "prestations", "postgres")
        assert layer.isValid(), "La couche PostGIS de test n'est pas lisible : " + layer.error().summary()
        QgsProject.instance().addMapLayer(layer)
        connection = metadata.createConnection(QgsDataSourceUri(layer.source()).connectionInfo(False), {})
        records = fetched(connection, {}, include_geometry=True)
        assert len(records) == DEMO_COUNT
        if suite == "sql":
            assert connection.executeSql(build_report_query({}, count_only=True)) == [[DEMO_COUNT]]
            check_patrimony_groups(connection, records)
            check_measures(connection, records)
            check_selection_and_dialog(container, connection)
        else:
            check_pdf_suite(connection, records, suite)
    finally:
        if app:
            QgsProject.instance().removeAllMapLayers()
            app.exitQgis()
        command("docker", "stop", container, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("sql", "pdf", "long"), default="sql",
                        help="sélections SQL/Qt (défaut), PDF rapides ou recette PDF complète")
    suite = parser.parse_args().suite
    if suite != "sql" and not all(shutil.which(tool) for tool in ("pdfinfo", "pdftotext")):
        parser.error("pdfinfo et pdftotext (Poppler) sont requis pour vérifier les PDF")
    start = time.monotonic()
    run_suite(suite)
    print(f"Suite {suite} : OK en {time.monotonic() - start:.2f} s", flush=True)


if __name__ == "__main__":
    main()
