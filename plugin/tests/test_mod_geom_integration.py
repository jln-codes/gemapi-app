"""Current prestation geometry contract on disposable PostGIS."""

import time
from uuid import uuid4

from test_postgres_integration import ROOT, command, sql


def main():
    container = "sig-prestations-mod-geom-" + uuid4().hex[:10]
    command("docker", "run", "--rm", "-d", "--name", container,
            "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgis/postgis:16-3.4")
    try:
        for _ in range(60):
            if command("docker", "exec", container, "pg_isready", "-h", "127.0.0.1",
                       "-U", "postgres", check=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("PostGIS local indisponible")
        sql(container, "CREATE EXTENSION IF NOT EXISTS postgis;")
        sql(container, (ROOT / "model/schema.sql").read_text())
        sql(container, "BEGIN; INSERT INTO gemapi.prestataires(id,nom) VALUES "
                       "('11111111-1111-1111-1111-111111111111','Fictif'); "
                       "INSERT INTO gemapi.techniciens(id,nom) VALUES "
                       "('66666666-6666-6666-6666-666666666666','Responsable fictif'); "
                       "INSERT INTO gemapi.types_prestations(id,code,libelle, categorie_id) VALUES "
                       "('22222222-2222-2222-2222-222222222222','TEST','Fictif', 'cf2572fb-9365-5ac5-bdf4-0d66581d9aaa'); "
                       "INSERT INTO gemapi.ah(id,nom) VALUES "
                       "('55555555-5555-5555-5555-555555555555','AH fictif'); "
                       "INSERT INTO gemapi.ah_stockage(id,ah_id,nom,geom) VALUES "
                       "('33333333-3333-3333-3333-333333333333',"
                       "'55555555-5555-5555-5555-555555555555','Fictive',"
                       "ST_GeomFromText('POLYGON((0 0,10 0,10 10,0 10,0 0))',3950)); "
                       "INSERT INTO gemapi.ah_ouvrage(ah_id,geom) VALUES "
                       "('55555555-5555-5555-5555-555555555555',"
                       "ST_GeomFromText('LINESTRING(0 0,10 0)',3950)); "
                       "INSERT INTO gemapi.prestations(id,type_prestation_id,prestataire_id,"
                       "statut_id,technicien_id,date_debut,date_fin,ah_stockage_id,geom) VALUES "
                       "('44444444-4444-4444-4444-444444444444',"
                       "'22222222-2222-2222-2222-222222222222',"
                       "'11111111-1111-1111-1111-111111111111',"
                       "(SELECT id FROM gemapi.statuts_prestations WHERE code='PLANIFIE'),"
                       "'66666666-6666-6666-6666-666666666666',"
                       "'2027-01-01','2027-01-02','33333333-3333-3333-3333-333333333333',ST_GeomFromText('POINT(2 2)',3950)); "
                       "UPDATE gemapi.prestations SET ah_stockage_id='33333333-3333-3333-3333-333333333333' WHERE id='44444444-4444-4444-4444-444444444444'; COMMIT;")
        assert sql(container, "SELECT is_nullable FROM information_schema.columns "
                   "WHERE table_schema='gemapi' AND table_name='prestations' "
                   "AND column_name='geom'").stdout.strip() == "YES"
        assert sql(container, "SELECT count(*) FROM pg_indexes WHERE schemaname='gemapi' "
                   "AND tablename='prestations' AND indexname='prestations_geom_idx'").stdout.strip() == "1"
        before = sql(container, "SELECT id::text FROM gemapi.prestations ORDER BY id; "
                     "SELECT id::text,ah_stockage_id::text "
                     "FROM gemapi.prestations WHERE ah_stockage_id IS NOT NULL ORDER BY id;").stdout
        prefix = ("BEGIN; WITH created AS (INSERT INTO gemapi.prestations(type_prestation_id,prestataire_id,"
                  "statut_id,technicien_id,date_debut,date_fin,ah_stockage_id,geom) VALUES "
                  "('22222222-2222-2222-2222-222222222222',"
                  "'11111111-1111-1111-1111-111111111111',"
                  "(SELECT id FROM gemapi.statuts_prestations WHERE code='PLANIFIE'),"
                  "'66666666-6666-6666-6666-666666666666',"
                  "'2027-01-01','2027-01-02','33333333-3333-3333-3333-333333333333',")
        accepted = (
            "POINT(1 1)", "MULTIPOINT((1 1),(11 11))",
            "LINESTRING(0 0,1 1)", "MULTILINESTRING((0 0,1 1),(10 10,11 11))",
            "POLYGON((0 0,1 0,1 1,0 1,0 0))",
            "MULTIPOLYGON(((0 0,1 0,1 1,0 1,0 0)),"
            "((10 10,11 10,11 11,10 11,10 10)))",
        )
        for wkt in accepted:
            sql(container, prefix + f"ST_GeomFromText('{wkt}',3950)) RETURNING id) "
                "SELECT id FROM created; COMMIT;")
        assert sql(container, "SELECT count(DISTINCT ST_GeometryType(geom)) "
                   "FROM gemapi.prestations").stdout.strip() == "6"
        rejected = ("ST_GeomFromText('POINT EMPTY',3950)",
                    "ST_GeomFromText('POLYGON((0 0,1 1,1 0,0 1,0 0))',3950)",
                    "ST_GeomFromText('POINT(1 1)',4326)",
                    "ST_GeomFromText('GEOMETRYCOLLECTION(POINT(1 1))',3950)",
                    "ST_GeomFromText('POINT Z(1 1 2)',3950)")
        for expression in rejected:
            result = sql(container, prefix + expression + ") RETURNING id) "
                "SELECT id FROM created; COMMIT;",
                check=False)
            assert result.returncode != 0, expression
        assert sql(container, "SELECT count(*) FROM gemapi.prestations").stdout.strip() == "7"
        assert sql(container, "SELECT count(ah_stockage_id) FROM gemapi.prestations").stdout.strip() == "7"
        assert before.startswith("44444444-4444-4444-4444-444444444444")
        print("Schéma courant : six types acceptés, six cas rejetés, UUID et liens conservés")
    finally:
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
