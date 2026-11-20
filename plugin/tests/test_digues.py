"""DIG-01 : schéma neuf et vue QGIS sur PostGIS jetable.

Exécuter avec le Python QGIS (QT_QPA_PLATFORM=offscreen) et Docker disponible.
"""

import time
from uuid import uuid4

from qgis.core import QgsApplication, QgsDataSourceUri, QgsVectorDataProvider, QgsVectorLayer

from test_postgres_integration import ROOT, command, sql


def rejected(container, statement, fragment):
    result = sql(container, statement, check=False)
    assert result.returncode != 0, statement
    assert fragment in result.stderr, result.stderr


def main():
    container = "sig-prestations-dig01-" + uuid4().hex[:10]
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
        command("docker", "exec", container, "mkdir", "-p", "/repo/demo")
        command("docker", "cp", str(ROOT / "model"), f"{container}:/repo/model")
        command("docker", "cp", str(ROOT / "demo" / "data"), f"{container}:/repo/demo/data")
        command("docker", "exec", "-e", "PGUSER=postgres", container,
                "bash", "/repo/demo/data/importer_base_neuve.sh", "postgres")
        assert sql(container, "SELECT count(*) FROM milieux.prestations;").stdout.strip() == "100"
        assert sql(container, "SELECT count(*) FROM milieux.cours_eau;").stdout.strip() == "58"
        assert sql(container, "SELECT count(*) FROM milieux.cours_eau WHERE "
                   "ST_GeometryType(geom)='ST_MultiLineString';").stdout.strip() == "58"
        assert sql(container, "SELECT count(*) FROM information_schema.columns "
                   "WHERE table_schema='milieux' AND table_name='digues' "
                   "AND column_name='geom';").stdout.strip() == "0"
        assert sql(container, "SELECT type,srid FROM geometry_columns WHERE "
                   "f_table_schema='milieux' AND f_table_name='digues_carte';"
                   ).stdout.strip() == "LINESTRING|3950"

        prest_before = sql(container, "SELECT string_agg(id::text,',' ORDER BY id) "
                          "FROM milieux.prestations;").stdout
        digue, river, section = (str(uuid4()) for _ in range(3))
        sql(container, f"BEGIN; INSERT INTO milieux.digues(id,nom) VALUES ('{digue}','Digue test'); "
                       f"INSERT INTO milieux.cours_eau(id,nom,source,direction,geom) VALUES ('{river}',"
                       "'Rivière test','TEST',TRUE,ST_Multi(ST_GeomFromText('LINESTRING(0 0,100 0)',3950))); "
                       "INSERT INTO milieux.digues_reperes "
                       "(id,digue_id,riviere_id,rive,debut_fraction,fin_fraction) "
                       f"VALUES ('{section}','{digue}','{river}','G',0.20,0.45); COMMIT;")
        assert sql(container, f"SELECT ST_AsEWKB(s.geom_reference) = "
                   "ST_AsEWKB(ST_LineSubstring(ST_GeometryN(r.geom,1),0.20,0.45)), "
                   "ST_Length(s.geom_reference), v.etat_referentiel "
                   "FROM milieux.digues_reperes s "
                   "JOIN milieux.cours_eau r ON r.id=s.riviere_id "
                   "JOIN milieux.digues_carte v ON v.id=s.id "
                   f"WHERE s.id='{section}';").stdout.strip() == "t|25|CONFORME"
        assert sql(container, "SELECT count(*) FROM milieux.digues_reperes;").stdout.strip() == "4"
        rejected(container, f"INSERT INTO milieux.digues_reperes(digue_id,riviere_id,rive,"
                 f"debut_fraction,fin_fraction) VALUES ('{digue}','{river}','D',0.2,0.45);",
                 "digues_reperes_digue_unique")

        for statement, message in (
            (f"INSERT INTO milieux.digues_reperes(digue_id,riviere_id,rive,"
             f"debut_fraction,fin_fraction) VALUES ('{digue}','{river}','G',-0.1,0.5);",
             "Fractions attendues"),
            (f"INSERT INTO milieux.digues_reperes(digue_id,riviere_id,rive,"
             f"debut_fraction,fin_fraction) VALUES ('{digue}','{river}','G',0.1,1.1);",
             "Fractions attendues"),
            (f"INSERT INTO milieux.digues_reperes(digue_id,riviere_id,rive,"
             f"debut_fraction,fin_fraction) VALUES ('{digue}','{river}','G',0.5,0.5);",
             "Fractions attendues"),
            (f"INSERT INTO milieux.digues_reperes(digue_id,riviere_id,rive,"
             f"debut_fraction,fin_fraction) VALUES ('{digue}','{river}','X',0.1,0.5);",
             "digues_reperes_rive_check"),
            (f"INSERT INTO milieux.digues_reperes(digue_id,riviere_id,rive,"
             f"debut_fraction,fin_fraction) VALUES ('{uuid4()}','{river}','G',0.1,0.5);",
             "foreign key"),
            (f"INSERT INTO milieux.digues_reperes(digue_id,riviere_id,rive,"
             f"debut_fraction,fin_fraction) VALUES ('{digue}','{uuid4()}','G',0.1,0.5);",
             "introuvable"),
        ):
            result = sql(container, statement, check=False)
            assert result.returncode != 0, statement
            # PostgreSQL/PostGIS may reject a fraction before the CHECK fires.
            assert result.stderr, (message, statement)

        multi, self_crossing = (str(uuid4()) for _ in range(2))
        sql(container, f"INSERT INTO milieux.cours_eau(id,nom,source,direction,geom) VALUES "
                       f"('{multi}','Tracé multiple','TEST',TRUE,ST_GeomFromText("
                       "'MULTILINESTRING((0 0,10 0),(10 0,20 0))',3950)),"
                       f"('{self_crossing}','Tracé croisé','TEST',TRUE,ST_Multi(ST_GeomFromText("
                       "'LINESTRING(0 0,10 10,0 10,10 0)',3950)));")
        rejected(container, "INSERT INTO milieux.digues_reperes"
                 "(digue_id,riviere_id,rive,debut_fraction,fin_fraction) "
                 f"VALUES ('{digue}','{multi}','G',0.1,0.5);", "non admissible")
        rejected(container, "INSERT INTO milieux.digues_reperes"
                 "(digue_id,riviere_id,rive,debut_fraction,fin_fraction) "
                 f"VALUES ('{digue}','{self_crossing}','G',0.1,0.5);", "non admissible")

        frozen = sql(container, f"SELECT encode(ST_AsEWKB(geom_reference),'hex'), "
                     "geom_riviere_signature FROM milieux.digues_reperes "
                     f"WHERE id='{section}';").stdout.strip()
        sql(container, f"UPDATE milieux.cours_eau SET geom=ST_Multi(ST_GeomFromText("
                       f"'LINESTRING(0 10,100 10)',3950)) WHERE id='{river}';")
        assert sql(container, f"SELECT encode(ST_AsEWKB(geom_reference),'hex'), "
                   "geom_riviere_signature FROM milieux.digues_reperes "
                   f"WHERE id='{section}';").stdout.strip() == frozen
        assert sql(container, f"SELECT etat_referentiel FROM "
                   f"milieux.digues_carte WHERE id='{section}';"
                   ).stdout.strip() == "REFERENTIEL_MODIFIE"
        rejected(container, f"UPDATE milieux.digues_reperes SET rive='D' "
                       f"WHERE id='{section}';", 'Référence figée')
        assert sql(container, f"SELECT encode(ST_AsEWKB(geom_reference),'hex'), "
                   "geom_riviere_signature FROM milieux.digues_reperes "
                   f"WHERE id='{section}';").stdout.strip() == frozen
        rejected(container, "UPDATE milieux.digues_reperes SET "
                 "geom_reference=ST_GeomFromText('LINESTRING(1 1,2 2)',3950) "
                 f"WHERE id='{section}';", "Référence figée")
        rejected(container, "UPDATE milieux.digues_reperes SET "
                 f"geom_riviere_signature='fausse' WHERE id='{section}';", "Référence figée")
        rejected(container, f"UPDATE milieux.digues_reperes SET debut_fraction=0.3,revision_validation=revision_validation+1 WHERE id='{section}';",
                 "non admissible")
        # Explicit human qualification of this invented test course only.
        sql(container, f"UPDATE milieux.cours_eau SET direction=TRUE WHERE id='{river}';")
        sql(container, f"UPDATE milieux.digues_reperes SET "
                       f"debut_fraction=0.3,fin_fraction=0.6,revision_validation=revision_validation+1 WHERE id='{section}';")
        assert sql(container, f"SELECT ST_Y(ST_StartPoint(geom)), "
                   f"ST_Length(geom), etat_referentiel FROM "
                   f"milieux.digues_carte WHERE id='{section}';"
                   ).stdout.strip() == "10|30|CONFORME"
        other_river = str(uuid4())
        sql(container, f"INSERT INTO milieux.cours_eau(id,nom,source,direction,geom) VALUES "
                       f"('{other_river}','Nouvelle référence','TEST',TRUE,"
                       "ST_Multi(ST_GeomFromText('LINESTRING(0 20,100 20)',3950))); "
                       f"UPDATE milieux.digues_reperes SET riviere_id='{other_river}',revision_validation=revision_validation+1 "
                       f"WHERE id='{section}';")
        assert sql(container, f"SELECT ST_Y(ST_StartPoint(geom)), "
                   f"etat_referentiel FROM milieux.digues_carte "
                   f"WHERE id='{section}';").stdout.strip() == "20|CONFORME"
        rejected(container, f"DELETE FROM milieux.digues WHERE id='{digue}';",
                 "foreign key")
        rejected(container, f"DELETE FROM milieux.cours_eau WHERE id='{other_river}';",
                 "foreign key")
        assert sql(container, "SELECT string_agg(id::text,',' ORDER BY id) "
                   "FROM milieux.prestations;").stdout == prest_before
        assert sql(container, "SELECT count(*) FROM milieux.prestations_fiches;").stdout.strip() == "100"

        sql(container, "CREATE ROLE dig01_read LOGIN; "
                       "GRANT USAGE ON SCHEMA milieux TO dig01_read; "
                       "GRANT SELECT ON milieux.digues_carte TO dig01_read;")
        missing_grants = sql(container, "SET ROLE dig01_read; "
                             "SELECT count(*) FROM milieux.digues_carte;",
                             check=False)
        assert missing_grants.returncode != 0 and "permission denied" in missing_grants.stderr
        sql(container, "GRANT SELECT ON milieux.digues_reperes, milieux.digues, "
                       "milieux.cours_eau TO dig01_read;")
        assert sql(container, "SET ROLE dig01_read; SELECT count(*) "
                   f"FROM milieux.digues_carte WHERE digue_id='{digue}';").stdout.strip().endswith("1")
        no_write = sql(container, "SET ROLE dig01_read; INSERT INTO milieux.digues(nom) "
                       "VALUES ('interdit');", check=False)
        assert no_write.returncode != 0 and "permission denied" in no_write.stderr
        rejected(container, "UPDATE milieux.digues_carte SET rive='G';",
                 "cannot update view")

        port = command("docker", "port", container, "5432").stdout.strip().rsplit(":", 1)[-1]
        app = QgsApplication([], True)
        app.initQgis()
        uri = QgsDataSourceUri()
        uri.setConnection("127.0.0.1", port, "postgres", "dig01_read", "")
        uri.setDataSource("milieux", "digues_carte", "geom", "", "id")
        layer = QgsVectorLayer(uri.uri(False), "Digues", "postgres")
        assert layer.isValid(), layer.error().summary()
        assert layer.featureCount() == 4
        capabilities = layer.dataProvider().capabilities()
        assert not capabilities & QgsVectorDataProvider.AddFeatures
        assert not capabilities & QgsVectorDataProvider.ChangeGeometries
        print("DIG-01 : schéma neuf, gel géométrique, "
              "écarts de référentiel, droits et lecture QGIS validés")
    finally:
        if app is not None:
            app.exitQgis()
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
