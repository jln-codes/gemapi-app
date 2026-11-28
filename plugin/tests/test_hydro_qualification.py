"""HYDRO-QUAL-01: persistent SQLite triggers, QGIS 3.44 and fresh PostGIS."""
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from qgis.core import QgsApplication, QgsVectorLayer, QgsGeometry, QgsFeature, Qgis
from qgis.PyQt.QtCore import NULL
from test_postgres_integration import ROOT, command, sql

sys.path.insert(0, str(ROOT / 'model'))
from qualifier_cours_eau_gpkg import parts


FILES = ['demo/gpkg/cours_eau.gpkg']


def gpkg_tests():
    app = QgsApplication([], True)
    app.initQgis()
    print('QGIS', Qgis.QGIS_VERSION, flush=True)
    try:
        with tempfile.TemporaryDirectory(dir=ROOT / 'audits') as folder:
            for index, relative in enumerate(FILES):
                source = ROOT / relative
                with sqlite3.connect(source) as db:
                    cols = [c[1] for c in db.execute('PRAGMA table_info(cours_eau)')]
                    rows = db.execute('SELECT * FROM cours_eau ORDER BY fid').fetchall()
                    for row in rows:
                        r = dict(zip(cols, row))
                        assert r['section'] == parts(r['geom'])
                        assert r['valide'] == int(r['direction'] == 1 and r['section'] == 1)
                    dest = Path(folder) / f'{index}.gpkg'
                    with sqlite3.connect(dest) as target:
                        db.backup(target)
                layer = QgsVectorLayer(str(dest) + '|layername=cours_eau', 'test', 'ogr')
                assert layer.isValid()
                fields = layer.fields()
                d, s, v = [fields.indexFromName(n) for n in ('direction','section','valide')]
                feature = next(f for f in layer.getFeatures() if f['section'] == 1)
                fid = feature.id()
                provider = layer.dataProvider()
                inserted = QgsFeature(fields)
                inserted['id'] = str(uuid4())
                inserted['source'] = 'TEST'
                inserted.setGeometry(feature.geometry())
                ok, created = provider.addFeatures([inserted])
                assert ok, provider.lastError()
                with sqlite3.connect(dest) as db:
                    assert db.execute('SELECT direction,section,valide FROM cours_eau WHERE id=?',(str(inserted['id']),)).fetchone() == (None,1,0)
                null_geom = QgsFeature(fields)
                null_geom['id'] = str(uuid4())
                null_geom['source'] = 'TEST'
                null_geom['direction'] = True
                ok, _ = provider.addFeatures([null_geom])
                assert ok, provider.lastError()
                with sqlite3.connect(dest) as db:
                    assert db.execute('SELECT direction,section,valide FROM cours_eau WHERE id=?',(str(null_geom['id']),)).fetchone() == (1,None,0)
                def values():
                    with sqlite3.connect(dest) as db:
                        return db.execute('SELECT direction,section,valide FROM cours_eau WHERE fid=?',(fid,)).fetchone()
                assert provider.changeAttributeValues({fid:{d:True}})
                assert values() == (1,1,1)
                assert provider.changeAttributeValues({fid:{fields.indexFromName('nom'):'Test attributaire'}})
                assert values() == (1,1,1)
                assert provider.changeGeometryValues({fid:feature.geometry()})
                assert values() == (1,1,1)
                shifted = QgsGeometry(feature.geometry())
                shifted.translate(1,0)
                assert provider.changeGeometryValues({fid:shifted})
                assert values() == (None,1,0)
                assert provider.changeAttributeValues({fid:{d:False}})
                assert values() == (0,1,0)
                assert provider.changeAttributeValues({fid:{d:NULL}})
                assert values() == (None,1,0)
                multi = next(f for f in layer.getFeatures() if f['section'] > 1)
                assert provider.changeAttributeValues({multi.id():{d:True}})
                with sqlite3.connect(dest) as db:
                    assert db.execute('SELECT valide FROM cours_eau WHERE fid=?',(multi.id(),)).fetchone()[0] == 0
                assert provider.changeGeometryValues({fid:multi.geometry()})
                assert values() == (None,multi['section'],0)
                layer = None
                print(relative, 'préservation et édition QGIS OK', flush=True)
    finally:
        app.exitQgis()


def postgres_tests():
    container = 'sig-hydro-qual-' + uuid4().hex[:8]
    command('docker','run','--rm','-d','--name',container,'-e','POSTGRES_HOST_AUTH_METHOD=trust','postgis/postgis:16-3.4')
    try:
        for _ in range(60):
            if command('docker','exec',container,'pg_isready','-h','127.0.0.1','-U','postgres',check=False).returncode == 0:
                break
            time.sleep(.5)
        sql(container,'CREATE EXTENSION IF NOT EXISTS postgis;')
        sql(container,(ROOT / 'model/schema.sql').read_text())
        uid = str(uuid4())
        sql(container, f"INSERT INTO gemapi.cours_eau(id,nom,source,geom) VALUES ('{uid}','Support fictif','TEST',ST_GeomFromText('MULTILINESTRING((0 0,1 1))',3950))")
        def state():
            return sql(container,f"SELECT COALESCE(direction::text,'NULL'),section,valide FROM gemapi.cours_eau WHERE id='{uid}'").stdout.strip()
        assert state() == 'NULL|1|f'
        for direction, expected in [('true','true|1|t'),('false','false|1|f'),('NULL','NULL|1|f')]:
            sql(container,f"UPDATE gemapi.cours_eau SET direction={direction} WHERE id='{uid}'")
            assert state() == expected
        sql(container,f"UPDATE gemapi.cours_eau SET direction=true WHERE id='{uid}'; UPDATE gemapi.cours_eau SET nom='attribut',geom=ST_GeomFromWKB(ST_AsBinary(geom),3950) WHERE id='{uid}'")
        assert state() == 'true|1|t'
        sql(container,f"UPDATE gemapi.cours_eau SET geom=ST_GeomFromText('MULTILINESTRING((0 0,2 2),(2 2,3 3))',3950),direction=true WHERE id='{uid}'")
        assert state() == 'NULL|2|f'
        sql(container,f"UPDATE gemapi.cours_eau SET direction=true WHERE id='{uid}'")
        assert state() == 'true|2|f'
        sql(container,f"DELETE FROM gemapi.cours_eau WHERE id='{uid}'")
        sql(container,(ROOT / 'demo/data/11_cours_eau.sql').read_text())
        with sqlite3.connect(ROOT / 'demo/gpkg/cours_eau.gpkg') as db:
            expected = db.execute('SELECT id,section,valide FROM cours_eau ORDER BY id').fetchall()
        actual = sql(container,'SELECT id,section,valide::int FROM gemapi.cours_eau ORDER BY id').stdout.strip().splitlines()
        assert actual == ['|'.join(map(str,r)) for r in expected]
        print('PostgreSQL 16 : qualification, invalidation et import des 58 UUID OK')
    finally:
        command('docker','stop',container,check=False)


if __name__ == '__main__':
    gpkg_tests()
    postgres_tests()
