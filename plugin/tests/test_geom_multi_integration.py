"""GEOM-MULTI-01 sur PostGIS jetable et QGIS hors écran."""

from contextlib import closing
import os
import time
from unittest.mock import patch
from uuid import uuid4

import psycopg2
from qgis.core import QgsApplication, QgsProject, QgsVectorLayer

from test_postgres_integration import ROOT, command
from gemapi_app.report_data import build_report_query, measure_lines, own_totals, prepare_rows
from gemapi_app.report_maps import location_layers
from gemapi_app.report_pdf import export_detailed_report
from gemapi_app.report_synthetic_portrait import (
    export_synthetic_portrait_report, group_layers_and_extent,
)


SITE = "MULTIPOLYGON(((0 0,200 0,200 200,0 200,0 0)),((400 0,600 0,600 200,400 200,400 0)))"
POSITIONS = (("intérieure", 20, 420, True, True),
             ("extérieure", 820, 920, False, False),
             ("partielle", 20, 920, False, True))
MEASURES = {"points": (2, None, None), "lignes": (None, 75, None),
            "surfaces": (None, None, 800)}


def parts(kind, first, second):
    if kind == "points":
        return f"MULTIPOINT(({first} 20),({second} 40))"
    if kind == "lignes":
        return f"MULTILINESTRING(({first} 20,{first + 30} 60),({second} 40,{second} 65))"
    return (f"MULTIPOLYGON((({first} 20,{first + 20} 20,{first + 20} 40,"
            f"{first} 40,{first} 20)),(({second} 40,{second + 40} 40,"
            f"{second + 40} 50,{second} 50,{second} 40)))")


def run_matrix(db):
    db.autocommit = True
    with db.cursor() as cur:
        cur.execute("CREATE SCHEMA extensions; CREATE EXTENSION postgis WITH SCHEMA extensions")
        cur.execute((ROOT / "model/schema.sql").read_text())
        cur.execute("SET search_path=pg_catalog,extensions,gemapi")
        cur.execute("INSERT INTO gemapi.techniciens(nom) VALUES ('Technicien fictif') RETURNING id")
        technician = cur.fetchone()[0]
        cur.execute("INSERT INTO gemapi.prestataires(nom) VALUES ('Entreprise fictive') RETURNING id")
        provider = cur.fetchone()[0]
        cur.execute("INSERT INTO gemapi.types_prestations(code,libelle,categorie_id) "
                    "SELECT 'GEOM-MULTI','Travaux fictifs',id FROM gemapi.prestations_categorie "
                    "WHERE ordre=1 RETURNING id")
        prestation_type = cur.fetchone()[0]
        cur.execute("SELECT id FROM gemapi.statuts_prestations WHERE code='TERMINE'")
        status = cur.fetchone()[0]
    db.autocommit = False
    with db.cursor() as cur:
        cur.execute("INSERT INTO gemapi.sites_terrestres(nom,geom) VALUES "
                    "('Site témoin',ST_Translate(ST_GeomFromText(%s,3950),1700000,9300000)) RETURNING id",
                    (SITE,))
        site = cur.fetchone()[0]
        cases = {}
        for kind in MEASURES:
            for position, first, second, covered, intersects in POSITIONS:
                title = f"Site {kind} {position}"
                wkt = parts(kind, first, second)
                cur.execute("INSERT INTO gemapi.prestations(intitule,type_prestation_id,prestataire_id,"
                            "technicien_id,statut_id,date_debut,date_fin,quantite,unite,site_terrestre_id,geom) "
                            "VALUES (%s,%s,%s,%s,%s,'2026-01-01','2026-01-02',7,'unités',%s,"
                            "ST_Translate(ST_GeomFromText(%s,3950),1700000,9300000)) RETURNING id",
                            (title, prestation_type, provider, technician, status, site, wkt))
                uid = cur.fetchone()[0]
                cur.execute("SELECT ST_Covers(s.geom,p.geom),ST_Intersects(s.geom,p.geom),"
                            "ST_NumGeometries(p.geom),ST_AsText(p.geom),"
                            "ST_AsEWKB(p.geom)=ST_AsEWKB(c.geom) "
                            "FROM gemapi.prestations p JOIN gemapi.sites_terrestres s ON s.id=p.site_terrestre_id "
                            "JOIN gemapi.prestations_carte c ON c.id=p.id WHERE p.id=%s", (uid,))
                actual_covered, actual_intersects, count, original, map_exact = cur.fetchone()
                assert (actual_covered, actual_intersects, count, map_exact) == (covered, intersects, 2, True)
                cases[uid] = (original, MEASURES[kind])

        for kind in MEASURES:
            cur.execute("INSERT INTO gemapi.vegetation(famille_vegetation,site_terrestre_id,designation,geometry) "
                        "VALUES ('ARBRES',%s,%s,ST_Translate(ST_GeomFromText(%s,3950),1700000,9300000)) "
                        "RETURNING id,ST_AsText(geometry)", (site, f"Zone {kind}", parts(kind, 20, 420)))
            zone, shape = cur.fetchone()
            cur.execute("INSERT INTO gemapi.prestations(intitule,type_prestation_id,prestataire_id,"
                        "technicien_id,statut_id,date_debut,date_fin,quantite,unite,vegetation_id) "
                        "VALUES (%s,%s,%s,%s,%s,'2026-01-01','2026-01-02',7,'unités',%s) RETURNING id",
                        (f"Zone {kind}", prestation_type, provider, technician, status, zone))
            uid = cur.fetchone()[0]
            cur.execute("SELECT p.geom IS NULL, ST_AsText(c.geom),f.longueur_m,f.surface_m2,f.surface_ha "
                        "FROM gemapi.prestations p JOIN gemapi.prestations_carte c USING(id) "
                        "JOIN gemapi.prestations_fiches f USING(id) WHERE p.id=%s", (uid,))
            _, length, area = MEASURES[kind]
            assert cur.fetchone() == (True, shape, length, area,
                                      area / 10000 if area is not None else None)
            cases[uid] = (shape, (None, None, None))

        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cur.execute(build_report_query({"site_terrestre": [site]}, include_geometry=True))
        records = prepare_rows(cur.fetchall())
        assert len(records) == len(cases) == 12
        assert {r["id"] for r in records} == set(cases)
        assert own_totals(records + records) == (225, 2400)
        for record in records:
            expected_shape, expected_measures = cases[record["id"]]
            assert tuple(record[k] for k in ("own_points", "own_length", "own_area")) == expected_measures
            assert (record["quantite"], record["unite"]) == ("7", "unités")
            layers, extent, _ = location_layers(record)
            assert extent is not None
            if record["has_geometry"]:
                assert record["own_wkt"] == expected_shape and len(layers) == 2
            else:
                assert record["own_wkt"] is None and len(layers) == 1
                assert record["reference_geometries"][0]["wkt"] == expected_shape
                assert record["reference_measures"] is None
                label = {
                    'MULTIPOINT': 'Géométrie ponctuelle du patrimoine',
                    'MULTILINESTRING': 'Longueur du patrimoine (géométrie parente) : 75,0 m',
                    'MULTIPOLYGON': 'Surface du patrimoine (géométrie parente) : 800,0 m²',
                }[expected_shape.partition('(')[0]]
                assert measure_lines(record) == [label, 'Quantité déclarée : 7 unités']
            for layer in layers:
                feature = next(layer.getFeatures())
                assert len(feature.geometry().asGeometryCollection()) == 2
                assert extent.contains(feature.geometry().boundingBox())
        layers, extent = group_layers_and_extent(records)
        assert sum(layer.featureCount() for layer in layers if layer.name() == "Prestations du groupe") == 9
        assert all(extent.contains(f.geometry().boundingBox()) for layer in layers for f in layer.getFeatures())

        negatives = (
            ("POINT(0 0)", 3950), ("LINESTRING(0 0,1 1)", 3950),
            ("POLYGON((0 0,1 0,1 1,0 0))", 3950),
            ("MULTIPOINT EMPTY", 3950), ("MULTIPOINT Z ((0 0 1))", 3950),
            ("MULTIPOINT((0 0))", 2154),
            ("MULTIPOLYGON(((0 0,1 1,1 0,0 1,0 0)))", 3950),
        )
        for table, id_filter in (("prestations", "site_terrestre_id"),
                                 ("sites_terrestres", "id")):
            for wkt, srid in negatives:
                cur.execute("SAVEPOINT invalid_geometry")
                try:
                    cur.execute(f"UPDATE gemapi.{table} SET geom=ST_GeomFromText(%s,%s) WHERE {id_filter}=%s",
                                (wkt, srid, site))
                except (psycopg2.errors.CheckViolation, psycopg2.errors.InvalidParameterValue):
                    pass
                else:
                    raise AssertionError((table, wkt, srid))
                finally:
                    cur.execute("ROLLBACK TO SAVEPOINT invalid_geometry")
                    cur.execute("RELEASE SAVEPOINT invalid_geometry")
        print("9 prestations sur site, 3 sur zone, 21 refus géométriques et mesures intégrales validés.")
    db.rollback()
    return records, site


def main():
    container = "sig-geom-multi-matrix-" + uuid4().hex[:10]
    command("docker", "run", "--rm", "-d", "--name", container, "-p", "127.0.0.1::5432",
            "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "-e", "POSTGRES_DB=seed", "postgis/postgis:16-3.4")
    app = None
    try:
        for _ in range(60):
            if command("docker", "exec", container, "pg_isready", "-h", "127.0.0.1",
                       "-U", "postgres", check=False).returncode == 0:
                break
            time.sleep(.5)
        port = command("docker", "port", container, "5432").stdout.strip().rsplit(":", 1)[-1]
        app = QgsApplication([], True)
        app.initQgis()
        with closing(psycopg2.connect(host="127.0.0.1", port=port, dbname="postgres", user="postgres")) as db:
            records, site = run_matrix(db)
        if os.environ.get("GEOM_MULTI_PDFS") == "1":
            out = ROOT / "audits/geom_multi_01"
            out.mkdir(parents=True, exist_ok=True)
            basemap = QgsVectorLayer("Polygon?crs=EPSG:2154", "Fond local", "memory")
            with patch("gemapi_app.report_pdf.background", return_value=None):
                export_detailed_report(records, out / "fiches.pdf", _shared_basemap=None)
            export_synthetic_portrait_report(
                records, {"site_terrestre": [site], "groups": ["site_terrestre"]},
                out / "synthese.pdf", basemap_layer=basemap,
            )
            del basemap
    finally:
        if app:
            QgsProject.instance().clear()
            app.exitQgis()
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
