"""Current six-mode model in a fresh disposable PostGIS database.

Run with the QGIS Python: /usr/bin/python3 plugin/tests/test_rattachements_model.py
"""
import sys
import os
import time
from math import isclose
from uuid import uuid4
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import psycopg2
from test_postgres_integration import command, sql, ROOT
from gemapi_app.record import build_insert, build_update, FIELDS, LINKS
from gemapi_app.report_data import build_report_query, measure_lines, prepare_rows, normalized_filters


def main():
    container = 'sig-relations-test-' + uuid4().hex[:8]
    command('docker','run','--rm','-d','--name',container,'-p','127.0.0.1::5432',
            '-e','POSTGRES_HOST_AUTH_METHOD=trust','postgis/postgis:16-3.4')
    try:
        for _ in range(60):
            if command('docker','exec',container,'pg_isready','-h','127.0.0.1','-U','postgres',check=False).returncode==0: break
            time.sleep(.5)
        sql(container,'CREATE EXTENSION IF NOT EXISTS postgis;')
        sql(container,(ROOT/'model/schema.sql').read_text())
        for name in ('01_techniciens','03_communes','04_prestataires','05_types_prestations','09_ah','10_sites_terrestres','11_cours_eau','digues'):
            sql(container,(ROOT/f'demo/data/{name}.sql').read_text())
        port=command('docker','port',container,'5432').stdout.strip().rsplit(':',1)[1]
        def connect(): return psycopg2.connect(host='127.0.0.1',port=port,user='postgres',dbname='postgres')
        db=connect()
        def one(query):
            with db.cursor() as c:c.execute(query);return c.fetchone()[0]
        values={k:one(f'SELECT id::text FROM milieux.{t} ORDER BY id LIMIT 1') for k,t in
                (('type_prestation_id','types_prestations'),('prestataire_id','prestataires'),('statut_id','statuts_prestations'),('technicien_id','techniciens'))}
        values.update(date_debut='2026-01-01',date_fin='2026-01-02')
        ids={f:one(f'SELECT id::text FROM milieux.{f} ORDER BY id LIMIT 1') for f in LINKS}
        ids['sites_zones']=one('SELECT id::text FROM milieux.sites_zones WHERE site_terrestre_id IN (SELECT site_terrestre_id FROM milieux.sites_zones GROUP BY site_terrestre_id HAVING count(*)>1) ORDER BY id LIMIT 1')
        db.rollback()
        passed=[]
        def attempt(label,family,geom,accepted,extra=''):
            # Use raw SQL for DB rejection tests so Python validation cannot mask a missing SQL rule.
            cols=['id',*values,'geom'];uid=str(uuid4());params=[f"'{uid}'",*(f"'{v}'" for v in values.values()),'NULL' if geom is None else f"ST_GeomFromText('{geom}',3950)"]
            if family:cols.append(LINKS[family][1]);params.append(f"'{ids[family]}'")
            query=f"INSERT INTO milieux.prestations({','.join(cols)}) VALUES ({','.join(params)});"
            query+=extra.replace('@id',uid)
            try:
                with db.cursor() as c:c.execute(query);c.execute('SET CONSTRAINTS ALL IMMEDIATE')
                result=True
            except psycopg2.Error:result=False
            db.rollback();assert result==accepted,label;passed.append(label)
        for f in LINKS:
            for g in (None,'POINT(0 0)','MULTIPOINT((0 0),(1 1))'):
                accepted = (g is not None or f in ('ah_stockage', 'ah_ouvrage', 'sites_zones'))
                if f == 'sites_terrestres':
                    accepted = g is not None and g.startswith('MULTI')
                elif f == 'sites_zones':
                    accepted = g is None
                attempt(f'{f}/{g}', f, g, accepted)
        attempt('no attachment',None,'POINT(0 0)',False)
        attempt('parent+zone','sites_terrestres','MULTIPOINT((0 0))',False,"UPDATE milieux.prestations SET site_zone_id='"+ids['sites_zones']+"' WHERE id='@id';")
        attempt('two direct modes','cours_eau','POINT(0 0)',False,f"UPDATE milieux.prestations SET digue_id='{ids['digues']}' WHERE id='@id';")
        attempt('last zone removed','sites_zones',None,False,"UPDATE milieux.prestations SET site_zone_id=NULL WHERE id='@id';")
        attempt('position incompatible','sites_terrestres','MULTIPOINT((0 0))',False,"UPDATE milieux.prestations SET position='Crête' WHERE id='@id';")
        attempt('rive incompatible','ah_stockage',None,False,"UPDATE milieux.prestations SET rive='Gauche' WHERE id='@id';")
        # Real plugin insert, read-only reports, atomic replacement, and null own measures.
        with db.cursor() as c:c.execute(build_insert(values,[('ah_stockage',ids['ah_stockage'])]));uid=c.fetchone()[0]
        db.commit()
        with db.cursor() as c:
            c.execute('SELECT xmin::text FROM milieux.prestations WHERE id=%s',(uid,));version=c.fetchone()[0]
            c.execute(build_update(uid,version,values,values,[('ah_stockage',ids['ah_stockage'])],[('ah_ouvrage',ids['ah_ouvrage'])],None,None))
        db.commit();passed.append('atomic replacement via plugin')
        site_id=one(f"SELECT site_terrestre_id::text FROM milieux.sites_zones WHERE id='{ids['sites_zones']}'")
        with db.cursor() as c:
            c.execute(build_insert(values,[('sites_zones',ids['sites_zones'])]));zone_uid=c.fetchone()[0]
        db.commit()
        with db.cursor() as c:
            c.execute('SELECT xmin::text FROM milieux.prestations WHERE id=%s',(zone_uid,));zone_version=c.fetchone()[0]
            c.execute(build_update(zone_uid,zone_version,values,values,
                                   [('sites_zones',ids['sites_zones'])],
                                   [('sites_terrestres',site_id)],None,'MULTIPOINT((0 0))'))
        db.commit()
        with db.cursor() as c:
            c.execute('SELECT xmin::text FROM milieux.prestations WHERE id=%s',(zone_uid,));zone_version=c.fetchone()[0]
            c.execute(build_update(zone_uid,zone_version,values,values,
                                   [('sites_terrestres',site_id)],
                                   [('sites_zones',ids['sites_zones'])],'MULTIPOINT((0 0))',None))
            c.execute('SELECT site_zone_id::text,site_terrestre_id FROM milieux.prestations WHERE id=%s',(zone_uid,))
            assert c.fetchone()==(ids['sites_zones'],None)
        db.commit()
        with db.cursor() as c:c.execute('DELETE FROM milieux.prestations WHERE id=%s',(zone_uid,))
        db.commit();passed.append('zone → site parent → zone via plugin')
        with db.cursor() as c:
            c.execute(build_report_query({},include_geometry=True));rows=prepare_rows(c.fetchall())
            assert len(rows)==1 and not rows[0]['has_geometry'] and rows[0]['own_length'] is None and rows[0]['reference_geometries']
            c.execute('SELECT count(*) FROM milieux.prestations_fiches');assert c.fetchone()[0]==1
            c.execute('SELECT count(*) FROM milieux.prestations__ah');assert c.fetchone()[0]==1
        db.rollback();passed.append('reports, own NULL measures, parent views')
        # Zone localisation is effective geometry, never an own geometry copy.
        for kind in ('ST_MultiPoint','ST_MultiLineString','ST_MultiPolygon'):
            zone=one(f"SELECT id::text FROM milieux.sites_zones WHERE ST_GeometryType(geom)='{kind}' ORDER BY id LIMIT 1")
            with db.cursor() as c:
                c.execute(build_insert({**values,'quantite':'7','unite':'arbres'},[('sites_zones',zone)]))
                test_id=c.fetchone()[0]
                c.execute('SELECT p.geom IS NULL,ST_Equals(v.geom,z.geom),f.possede_geometrie,f.type_geometrie_postgis,p.quantite,p.unite FROM milieux.prestations p JOIN milieux.sites_zones z ON z.id=p.site_zone_id JOIN milieux.prestations_carte v ON v.id=p.id JOIN milieux.prestations_fiches f ON f.id=p.id WHERE p.id=%s',(test_id,))
                assert c.fetchone()==(True,True,True,kind,7,'arbres')
                c.execute(build_report_query({'sites_zones':[zone]},include_geometry=True))
                item=next(r for r in prepare_rows(c.fetchall()) if r['id']==str(test_id))
                assert item['own_wkt'] is None and not item['has_geometry']
                assert len(item['reference_geometries'])==1 and item['reference_geometries'][0]['wkt']
                assert item['quantite']=='7' and item['unite']=='arbres'
                if kind=='ST_MultiPoint':
                    assert item['parent_zone_length'] is item['parent_zone_area'] is None
                    assert measure_lines(item,include_quantity=False)==['Géométrie ponctuelle de la zone']
                else:
                    field,function=('parent_zone_length','ST_Length') if kind=='ST_MultiLineString' else ('parent_zone_area','ST_Area')
                    c.execute(f'SELECT {function}(geom) FROM milieux.sites_zones WHERE id=%s',(zone,))
                    assert isclose(item[field],c.fetchone()[0],rel_tol=1e-12)
                    assert 'géométrie parente' in measure_lines(item,include_quantity=False)[0]
                c.execute('SELECT id::text FROM milieux.communes WHERE ST_Intersects(geom,(SELECT geom FROM milieux.sites_zones WHERE id=%s)) LIMIT 1',(zone,))
                commune=c.fetchone()
                if commune:
                    c.execute(build_report_query({'sites_zones':[zone],'communes':[commune[0]]},include_geometry=True))
                    assert any(r['id']==str(test_id) for r in prepare_rows(c.fetchall()))
                c.execute('DELETE FROM milieux.prestations WHERE id=%s',(test_id,))
            db.commit();passed.append('zone effective geometry, view, report, quantity '+kind)
        # Racing zone-vs-direct writes must fail rather than commit an invalid state.
        for isolation in ('READ COMMITTED','REPEATABLE READ'):
            a,b=connect(),connect();a.set_session(isolation_level=isolation);b.set_session(isolation_level=isolation)
            with b.cursor() as c:c.execute('SELECT count(*) FROM milieux.prestations')
            with a.cursor() as c:c.execute('UPDATE milieux.prestations SET intitule=%s WHERE id=%s',(isolation,uid))
            def race():
                try:
                    with b.cursor() as c:c.execute('SET statement_timeout=5000');c.execute('UPDATE milieux.prestations SET site_zone_id=%s WHERE id=%s',(ids['sites_zones'],uid))
                    b.commit();return False
                except psycopg2.Error:b.rollback();return True
            with ThreadPoolExecutor() as pool:
                future=pool.submit(race);time.sleep(.1);a.commit();assert future.result()
            a.close();b.close();passed.append('concurrent zone/direct '+isolation)
        db.close()
        # Exercise the real shared Qt form and PostgreSQL provider.
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from qgis.core import QgsApplication,QgsProject,QgsDataSourceUri,QgsVectorLayer,QgsWkbTypes,QgsGeometry
        from qgis.PyQt.QtCore import Qt
        from unittest.mock import patch
        from test_photo_ui import Interface
        from gemapi_app.creation import CreationDialog
        app=QgsApplication([],True);app.initQgis();iface=Interface()
        for table,kind in [('prestations',QgsWkbTypes.Point),('sites_zones',QgsWkbTypes.Point),('sites_zones',QgsWkbTypes.LineString),('sites_zones',QgsWkbTypes.Polygon)]:
            uri=QgsDataSourceUri();uri.setConnection('127.0.0.1',port,'postgres','postgres','');uri.setDataSource('milieux',table,'geom','','id');uri.setWkbType(kind);uri.setSrid('3950')
            layer=QgsVectorLayer(uri.uri(False),table,'postgres');assert layer.isValid();QgsProject.instance().addMapLayer(layer)
        dialog=CreationDialog(iface);dialog.show();app.processEvents()
        assert not dialog._object_load_failures
        assert set(obj[0] for obj in dialog.objects)==set(LINKS)
        sites = [obj for obj in dialog.objects if obj[0]=='sites_terrestres']
        zones = [obj for obj in dialog.objects if obj[0]=='sites_zones']
        assert sites and zones
        site_names = {obj[2] for obj in sites}
        assert all(not name.endswith(' — Site terrestre') for name in site_names)
        parent_name = next(name for name in site_names if sum(obj[2].startswith(name+' — ') for obj in zones)>=2)
        matching_zones = [obj for obj in zones if obj[2].startswith(parent_name+' — ')]
        assert len(matching_zones)>=2
        dialog.searchEdit.setText(parent_name)
        visible = [dialog.objectList.item(i).text() for i in range(dialog.objectList.count())]
        assert parent_name in visible and all(obj[2] in visible for obj in matching_zones)
        dialog.searchEdit.setText(matching_zones[0][2].split(' — ',1)[1])
        assert any(dialog.objectList.item(i).text()==matching_zones[0][2] for i in range(dialog.objectList.count()))
        dialog.searchEdit.setText(parent_name)
        if os.environ.get('PATRIMONY_LABEL_SCREENSHOT'):
            dialog.resize(1400, 850)
            app.processEvents()
            dialog.grab().save(os.environ['PATRIMONY_LABEL_SCREENSHOT'])
        dialog._add_selection('sites_terrestres',sites[0][1],sites[0][2])
        assert dialog._associations()==[('sites_terrestres',sites[0][1][0])]
        dialog.selectedList.clear()
        dialog._add_selection('sites_zones',matching_zones[0][1],matching_zones[0][2])
        assert dialog._associations()==[('sites_zones',matching_zones[0][1][0])]
        dialog.selectedList.clear()
        dialog.searchEdit.clear()
        dialog.geometry=QgsGeometry.fromWkt('MULTIPOINT((1 1),(2 2))');dialog.geometry_kind='point';dialog._update_geometry_status();dialog._filter_objects()
        assert all(dialog.objectList.item(i).data(Qt.UserRole)[0]!='sites_zones' for i in range(dialog.objectList.count()))
        zone=next(o for o in dialog.objects if o[0]=='sites_zones')
        dialog._add_selection('sites_zones',zone[1],zone[2]);dialog._update_geometry_status()
        assert dialog.selectedList.count()==1 and dialog._geometry_error() and not dialog.saveButton.isEnabled()
        dialog.selectedList.clear()
        class Candidates:
            def __init__(self,levee=True):self.levee=levee
            def executeSql(self,_):
                return [('cours_eau','r','MULTILINESTRING((0 0,1000 0))',None,None,None,None)]+([('digues','d',None,'r',.2,.4,True)] if self.levee else [])
        for geometry,warning in [('POINT(300 80)',False),('POINT(500 80)',False),('LINESTRING(300 80,500 80)',True)]:
            dialog.geometry=QgsGeometry.fromWkt(geometry);dialog._spatial_cache=None
            with patch.object(dialog,'_connection',return_value=Candidates()):dialog._spatial_candidates(500)
            assert bool(dialog.spatialWarning.text())==warning,(geometry,dialog.spatialWarning.text())
        dialog.geometry=QgsGeometry.fromWkt('POINT(300 80)');dialog._spatial_cache=None
        with patch.object(dialog,'_connection',return_value=Candidates(False)):dialog._spatial_candidates(500000)
        assert not dialog.spatialWarning.text()
        dialog.shutdown()
        edit=CreationDialog(iface,mode='edit');edit.load_existing(edit._connection(),uid)
        assert edit.geometry is None and edit._associations()==[('ah_ouvrage',ids['ah_ouvrage'])]
        assert all(not obj[2].endswith(' — Site terrestre') for obj in edit.objects if obj[0]=='sites_terrestres')
        assert any(obj[2].startswith(parent_name+' — ') for obj in edit.objects if obj[0]=='sites_zones')
        edit.intituleEdit.setText('Édition sans géométrie conservée');edit._save_edit();assert edit._edit_saved
        edit.shutdown();QgsProject.instance().clear();app.exitQgis()
        passed.append('PyQGIS real provider/form, six modes, multigeometry exclusion, retained links, warning crossing only, edit without own geometry')
        print('\n'.join('PASS '+label for label in passed));print(f'{len(passed)} validations réussies')
    finally:command('docker','rm','-f',container,check=False)

if __name__=='__main__':main()
