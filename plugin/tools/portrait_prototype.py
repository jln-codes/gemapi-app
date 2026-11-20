"""Render the experimental portrait report from the 12 original 2026 demo records."""

import argparse
import re
import sys
from pathlib import Path

from qgis.core import QgsApplication, QgsGeometry, QgsWkbTypes

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugin"))
from gemapi_app.report_pdf import export_detailed_report, export_synthetic_report  # noqa: E402
from gemapi_app.report_data import report_warnings  # noqa: E402


def lookup(filename, pattern):
    source = (ROOT / "demo" / "data" / filename).read_text(encoding="utf-8")
    return dict(re.findall(pattern, source))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--editor-login", default="", help="Identifiant de la connexion PostgreSQL")
    args = parser.parse_args()
    app = QgsApplication([], True)
    app.initQgis()
    types = lookup("05_types_prestations.sql",
                   r"VALUES \('([0-9a-f-]{36})', '[^']+', '([^']+)'")
    providers = lookup("04_prestataires.sql",
                       r"VALUES \('([0-9a-f-]{36})', '([^']+)'")
    # The technician SQL has three captures; keep the full name in SQL order.
    people = {identifier: f"{first} {last}" for identifier, last, first in
              re.findall(r"VALUES \('([0-9a-f-]{36})', '([^']+)', '([^']+)'",
                         (ROOT / "demo/data/01_techniciens.sql").read_text(encoding="utf-8"))}
    technician_sql = (ROOT / "demo/data/01_techniciens.sql").read_text(encoding="utf-8")
    names_by_login = {}
    for last, first, login in re.findall(
            r"VALUES \('[0-9a-f-]{36}', '([^']+)', '([^']+)', (NULL|'[^']*')",
            technician_sql):
        if login != "NULL" and login.strip("'"):
            names_by_login[login.strip("'").casefold()] = f"{first} {last}"
    editor_login = args.editor_login.strip()
    editor_name = names_by_login.get(editor_login.casefold())
    source = (ROOT / "demo/data/15_prestations.sql").read_text(encoding="utf-8")
    row_pattern = re.compile(
        r"VALUES \('([0-9a-f-]{36})','([^']*)','([0-9a-f-]{36})',"
        r"'([0-9a-f-]{36})',\(SELECT id FROM milieux.statuts_prestations "
        r"WHERE code='([^']+)'\),'([0-9a-f-]{36})','(2026-[^']+)',"
        r"'([^']+)',([0-9.]+),'([^']*)','([^']*)',"
        r"ST_GeomFromWKB\(decode\('([0-9a-f]+)','hex'\),3950\)\)"
    )
    records = []
    for match in row_pattern.finditer(source):
        (identifier, title, kind_id, provider_id, status, technician_id,
         start, end, quantity, unit, description, wkb) = match.groups()
        if not start.endswith("-01"):
            continue
        geometry = QgsGeometry()
        geometry.fromWkb(bytes.fromhex(wkb))
        geometry_kind = QgsWkbTypes.geometryType(geometry.wkbType())
        records.append({
            "id": identifier,
            "intitule": title,
            "type": types[kind_id],
            "statut": status,
            "provider": providers[provider_id],
            "technician": people[technician_id],
            "date_debut": start,
            "date_fin": end,
            "quantite": float(quantity),
            "unite": unit,
            "description": description,
            "communes": "Non renseignées dans les données source",
            "objects": "",
            "own_length": geometry.length() if geometry_kind == QgsWkbTypes.LineGeometry else None,
            "own_area": geometry.area() if geometry_kind == QgsWkbTypes.PolygonGeometry else None,
            "has_geometry": True,
            "reference_measures": None,
            "own_wkt": geometry.asWkt(),
            "reference_geometries": [],
        })
    if len(records) != 12 or len({record["id"] for record in records}) != 12:
        raise RuntimeError("Les données SQL doivent contenir 12 prestations de 2026.")
    output_dir = ROOT / "audits"
    output_dir.mkdir(exist_ok=True)
    print(f"Éditeur : {editor_name or 'identité non résolue'} (login : {editor_login})", flush=True)
    if "--synthetic" in sys.argv:
        output = output_dir / "prestations_synthetique_paysage_01.pdf"
        filters = {"groups": ("year", "type", "status")}
        pages = export_synthetic_report(
            records, filters, "Prestations de 2026",
            report_warnings(records, filters), output)
    else:
        output = output_dir / "prestations_detaille_validation.pdf"
        pages = export_detailed_report(
            records, output,
            editor_login=editor_login, editor_name=editor_name)
    print(f"{pages} pages : {output}", flush=True)


if __name__ == "__main__":
    main()
