"""UX-06 selection rules and scale on a disposable PostGIS demo database."""

import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.report_data import build_management_query  # noqa: E402
from test_postgres_integration import ROOT, command, load_demo_rows, sql  # noqa: E402


def main():
    container = "sig-prestations-search-" + uuid4().hex[:10]
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
        sql(container, (ROOT / "model/schema.sql").read_text())
        load_demo_rows(container)

        def one(query):
            return sql(container, query).stdout.strip()

        def ids(filters=None, text=""):
            result = one(build_management_query(filters or {}, text))
            return [row.split("|", 1)[0] for row in result.splitlines()] if result else []

        uid = {key: str(uuid4()) for key in
               ("commune", "ah1", "ah2", "site_parent", "zec1", "zec2", "site", "own", "linked",
                "via_zec", "outside", "nearby", "type", "type_no_title",
                "provider2")}
        provider = one("SELECT id::text FROM milieux.prestataires LIMIT 1")
        technician = one("SELECT id::text FROM milieux.techniciens LIMIT 1")
        sql(container, "INSERT INTO milieux.prestataires (id,nom) VALUES "
                       f"('{uid['provider2']}','Prestataire UX09');")
        river = one("SELECT id::text FROM milieux.cours_eau LIMIT 1")
        statuses = {code: one("SELECT id::text FROM milieux.statuts_prestations "
                              f"WHERE code='{code}'") for code in
                    ("PLANIFIE", "EN_COURS", "TERMINE", "ANNULE")}
        assert all(statuses.values())
        sql(container, f"BEGIN; INSERT INTO milieux.types_prestations (id,code,libelle, categorie_id) VALUES "
                       f"('{uid['type']}','UX06','Type UX06', 'cf2572fb-9365-5ac5-bdf4-0d66581d9aaa'),"
                       f"('{uid['type_no_title']}','UX06_NULL','Type sans titre', 'cf2572fb-9365-5ac5-bdf4-0d66581d9aaa'); "
                       f"INSERT INTO milieux.communes (id,insee,nom,geom) VALUES "
                       f"('{uid['commune']}','UX06','Commune UX06',"
                       "ST_Multi(ST_GeomFromText('POLYGON((-100 -100,100 -100,100 100,-100 100,-100 -100))',3950))); "
                       f"INSERT INTO milieux.ah (id,nom) VALUES "
                       f"('{uid['ah1']}','AH UX06 A'),('{uid['ah2']}','AH UX06 B'); "
                       f"INSERT INTO milieux.ah_stockage (id,ah_id,nom,geom) VALUES "
                       f"('{uid['zec1']}','{uid['ah1']}','ZEC UX06 A',ST_GeomFromText("
                       "'POLYGON((-20 -20,20 -20,20 20,-20 20,-20 -20))',3950)),"
                       f"('{uid['zec2']}','{uid['ah2']}','ZEC UX06 B',ST_GeomFromText("
                       "'POLYGON((-10 -10,30 -10,30 30,-10 30,-10 -10))',3950)); "
                       f"INSERT INTO milieux.ah_ouvrage (ah_id,geom) VALUES "
                       f"('{uid['ah1']}',ST_GeomFromText('LINESTRING(0 0,1 1)',3950)),"
                       f"('{uid['ah2']}',ST_GeomFromText('LINESTRING(2 2,3 3)',3950)); "
                       f"INSERT INTO milieux.sites_terrestres (id,nom,geom) VALUES "
                       f"('{uid['site_parent']}','Site parent UX06',ST_GeomFromText("
                       "'MULTIPOLYGON(((0 0,20 0,20 20,0 20,0 0)))',3950)); "
                       f"INSERT INTO public.vegetation(famille_vegetation,id,site_terrestre_id,designation,geometry) VALUES "
                       f"('ARBRES','{uid['site']}','{uid['site_parent']}','Site UX06',"
                       "ST_GeomFromText('MULTIPOINT((10 10))',3950)); COMMIT;")
        rows = (
            ("own", "Travaux géométrie", "type", "PLANIFIE", "POINT(0 0)"),
            ("linked", None, "type_no_title", "TERMINE", "POINT(10 10)"),
            ("via_zec", "Travaux sur ZEC", "type", "EN_COURS", "POINT(15 15)"),
            ("outside", "Hors commune", "type", "ANNULE", "POINT(10000 10000)"),
            ("nearby", "Proche mais non liée", "type", "PLANIFIE", "POINT(1 1)"),
        )
        statements = ["BEGIN;"]
        for key, title, type_key, status, geometry in rows:
            title_sql = "NULL" if title is None else "'" + title.replace("'", "''") + "'"
            geometry_sql = f"ST_GeomFromText('{geometry}',3950)"
            start_date = "2026-12-01" if key == "linked" else "2027-01-01"
            statements.append("INSERT INTO milieux.prestations "
                           "(id,intitule,type_prestation_id,prestataire_id,statut_id,"
                           "technicien_id,date_debut,date_fin,geom) VALUES "
                           f"('{uid[key]}',{title_sql},'{uid[type_key]}',"
                           f"'{uid['provider2'] if key == 'nearby' else provider}',"
                           f"'{statuses[status]}','{technician}','{start_date}','2027-01-15',"
                           f"{geometry_sql});")
        statements.append(f"UPDATE milieux.prestations SET ah_stockage_id='{uid['zec2']}' WHERE id='{uid['own']}'; "
                       f"UPDATE milieux.prestations SET ah_stockage_id='{uid['zec1']}' WHERE id='{uid['via_zec']}'; "
                       f"UPDATE milieux.prestations SET vegetation_id='{uid['site']}',geom=NULL "
                       f"WHERE id='{uid['linked']}'; "
                       f"UPDATE milieux.prestations SET cours_eau_id='{river}' WHERE id IN ('{uid['nearby']}','{uid['outside']}'); COMMIT;")
        sql(container, "\n".join(statements))

        assert len(ids()) == 105
        assert ids({"providers": [uid["provider2"]]}) == [uid["nearby"]]
        assert uid["nearby"] not in ids({"providers": [provider]})
        assert set(ids({"providers": [provider, uid["provider2"]]})) == (
            set(ids({"providers": [provider]})) | {uid["nearby"]})
        assert ids({"providers": [uid["provider2"]],
                    "statuses": [statuses["PLANIFIE"]]}) == [uid["nearby"]]
        assert ids({"providers": [uid["provider2"]],
                    "statuses": [statuses["TERMINE"]]}) == []
        assert ids(text="Type sans titre") == [uid["linked"]]
        assert not ids(text="introuvable")
        by_status_year = set(ids({"statuses": [statuses["PLANIFIE"], statuses["TERMINE"]],
                                  "years": [2027]}))
        assert {uid["own"], uid["linked"], uid["nearby"]} <= by_status_year
        assert not {uid["via_zec"], uid["outside"]} & by_status_year
        assert set(ids({"ah_stockage": [uid["zec1"], uid["zec2"]]})) == {
            uid["own"], uid["via_zec"]}
        assert len(ids({"ah_stockage": [uid["zec1"], uid["zec2"]]})) == 2
        ouvrage = one("SELECT ah_ouvrage_id::text FROM milieux.prestations "
                      "WHERE ah_ouvrage_id IS NOT NULL ORDER BY ah_ouvrage_id LIMIT 1")
        by_storage = set(ids({"ah_stockage": [uid["zec1"]]}))
        by_ouvrage = set(ids({"ah_ouvrage": [ouvrage]}))
        assert by_storage and by_ouvrage
        assert set(ids({"ah_stockage": [uid["zec1"]], "ah_ouvrage": [ouvrage]})) == (
            by_storage | by_ouvrage)
        assert ids({"ah_stockage": [uid["zec1"]], "vegetation": [uid["site"]]}) == []
        assert ids({"ah_stockage": [uid["zec1"]], "cours_eau": [river]}) == []
        assert set(ids({"communes": [uid["commune"]]})) == {
            uid["own"], uid["linked"], uid["via_zec"], uid["nearby"]}
        assert uid["nearby"] not in ids({"ah_stockage": [uid["zec1"]]})
        assert not ids(text="x' OR 1=1 --")
        # Completed work overlaps 2026 only if its interval starts there;
        # planned work uses its start year regardless of forecast end.
        assert uid["linked"] in ids({"years": [2026]})

        timings = []
        for amount, expected in ((50, 155), (450, 605)):
            sql(container, "BEGIN; WITH created AS (INSERT INTO milieux.prestations "
                           "(intitule,type_prestation_id,prestataire_id,statut_id,technicien_id,"
                           "date_debut,date_fin,geom,cours_eau_id) SELECT 'Charge ' || n::text, "
                           f"'{uid['type']}','{provider}','{statuses['PLANIFIE']}','{technician}',"
                           f"'2028-01-01','2028-01-15',"
                           f"ST_SetSRID(ST_Point(n+1000,n+1000),3950),'{river}' "
                           f"FROM generate_series(1,{amount}) n RETURNING id) "
                           "SELECT id FROM created; COMMIT;")
            start = time.perf_counter()
            assert len(ids()) == expected
            assert set(ids({"ah_stockage": [uid["zec1"], uid["zec2"]]})) == {
                uid["own"], uid["via_zec"]}
            timings.append(time.perf_counter() - start)
        print("Recherche UX-06 : 105 cas métier, puis 155 et 605 prestations ; "
              f"requêtes en {timings[0]:.2f} s et {timings[1]:.2f} s")
    finally:
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
