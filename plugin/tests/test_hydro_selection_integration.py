"""UX-HYDRO-01: real creation/edit forms against disposable fictitious PostGIS.

Run: QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_hydro_selection_integration.py
"""

import os
import sys
import time
from pathlib import Path
from uuid import uuid4

from qgis.PyQt.QtCore import QDate, Qt
from qgis.PyQt.QtWidgets import QMainWindow
from qgis.core import (QgsApplication, QgsDataSourceUri, QgsGeometry, QgsProject,
                       QgsVectorLayer, QgsWkbTypes)
from qgis.gui import QgsMapCanvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.creation import CreationDialog  # noqa: E402
from gemapi_app.management import ManageDialog, connection_from_project  # noqa: E402
from gemapi_app.report_data import build_management_query, build_report_query, prepare_rows  # noqa: E402
from gemapi_app.report_pdf import export_detailed_report  # noqa: E402
from gemapi_app.report_synthetic_portrait import export_synthetic_portrait_report  # noqa: E402
from gemapi_app.report_maps import background, location_layers  # noqa: E402
from test_postgres_integration import ROOT, command, sql  # noqa: E402


def main():
    container = "sig-prestations-ux-hydro-" + uuid4().hex[:10]
    command("docker", "run", "--rm", "-d", "--name", container,
            "-p", "127.0.0.1::5432", "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
            "postgis/postgis:16-3.4")
    app = None
    try:
        for _ in range(60):
            if command("docker", "exec", container, "pg_isready", "-h", "127.0.0.1",
                       "-U", "postgres", check=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("PostGIS de test indisponible")
        sql(container, "CREATE EXTENSION IF NOT EXISTS postgis;")
        sql(container, (ROOT / "model/schema.sql").read_text())
        sources = sorted((ROOT / "demo/data").glob("[0-9][0-9]_*.sql"))
        sql(container, "\n".join(
            [*(source.read_text() for source in sources if source.name < "15_"),
             (ROOT / "demo/data/digues.sql").read_text(),
             *(source.read_text() for source in sources if source.name >= "15_")] ))
        river_ids = [str(uuid4()) for _ in range(4)]
        river_rows = (
            (river_ids[0], "Rivière des Trois Saules", "MULTILINESTRING((1682600 9232400,1682700 9232500))"),
            (river_ids[1], "Rivière des Trois Saules", "MULTILINESTRING((1682700 9232500,1682800 9232600))"),
            (river_ids[2], "Rivière des Trois Saules", "MULTILINESTRING((1690000 9240000,1690100 9240100))"),
            (river_ids[3], "Rivière des Prairies", "MULTILINESTRING((1684000 9233000,1684100 9233100))"),
        )
        for uid, name, geometry in river_rows:
            sql(container, "INSERT INTO milieux.cours_eau"
                           "(id,nom,type_ecoulement,direction,source,geom) VALUES "
                           f"('{uid}','{name}','rivière',FALSE,'DEMO_TEST',"
                           f"ST_GeomFromText('{geometry}',3950));")

        port = command("docker", "port", container, "5432").stdout.strip().rsplit(":", 1)[-1]
        app = QgsApplication([], True)
        app.initQgis()
        project = QgsProject.instance()

        def layer(table, geom=""):
            uri = QgsDataSourceUri()
            uri.setConnection("127.0.0.1", port, "postgres", "postgres", "")
            uri.setDataSource("milieux", table, geom, "", "id")
            if geom:
                uri.setSrid("3950")
                uri.setWkbType({"cours_eau": QgsWkbTypes.MultiLineString,
                                "ah_stockage": QgsWkbTypes.Polygon,
                                "ah_ouvrage": QgsWkbTypes.LineString}.get(table,
                                                                        QgsWkbTypes.Point))
            result = QgsVectorLayer(uri.uri(False), table, "postgres")
            assert result.isValid(), (table, result.error().summary())
            project.addMapLayer(result)
            return result

        for table in ("prestations", "types_prestations", "prestataires",
                      "ah_stockage", "ah_ouvrage", "sites_zones"):
            layer(table, "geom" if table in ("prestations", "ah_stockage", "ah_ouvrage", "sites_zones") else "")
        hydro_layer = layer("cours_eau", "geom")

        class Interface:
            def __init__(self):
                self.window = QMainWindow()
                self.canvas = QgsMapCanvas()

            def mainWindow(self):
                return self.window

            def mapCanvas(self):
                return self.canvas

        iface = Interface()
        connection = connection_from_project()
        manager = ManageDialog(connection=connection)
        manager.familyCombo.setCurrentIndex(manager.familyCombo.findData("cours_eau"))
        grouped = [manager.objectPicker.list.item(i)
                   for i in range(manager.objectPicker.list.count())
                   if "Trois Saules" in manager.objectPicker.list.item(i).text()]
        assert sorted(len(item.data(Qt.UserRole)) for item in grouped) == [1, 2]
        manager.familyCombo.setCurrentIndex(manager.familyCombo.findData("ah"))
        assert "cours_eau" not in manager.filters()
        manager.close()
        create = CreationDialog(iface)
        original = [create.objectList.item(i) for i in range(create.objectList.count())]
        triples = [item for item in original if "Trois Saules" in item.text()
                   and item.data(Qt.UserRole)[0] == "cours_eau"]
        assert len(triples) == 3 and all(len(item.data(Qt.UserRole)[1]) == 1 for item in triples)
        group = [item for item in triples if "tronçon" in item.text()]
        assert len(group) == 2
        distant = next(item for item in triples if "tronçon" not in item.text())
        group_ids = tuple(item.data(Qt.UserRole)[1][0] for item in group)
        distant_id = distant.data(Qt.UserRole)[1][0]
        canal = next(item for item in original if "Rivière des Prairies" in item.text())
        canal_id = canal.data(Qt.UserRole)[1][0]
        assert not any("sans nom" in item.text() for item in original)
        create.searchEdit.setText("  RIVIERE DES TROIS SAULES ")
        assert create.objectList.count() == 3
        create.searchEdit.setText("Riviére des Prairies")
        assert create.objectList.count() == 1
        create.searchEdit.setText(river_ids[0])
        assert create.objectList.count() == 0
        create.searchEdit.clear()
        for item in (create.objectList.item(i) for i in range(create.objectList.count())):
            if not set(item.data(Qt.UserRole)[1]).intersection(
                    set(group_ids) | {distant_id, canal_id}):
                continue
            item.setSelected(True)
        create._add_objects()
        assert create._associations() == []
        create.objectList.clearSelection()
        chosen = next(item for item in (create.objectList.item(i)
                       for i in range(create.objectList.count()))
                       if item.data(Qt.UserRole)[1][0] == group_ids[0])
        chosen.setSelected(True)
        create._add_objects()
        expected = {group_ids[0]}
        assert {uid for table, uid in create._associations() if table == "cours_eau"} == expected
        assert len(create._associations()) == 1
        create._add_objects()  # Repeated click must not duplicate a relation.
        assert len(create._associations()) == 1
        create.typeCombo.setCurrentIndex(1)
        create.prestataireCombo.setCurrentIndex(1)
        create.statutCombo.setCurrentIndex(1)
        create.technicienCombo.setCurrentIndex(1)
        create.debutDate.setDate(QDate(2027, 1, 1))
        create.finDate.setDate(QDate(2027, 1, 15))
        create.intituleEdit.setText("UX-HYDRO création fictive")
        create.geometry = QgsGeometry.fromWkt("POINT(1682600 9232400)")
        create.geometry_kind = "point"
        create._update_geometry_status()
        create._save()
        assert "enregistrées" in create.statusLabel.text(), create.statusLabel.text()
        created_id = sql(container, "SELECT id::text FROM milieux.prestations "
                         "WHERE intitule='UX-HYDRO création fictive';").stdout.strip()
        created_links = set(sql(container, "SELECT cours_eau_id::text FROM "
                                "milieux.prestations "
                                f"WHERE id='{created_id}';").stdout.split())
        assert created_links == expected
        assert connection.executeSql(build_report_query(
            {"cours_eau": [group_ids[0]]}, count_only=True))[0][0] >= 1
        assert any(str(row[0]) == created_id for row in connection.executeSql(
            build_management_query({"cours_eau": [group_ids[0]]})))

        partial_id = str(uuid4())
        type_id = sql(container, "SELECT id::text FROM milieux.types_prestations LIMIT 1").stdout.strip()
        provider_id = sql(container, "SELECT id::text FROM milieux.prestataires LIMIT 1").stdout.strip()
        status_id = sql(container, "SELECT id::text FROM milieux.statuts_prestations "
                        "WHERE code='PLANIFIE'").stdout.strip()
        technician_id = sql(container, "SELECT id::text FROM milieux.techniciens LIMIT 1").stdout.strip()
        sql(container, "BEGIN; INSERT INTO milieux.prestations"
                       "(id,intitule,type_prestation_id,prestataire_id,statut_id,technicien_id,"
                       "date_debut,date_fin,geom) VALUES "
                       f"('{partial_id}','UX-HYDRO partielle','{type_id}','{provider_id}',"
                       f"'{status_id}','{technician_id}','2027-01-01','2027-01-15',"
                       "ST_GeomFromText('POINT(1682000 9232000)',3950)); "
                       f"UPDATE milieux.prestations SET cours_eau_id='{group_ids[0]}' WHERE id='{partial_id}'; COMMIT;")

        def opened():
            dialog = CreationDialog(iface, mode="edit")
            dialog.load_existing(connection, partial_id)
            return dialog

        edit = opened()
        assert edit._associations() == [("cours_eau", group_ids[0])]
        assert any("partiel 1/2" in edit.selectedList.item(i).text()
                   for i in range(edit.selectedList.count()))
        edit._save_edit()
        assert "Aucune modification" in edit.statusLabel.text()
        assert sql(container, "SELECT count(*) FROM milieux.prestations "
                   f"WHERE id='{partial_id}';").stdout.strip() == "1"
        edit.shutdown()

        # Reopen after a fictitious new adjacent object was added to the source.
        third_id = str(uuid4())
        sql(container, "INSERT INTO milieux.cours_eau"
                       "(id,nom,type_ecoulement,direction,source,geom) VALUES "
                       f"('{third_id}','Rivière des Trois Saules','rivière',"
                       "FALSE,'DEMO_TEST',ST_GeomFromText("
                       "'MULTILINESTRING((1682800 9232600,1682900 9232700))',3950));")
        hydro_layer.reload()
        edit = opened()
        assert edit._associations() == [("cours_eau", group_ids[0])]
        assert any("partiel 1/3" in edit.selectedList.item(i).text()
                   for i in range(edit.selectedList.count()))
        edit.intituleEdit.setText("UX-HYDRO autre champ modifié")
        edit._save_edit()
        assert sql(container, "SELECT count(*) FROM milieux.prestations "
                   f"WHERE id='{partial_id}';").stdout.strip() == "1"

        edit = opened()
        edit.selectedList.selectAll()
        edit._remove_objects()
        edit.nearbyOnly.setChecked(False)
        replacement = next(edit.objectList.item(i) for i in range(edit.objectList.count())
                           if third_id in edit.objectList.item(i).data(Qt.UserRole)[1])
        replacement.setSelected(True)
        edit._add_objects()
        assert edit._associations() == [("cours_eau", third_id)]
        edit._save_edit()
        assert sql(container, "SELECT count(*) FROM milieux.prestations "
                   f"WHERE id='{partial_id}';").stdout.strip() == "1"

        edit = opened()
        edit.selectedList.selectAll()
        edit._remove_objects()
        assert edit._associations() == []
        assert not edit.saveButton.isEnabled()
        edit._save_edit()
        assert sql(container, "SELECT count(*) FROM milieux.prestations "
                   f"WHERE id='{partial_id}';").stdout.strip() == "1"
        edit.shutdown()

        # A patrimonial child can be selected and saved without drawing first.
        without_geom = CreationDialog(iface)
        assert not without_geom.nearbyOnly.isEnabled()
        assert not without_geom.nearbyOnly.isChecked()
        assert without_geom.objectList.count() > 0
        candidate = next(without_geom.objectList.item(i)
                         for i in range(without_geom.objectList.count())
                         if without_geom.objectList.item(i).data(Qt.UserRole)[0] == "ah_stockage")
        candidate.setSelected(True)
        without_geom._add_objects()
        assert len(without_geom._associations()) == 1
        assert "facultative" in without_geom.geometryStatusLabel.text()
        assert without_geom.geometryGroup.parent() is without_geom.locationGroup
        assert without_geom.associationGroup.parent() is without_geom.locationGroup
        without_geom.typeCombo.setCurrentIndex(1)
        without_geom.prestataireCombo.setCurrentIndex(1)
        without_geom.statutCombo.setCurrentIndex(1)
        without_geom.technicienCombo.setCurrentIndex(1)
        without_geom.debutDate.setDate(QDate(2027, 2, 1))
        without_geom.finDate.setDate(QDate(2027, 2, 2))
        without_geom.intituleEdit.setText("UX-HYDRO sans géométrie")
        assert without_geom.saveButton.isEnabled()
        without_geom.resize(without_geom.width(), 850)
        without_geom.show()
        app.processEvents()
        shot = ROOT / "audits/prestations_geometrie_01_formulaire.png"
        shot.parent.mkdir(exist_ok=True)
        assert without_geom.grab().save(str(shot))
        without_geom._save()
        assert "enregistrées" in without_geom.statusLabel.text(), without_geom.statusLabel.text()
        no_geom_id = sql(container, "SELECT id::text FROM milieux.prestations "
                         "WHERE intitule='UX-HYDRO sans géométrie' AND geom IS NULL;").stdout.strip()
        assert no_geom_id
        mapped = prepare_rows(connection.executeSql(build_report_query({}, include_geometry=True)))
        mapped_by_id = {row["id"]: row for row in mapped}
        without_map, with_map = mapped_by_id[no_geom_id], mapped_by_id[created_id]
        assert not without_map["has_geometry"] and without_map["own_wkt"] is None
        assert without_map["own_length"] is None and without_map["own_area"] is None
        assert without_map["reference_geometries"]
        assert location_layers(without_map)[1] is not None
        assert with_map["has_geometry"] and location_layers(with_map)[1] is not None
        pdf_root = ROOT / "audits"
        if os.environ.get("GEOMETRY_PDF_CONTROLS") == "1":
            basemap = background("epure")
            assert basemap is not None and basemap.isValid(), "Fond IGN indisponible"
            assert export_detailed_report(
                [without_map], str(pdf_root / "prestations_geometrie_01_sans_geometrie.pdf"),
                _shared_basemap=basemap) == 1
            assert export_detailed_report(
                [with_map], str(pdf_root / "prestations_geometrie_01_avec_geometrie.pdf"),
                _shared_basemap=basemap) == 1
            assert export_synthetic_portrait_report(
                [without_map, with_map], {"groups": ()},
                str(pdf_root / "prestations_geometrie_01_synthetique.pdf"),
                basemap_layer=basemap)[0] >= 1
        no_geom_edit = CreationDialog(iface, mode="edit")
        no_geom_edit.load_existing(connection, no_geom_id)
        assert no_geom_edit.geometry is None
        assert no_geom_edit.saveButton.isEnabled()
        no_geom_edit.intituleEdit.setText("UX-HYDRO sans géométrie modifiée")
        no_geom_edit._save_edit()
        assert sql(container, "SELECT count(*) FROM milieux.prestations "
                   f"WHERE id='{no_geom_id}' AND geom IS NULL "
                   "AND intitule='UX-HYDRO sans géométrie modifiée'").stdout.strip() == "1"
        no_geom_edit.selectedList.selectAll()
        no_geom_edit._remove_objects()
        river = next(no_geom_edit.objectList.item(i)
                     for i in range(no_geom_edit.objectList.count())
                     if no_geom_edit.objectList.item(i).data(Qt.UserRole)[0] == "cours_eau")
        river.setSelected(True)
        no_geom_edit._add_objects()
        assert "obligatoire" in no_geom_edit.geometryStatusLabel.text()
        assert not no_geom_edit.saveButton.isEnabled()
        no_geom_edit.shutdown()
        without_geom.shutdown()
        print("Sélection hydro : tronçons distincts, création unique et remplacement validés")
    finally:
        if app is not None:
            QgsProject.instance().clear()
            app.exitQgis()
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
