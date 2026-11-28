"""TAB-01A: validate the enriched view on disposable PostGIS databases.

Run explicitly with Docker: python3 plugin/tests/test_prestations_fiches.py
No port is published; the container is removed when the test finishes.
"""

import json
import time
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import ZipFile

from test_postgres_integration import ROOT, command, sql

TYPE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROVIDER_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TECH_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def project_fields():
    with ZipFile(ROOT / "demo/prestations_demo.qgz") as archive:
        assert archive.testzip() is None
        project_xml = archive.read("prestations_demo.qgs")
        assert b"prestations_fiches_v2" not in project_xml
        root = ElementTree.fromstring(project_xml)
    layers = root.findall("./projectlayers/maplayer")
    assert len(layers) == 26
    assert len({layer.findtext('id') for layer in layers}) == len(layers)
    assert root.findall("./relations/relation")
    matches = [layer for layer in layers
               if '"prestations_fiches"' in layer.findtext("datasource", "")]
    assert len(matches) == 1
    layer = matches[0]
    assert layer.findtext("id").startswith("prestations_fiches_")
    assert layer.get("wkbType") == "NoGeometry" and layer.get("readOnly") == "1"
    assert layer.findtext("provider") == "postgres"
    assert '"gemapi"."prestations_fiches"' in layer.findtext("datasource")
    fields = [field.get("name") for field in layer.findall("./fieldConfiguration/field")]
    columns = layer.findall("./attributetableconfig/columns/column")
    shown = [column for column in columns if column.get("hidden") == "0"]
    hidden = [column for column in columns if column.get("hidden") == "1"
              and column.get("type") == "field"]
    assert set(fields) >= {"id", "position", "rive"}

    assert set(fields) >= {
        "id", "type_prestation_id", "prestataire_id", "statut_id",
        "technicien_id", "description", "photo_1", "photo_2",
    }
    # Hidden columns and native widget settings are user preferences.
    # Read-only enforcement is tested against the SQL view below.
    return fields


def scalar(container, statement):
    return sql(container, statement).stdout.strip()


def assert_rows(container):
    assert scalar(container, "SELECT count(*) FROM gemapi.prestations") == "7"
    assert scalar(container, "SELECT count(*) FROM gemapi.prestations_fiches") == "7"
    assert scalar(container, "SELECT count(*) - count(DISTINCT id) "
                  "FROM gemapi.prestations_fiches") == "0"
    assert scalar(container, "SELECT count(*) FROM ("
                  "(SELECT id FROM gemapi.prestations EXCEPT "
                  "SELECT id FROM gemapi.prestations_fiches) UNION ALL "
                  "(SELECT id FROM gemapi.prestations_fiches EXCEPT "
                  "SELECT id FROM gemapi.prestations)) x") == "0"
    assert scalar(container, "SELECT type_prestation, prestataire, statut, "
                  "technicien IS NOT NULL, type_geometrie, possede_geometrie, "
                  "intitule IS NULL, quantite, unite FROM "
                  "gemapi.prestations_fiches WHERE id="
                  "'10000000-0000-0000-0000-000000000001'") == (
                      "Abattage|Entreprise Test|Planifié|t|Point|t|t|17|arbres")
    assert scalar(container, "SELECT technicien, technicien_id='" + TECH_ID + "' "
                  "FROM gemapi.prestations_fiches WHERE id="
                  "'10000000-0000-0000-0000-000000000002'") == "Ada Lovelace|t"
    expected = [
        ("Point", "ST_Point", "t", "", ""),
        ("Point", "ST_Point", "t", "", ""),
        ("Point", "ST_MultiPoint", "t", "", ""),
        ("Ligne", "ST_LineString", "t", "5", ""),
        ("Ligne", "ST_MultiLineString", "t", "10", ""),
        ("Polygone", "ST_Polygon", "t", "", "100"),
        ("Polygone", "ST_MultiPolygon", "t", "", "200"),
    ]
    got = scalar(container, "SELECT type_geometrie, "
                 "coalesce(type_geometrie_postgis,''), "
                 "possede_geometrie, coalesce(longueur_m::text,''), "
                 "coalesce(surface_m2::text,'') "
                 "FROM gemapi.prestations_fiches ORDER BY id").splitlines()
    for row, values in zip(got, expected, strict=True):
        actual = row.split("|")
        assert actual[:3] == list(values[:3]), (actual, values)
        assert (not actual[3] and not values[3]) or abs(float(actual[3]) - float(values[3])) < 1e-9
        assert (not actual[4] and not values[4]) or abs(float(actual[4]) - float(values[4])) < 1e-9
    assert scalar(container, "SELECT abs(surface_ha - 0.01) < 1e-12 FROM "
                  "gemapi.prestations_fiches WHERE id="
                  "'10000000-0000-0000-0000-000000000006'") == "t"
    assert scalar(container, "SELECT abs(surface_ha - 0.02) < 1e-12 FROM "
                  "gemapi.prestations_fiches WHERE id="
                  "'10000000-0000-0000-0000-000000000007'") == "t"
    assert scalar(container, "SELECT quantite <> longueur_m FROM "
                  "gemapi.prestations_fiches WHERE id="
                  "'10000000-0000-0000-0000-000000000004'") == "t"
    assert scalar(container, "SELECT photo_1, photo_1_commentaire, "
                  "photo_2, photo_2_commentaire FROM "
                  "gemapi.prestations_fiches WHERE id="
                  "'10000000-0000-0000-0000-000000000006'") == (
                      "images/avant.jpg|Avant|images/apres.jpg|Après")
    assert scalar(container, "SELECT count(ah_stockage_id) FROM gemapi.prestations "
                  "WHERE id='10000000-0000-0000-0000-000000000006'") == "1"
    assert scalar(container, "SELECT count(*) FROM gemapi.prestations_fiches "
                  "WHERE id='10000000-0000-0000-0000-000000000006'") == "1"
    assert scalar(container, "SELECT count(*) FROM information_schema.columns "
                  "WHERE table_schema='gemapi' AND table_name='prestations_fiches' "
                  "AND column_name='geom'") == "0"
    assert scalar(container, "SELECT is_updatable FROM information_schema.views "
                  "WHERE table_schema='gemapi' AND table_name='prestations_fiches'") == "NO"
    assert scalar(container, "SELECT reloptions @> ARRAY['security_invoker=true']::text[] "
                  "FROM pg_class WHERE oid='gemapi.prestations_fiches'::regclass") == "t"
    assert sql(container, "UPDATE gemapi.prestations_fiches SET intitule='Interdit' "
               "WHERE id='10000000-0000-0000-0000-000000000001'", check=False).returncode != 0
    assert sql(container, "DELETE FROM gemapi.prestations_fiches WHERE "
               "id='10000000-0000-0000-0000-000000000001'", check=False).returncode != 0


def seed(container):
    status_id = scalar(container, "SELECT id FROM gemapi.statuts_prestations "
                       "WHERE code='PLANIFIE'")
    sql(container, f"BEGIN; INSERT INTO gemapi.types_prestations (id, code, libelle, categorie_id) "
                   f"VALUES ('{TYPE_ID}','ABATTAGE','Abattage', 'cf2572fb-9365-5ac5-bdf4-0d66581d9aaa'); "
                   f"INSERT INTO gemapi.prestataires (id, nom) "
                   f"VALUES ('{PROVIDER_ID}','Entreprise Test'); "
                   f"INSERT INTO gemapi.techniciens (id, nom, prenom) "
                   f"VALUES ('{TECH_ID}','Lovelace','Ada'); "
                   "INSERT INTO gemapi.prestations (id, type_prestation_id, "
                   "prestataire_id, statut_id, technicien_id, date_debut, date_fin, quantite, unite, geom) "
                   "VALUES ('10000000-0000-0000-0000-000000000001', "
                   f"'{TYPE_ID}', '{PROVIDER_ID}', '{status_id}', '{TECH_ID}', "
                   "'2027-01-01','2027-01-02',17,'arbres',"
                   "ST_GeomFromText('POINT(100 100)',3950)); "
                   "INSERT INTO gemapi.cours_eau(id,nom,source,geom) VALUES "
                   "('40000000-0000-0000-0000-000000000001','Rivière témoin','TEST',"
                   "ST_GeomFromText('MULTILINESTRING((0 0,100 100))',3950)); "
                   "UPDATE gemapi.prestations SET cours_eau_id='40000000-0000-0000-0000-000000000001' WHERE id='10000000-0000-0000-0000-000000000001'; COMMIT;")
    geometries = [
        "POINT(0 0)",
        "MULTIPOINT((0 0),(1 1))",
        "LINESTRING(0 0,3 4)",
        "MULTILINESTRING((0 0,3 4),(0 0,0 5))",
        "POLYGON((0 0,10 0,10 10,0 10,0 0))",
        "MULTIPOLYGON(((0 0,10 0,10 10,0 10,0 0)),"
        "((20 0,30 0,30 10,20 10,20 0)))",
    ]
    for number, wkt in enumerate(geometries, start=2):
        uid = f"10000000-0000-0000-0000-{number:012d}"
        photos = (", photo_1, photo_1_commentaire, photo_2, photo_2_commentaire"
                  if number == 6 else "")
        photo_values = (", 'images/avant.jpg', 'Avant', 'images/apres.jpg', 'Après'"
                        if number == 6 else "")
        sql(container, "BEGIN; INSERT INTO gemapi.prestations "
                       "(id, type_prestation_id, prestataire_id, statut_id, technicien_id, "
                       f"date_debut, date_fin, quantite, geom{photos}) "
                       f"VALUES ('{uid}','{TYPE_ID}','{PROVIDER_ID}','{status_id}','{TECH_ID}',"
                       f"'2027-01-01','2027-01-02',17,"
                       f"ST_GeomFromText('{wkt}',3950){photo_values}); "
                       f"UPDATE gemapi.prestations SET cours_eau_id='40000000-0000-0000-0000-000000000001' WHERE id='{uid}'; COMMIT;")
    sql(container, "BEGIN; INSERT INTO gemapi.ah(id,nom) VALUES "
                   "('30000000-0000-0000-0000-000000000001','AH 1'),"
                   "('30000000-0000-0000-0000-000000000002','AH 2'); "
                   "INSERT INTO gemapi.ah_stockage (id, ah_id, nom, geom) VALUES "
                   "('20000000-0000-0000-0000-000000000001',"
                   "'30000000-0000-0000-0000-000000000001','Z1',"
                   "ST_GeomFromText('POLYGON((0 0,1 0,1 1,0 1,0 0))',3950)),"
                   "('20000000-0000-0000-0000-000000000002',"
                   "'30000000-0000-0000-0000-000000000002','Z2',"
                   "ST_GeomFromText('POLYGON((2 0,3 0,3 1,2 1,2 0))',3950)); "
                   "INSERT INTO gemapi.ah_ouvrage(ah_id,geom) VALUES "
                   "('30000000-0000-0000-0000-000000000001',"
                   "ST_GeomFromText('LINESTRING(0 0,1 0)',3950)),"
                   "('30000000-0000-0000-0000-000000000002',"
                   "ST_GeomFromText('LINESTRING(2 0,3 0)',3950)); "
                   "UPDATE gemapi.prestations SET cours_eau_id=NULL,ah_stockage_id='20000000-0000-0000-0000-000000000001' "
                   "WHERE id='10000000-0000-0000-0000-000000000006'; COMMIT;")



def measure(container, count):
    sql(container, "ANALYZE gemapi.prestations;")
    plan = json.loads(sql(container, "EXPLAIN (ANALYZE, FORMAT JSON) "
                          "SELECT * FROM gemapi.prestations_fiches").stdout)
    return round(plan[0]["Execution Time"], 3)


def main():
    fields = project_fields()
    container = "sig-prestations-view-" + uuid4().hex[:10]
    command("docker", "run", "--rm", "-d", "--name", container,
            "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgis/postgis:16-3.4")
    try:
        for _ in range(60):
            if command("docker", "exec", container, "pg_isready", "-h", "127.0.0.1",
                       "-U", "postgres", check=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("PostGIS de test indisponible")
        sql(container, "CREATE EXTENSION IF NOT EXISTS postgis;")
        sql(container, (ROOT / "model/schema.sql").read_text(encoding="utf-8"))
        assert scalar(container, "SELECT count(*) FROM information_schema.views "
                      "WHERE table_schema='gemapi' AND table_name LIKE 'prestations_fiches%'") == "1"
        assert scalar(container, "SELECT count(*) FROM gemapi.prestations_fiches") == "0"
        columns = scalar(container, "SELECT string_agg(column_name, ',' "
                         "ORDER BY ordinal_position) FROM information_schema.columns "
                         "WHERE table_schema='gemapi' AND table_name='prestations_fiches'")
        assert set(fields) <= set(columns.split(","))
        assert scalar(container, "SELECT srtext LIKE '%UNIT[\"metre\",1%' "
                      "FROM spatial_ref_sys WHERE srid=3950") == "t"
        seed(container)
        assert_rows(container)
        # Add test-only rows with valid geometry to measure full view scans.
        status_id = scalar(container, "SELECT id FROM gemapi.statuts_prestations "
                           "WHERE code='PLANIFIE'")
        for extra in (493, 4500):
            sql(container, "BEGIN; WITH created AS (INSERT INTO gemapi.prestations "
                           "(type_prestation_id, prestataire_id, statut_id, technicien_id, "
                           "date_debut, date_fin, cours_eau_id, geom) SELECT "
                           f"'{TYPE_ID}', '{PROVIDER_ID}', '{status_id}', '{TECH_ID}', "
                           "'2027-01-01', '2027-01-02', '40000000-0000-0000-0000-000000000001', "
                           "ST_SetSRID(ST_Point(n, n),3950) "
                           f"FROM generate_series(1,{extra}) AS n RETURNING id) "
                           "SELECT id FROM created; COMMIT;")
            count = int(scalar(container, "SELECT count(*) FROM gemapi.prestations"))
            assert count in (500, 5000)
            assert scalar(container, "SELECT count(*) FROM gemapi.prestations_fiches") == str(count)
            print(f"Vue : {count} lignes, EXPLAIN ANALYZE {measure(container, count)} ms")
        assert scalar(container, "SELECT count(*) - count(DISTINCT id) "
                      "FROM gemapi.prestations_fiches") == "0"

        print("Vue : schéma courant, six types et lecture seule OK")
    finally:
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
