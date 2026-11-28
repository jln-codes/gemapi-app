"""Disposable PostGIS test for versioned deletion and effective role rights."""
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.record import build_delete, build_insert
from test_postgres_integration import ROOT, command, sql


def fixture(container):
    sql(container, "CREATE EXTENSION IF NOT EXISTS postgis;")
    sql(container, (ROOT / 'model/schema.sql').read_text(encoding='utf-8'))
    sql(container, (ROOT / 'model/roles_milieux.sql').read_text(encoding='utf-8'))
    sql(container, "INSERT INTO gemapi.prestataires(nom) VALUES ('Prestataire jetable'); "
        "INSERT INTO gemapi.techniciens(nom) VALUES ('Technicien jetable'); "
        "INSERT INTO gemapi.types_prestations(categorie_id,code,libelle) "
        "SELECT id,'PERF09B','Type jetable' FROM gemapi.prestations_categorie LIMIT 1; "
        "INSERT INTO gemapi.ah(nom) VALUES ('AH jetable'); "
        "INSERT INTO gemapi.ah_stockage(ah_id,nom,geom) "
        "SELECT id,'Stockage jetable',ST_GeomFromText('POLYGON((0 0,10 0,10 10,0 0))',3950) "
        "FROM gemapi.ah LIMIT 1; "
        "INSERT INTO gemapi.sites_terrestres(nom,geom) "
        "VALUES ('Site jetable',ST_GeomFromText('MULTIPOLYGON(((0 0,10 0,10 10,0 0)))',3950)); "
        "INSERT INTO gemapi.vegetation(famille_vegetation,site_terrestre_id,designation,geometry) "
        "SELECT 'ARBRES',id,'Zone jetable',ST_GeomFromText('MULTIPOINT((1 1))',3950) "
        "FROM gemapi.sites_terrestres LIMIT 1;")


def values(container, photo):
    ids = sql(container, "SELECT (SELECT id::text FROM gemapi.prestataires LIMIT 1),"
        "(SELECT id::text FROM gemapi.techniciens LIMIT 1),"
        "(SELECT id::text FROM gemapi.types_prestations WHERE code='PERF09B'),"
        "(SELECT id::text FROM gemapi.statuts_prestations WHERE code='PLANIFIE'),"
        "(SELECT id::text FROM gemapi.ah_stockage LIMIT 1),"
        "(SELECT id::text FROM gemapi.vegetation LIMIT 1)").stdout.strip().split('|')
    assert len(ids) == 6 and all(ids)
    return dict(intitule='Essai de suppression', prestataire_id=ids[0],
                technicien_id=ids[1], type_prestation_id=ids[2], statut_id=ids[3],
                date_debut='2026-11-01', date_fin='2026-11-02', photo_1=str(photo)), ids[4:]


def insert(container, data, family, parent):
    rows = sql(container, build_insert(data, [(family, parent)]))
    uid = rows.stdout.strip().split('|')[0]
    assert uid
    return uid


def version(container, uid):
    return sql(container, f"SELECT xmin::text FROM gemapi.prestations WHERE id='{uid}'").stdout.strip()


def main():
    container = 'sig-prestations-09b-' + uuid4().hex[:10]
    command('docker', 'run', '--rm', '-d', '--name', container,
            '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', 'postgis/postgis:16-3.4')
    photo = ROOT / 'audits/PERF-QGIS-09B/photo-preservee.txt'
    photo.parent.mkdir(exist_ok=True, parents=True)
    photo.write_text('La suppression SQL ne touche pas ce fichier.', encoding='utf-8')
    try:
        for _ in range(60):
            if command('docker', 'exec', container, 'pg_isready', '-h', '127.0.0.1',
                       '-U', 'postgres', check=False).returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError('PostGIS jetable non prêt')
        fixture(container)
        data, (storage, zone) = values(container, photo)
        rights = sql(container, "SET ROLE milieux_consultation; SELECT "
            "has_table_privilege('gemapi.prestations','SELECT'),"
            "has_table_privilege('gemapi.prestations','INSERT'),"
            "has_table_privilege('gemapi.prestations','UPDATE'),"
            "has_table_privilege('gemapi.prestations','DELETE')").stdout.strip().splitlines()[-1]
        assert rights == 't|f|f|f', rights
        for role in ('milieux_prestations', 'milieux_patrimoine'):
            rights = sql(container, f"SET ROLE {role}; SELECT "
                "has_table_privilege('gemapi.prestations','SELECT'),"
                "has_table_privilege('gemapi.prestations','INSERT'),"
                "has_table_privilege('gemapi.prestations','UPDATE'),"
                "has_table_privilege('gemapi.prestations','DELETE')").stdout.strip().splitlines()[-1]
            assert rights == 't|t|t|t', (role, rights)
        uid = insert(container, data, 'ah_stockage', storage)
        before = version(container, uid)
        denied = sql(container, 'SET ROLE milieux_consultation; ' +
                     build_delete(uid, before), check=False)
        assert denied.returncode != 0 and 'SIG_PRESTATIONS_FORBIDDEN' in denied.stderr
        assert version(container, uid) == before
        sql(container, f"UPDATE gemapi.prestations SET description='Concurrent' WHERE id='{uid}'")
        conflict = sql(container, 'SET ROLE milieux_prestations; ' +
                       build_delete(uid, before), check=False)
        assert conflict.returncode != 0 and 'SIG_PRESTATIONS_CONFLICT' in conflict.stderr
        assert version(container, uid) != before
        sql(container, 'SET ROLE milieux_prestations; ' + build_delete(uid, version(container, uid)))
        assert not version(container, uid)
        assert photo.read_text(encoding='utf-8').startswith('La suppression SQL')
        gone = sql(container, 'SET ROLE milieux_prestations; ' +
                   build_delete(uid, before), check=False)
        assert gone.returncode != 0 and 'SIG_PRESTATIONS_NOT_FOUND' in gone.stderr
        zone_id = insert(container, data, 'vegetation', zone)
        assert sql(container, f"SELECT geom IS NULL FROM gemapi.prestations WHERE id='{zone_id}'").stdout.strip() == 't'
        sql(container, 'SET ROLE milieux_patrimoine; ' + build_delete(zone_id, version(container, zone_id)))
        assert not version(container, zone_id)
        assert sql(container, "SELECT (SELECT count(*) FROM gemapi.ah_stockage),"
            "(SELECT count(*) FROM gemapi.ah),"
            "(SELECT count(*) FROM gemapi.vegetation),"
            "(SELECT count(*) FROM gemapi.sites_terrestres),"
            "(SELECT count(*) FROM gemapi.prestataires),"
            "(SELECT count(*) FROM gemapi.techniciens)").stdout.strip() == '1|1|1|1|1|1'
        concurrent_id = insert(container, data, 'ah_stockage', storage)
        stale = version(container, concurrent_id)
        hold_sql = (f"BEGIN; UPDATE gemapi.prestations SET description='Autre session' "
                    f"WHERE id='{concurrent_id}'; SELECT 'LOCKED'; SELECT pg_sleep(5); COMMIT;")
        holding = subprocess.Popen(['docker', 'exec', '-i', container, 'psql', '-X', '-A', '-t',
                                    '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'postgres'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding='utf-8')
        holding.stdin.write(hold_sql)
        holding.stdin.close()
        assert any(holding.stdout.readline().strip() == 'LOCKED' for _ in range(4))
        blocked = sql(container, 'SET ROLE milieux_prestations; ' +
                      build_delete(concurrent_id, stale), check=False)
        assert blocked.returncode != 0 and 'SIG_PRESTATIONS_CONFLICT' in blocked.stderr
        assert holding.wait(timeout=15) == 0
        assert version(container, concurrent_id) != stale
        sql(container, 'SET ROLE milieux_prestations; ' +
            build_delete(concurrent_id, version(container, concurrent_id)))
        print('PostGIS jetable : droits, conflit xmin, sessions concurrentes, photos et parents préservés')
    finally:
        command('docker', 'stop', container, check=False)


if __name__ == '__main__':
    main()
