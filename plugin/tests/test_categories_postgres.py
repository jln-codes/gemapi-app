"""Validate the current category reference in a fresh disposable PostGIS."""
import sqlite3
import time
from uuid import uuid4
from test_postgres_integration import ROOT, command, sql


def main():
    container = "sig-categories-" + uuid4().hex[:8]
    command("docker", "run", "--rm", "-d", "--name", container,
            "-p", "127.0.0.1::5432", "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgis/postgis:16-3.4")
    try:
        for _ in range(60):
            if command("docker", "exec", container, "pg_isready", "-h", "127.0.0.1",
                       "-U", "postgres", check=False).returncode == 0:
                break
            time.sleep(.5)
        sql(container, "CREATE EXTENSION IF NOT EXISTS postgis;")
        sql(container, (ROOT / "model/schema.sql").read_text())
        port = command("docker", "port", container, "5432").stdout.strip().rsplit(":", 1)[-1]
        command("ogr2ogr", "-f", "PostgreSQL",
                f"PG:host=127.0.0.1 port={port} dbname=postgres user=postgres",
                str(ROOT / "demo/gpkg/referentiels.gpkg"),
                "-append", "-nln", "milieux.types_prestations",
                "-sql", "SELECT id,code,libelle,actif,categorie_id FROM types_prestations", "-unsetFid")
        imported = sql(container, "SELECT id,code,libelle,categorie_id FROM "
                       "milieux.types_prestations ORDER BY code").stdout
        # Reinitializing the reference twice must neither duplicate nor renumber it.
        for _ in range(2):
            sql(container, (ROOT / "demo/data/05_types_prestations.sql").read_text())
            assert sql(container, "SELECT id,code,libelle,categorie_id FROM "
                       "milieux.types_prestations ORDER BY code").stdout == imported
        sql(container, (ROOT / "model/roles_milieux.sql").read_text())
        rows = sql(container, "SELECT t.id,t.code,t.libelle,t.categorie_id,c.libelle "
                   "FROM milieux.types_prestations t JOIN milieux.prestations_categorie c "
                   "ON c.id=t.categorie_id ORDER BY t.code").stdout.strip().splitlines()
        with sqlite3.connect(ROOT / "demo/gpkg/referentiels.gpkg") as db:
            expected = db.execute(
                "SELECT t.id,t.code,t.libelle,t.categorie_id,c.libelle "
                "FROM types_prestations t JOIN prestations_categorie c "
                "ON c.id=t.categorie_id ORDER BY t.code").fetchall()
        assert rows == ["|".join(row) for row in expected]
        assert sql(container, "SELECT string_agg(n::text,',' ORDER BY ordre) FROM "
                   "(SELECT c.ordre,count(t.id) n FROM milieux.prestations_categorie c "
                   "LEFT JOIN milieux.types_prestations t ON t.categorie_id=c.id "
                   "GROUP BY c.ordre) counts").stdout.strip() == "3,2,3,1"
        with sqlite3.connect(ROOT / "demo/gpkg/referentiels.gpkg") as db:
            categories = db.execute(
                "SELECT id,libelle,ordre FROM prestations_categorie ORDER BY ordre").fetchall()
            assert not db.execute("PRAGMA foreign_key_check").fetchall()
        assert sql(container, "SELECT id,libelle,ordre FROM "
                   "milieux.prestations_categorie ORDER BY ordre").stdout.strip().splitlines() == [
                       "|".join(str(value) for value in row) for row in categories]
        for value in ("NULL", "'00000000-0000-0000-0000-000000000000'"):
            assert sql(container, "INSERT INTO milieux.types_prestations "
                       "(code,libelle,categorie_id) VALUES ('INVALIDE','Invalide',"
                       + value + ")", check=False).returncode != 0
        assert sql(container, "DELETE FROM milieux.prestations_categorie",
                   check=False).returncode != 0
        assert sql(container, "SET ROLE milieux_consultation; "
                   "SELECT count(*) FROM milieux.prestations_categorie").stdout.strip().endswith("4")
        print("PostGIS neuf : catégories, classement 3/2/3/1, UUID/libellés SQL-GPKG, "
              "NOT NULL, clés étrangères, droits, import OGR et réinitialisation sans doublon OK")
    finally:
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
