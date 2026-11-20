"""REPORT-AH-01/02: canonical PostGIS, entirely invented data, no remote DSN.

QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_report_ah_integration.py
Add REPORT_AH_PDFS=1 to render detailed/synthetic comparisons in audits/report_ah_02.
"""
import json
import unicodedata
from copy import deepcopy
import os
import time
import unittest
from collections import Counter
from uuid import NAMESPACE_URL, uuid4, uuid5

import psycopg2

from test_postgres_integration import ROOT, command
from gemapi_app.report_data import (ah_recognition_lines, build_management_query,
    build_report_query, grouped_entries, own_totals, prepare_rows, report_warnings)

OUT = ROOT / 'audits/report_ah_02'


def uid(name):
    return str(uuid5(NAMESPACE_URL, 'REPORT-AH-01/' + name))


class ReportAhIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.container = 'sig-report-ah-' + uuid4().hex[:10]
        command('docker', 'run', '--rm', '-d', '--name', cls.container,
                '-p', '127.0.0.1::5432', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
                '-e', 'POSTGRES_DB=seed', 'postgis/postgis:16-3.4')
        cls.addClassCleanup(command, 'docker', 'stop', cls.container, check=False)
        for _ in range(60):
            if command('docker', 'exec', cls.container, 'pg_isready', '-h', '127.0.0.1',
                       '-U', 'postgres', check=False).returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError('PostGIS jetable indisponible')
        cls.port = command('docker', 'port', cls.container, '5432').stdout.strip().rsplit(':', 1)[-1]
        cls.db = psycopg2.connect(host='127.0.0.1', port=cls.port, dbname='postgres', user='postgres')
        cls.addClassCleanup(cls.db.close)
        cls.q('CREATE SCHEMA extensions; CREATE EXTENSION postgis WITH SCHEMA extensions;')
        cls.q((ROOT / 'model/schema.sql').read_text())
        cls.q('SET search_path=pg_catalog,extensions,public')
        cls.q("INSERT INTO milieux.prestataires(id,nom) VALUES (%s,'Entreprise fictive')", (uid('provider'),))
        cls.q("INSERT INTO milieux.techniciens(id,nom) VALUES (%s,'Technicien fictif')", (uid('tech'),))
        for name in ('T1', 'T2'):
            cls.q('INSERT INTO milieux.types_prestations(id,code,libelle,categorie_id) '
                  'SELECT %s,%s,%s,id FROM milieux.prestations_categorie ORDER BY ordre LIMIT 1',
                  (uid(name), name, 'Type fictif ' + name))
        for name in ('A', 'B'):
            cls.q('INSERT INTO milieux.ah(id,nom) VALUES (%s,%s)', (uid(name), 'AH fictif ' + name))
            cls.q("INSERT INTO milieux.ah_stockage(id,ah_id,nom,geom) VALUES (%s,%s,%s,"
                  "ST_Translate(ST_GeomFromText('POLYGON((0 -5,600 -5,600 5,0 5,0 -5))',3950),1700000,9300000))",
                  (uid('S' + name), uid(name), 'Stockage ' + name))
            cls.q("INSERT INTO milieux.ah_ouvrage(id,ah_id,nom,geom) VALUES (%s,%s,%s,"
                  "ST_Translate(ST_GeomFromText('LINESTRING(100 -5,100 5)',3950),1700000,9300000))",
                  (uid('O' + name), uid(name), 'Ouvrage ' + name))
        # R2 shares the same axis deliberately: identity must still be checked.
        for name in ('R', 'R2'):
            cls.q("INSERT INTO milieux.cours_eau(id,nom,type_ecoulement,source,direction,geom) "
                  "VALUES (%s,%s,'rivière','FICTION REPORT-AH-01',true,"
                  "ST_Translate(ST_GeomFromText('MULTILINESTRING((0 0,1000 0))',3950),1700000,9300000))",
                  (uid(name), 'Rivière fictive ' + name))
        for name, parent, start, end in (('s1','A',.1,.3), ('s2','A',.4,.6),
                                        ('s3','B',.2,.5)):
            # The fixture's references must be actual components of storage intersections.
            polygon = ('POLYGON((100 -5,300 -5,300 2,400 2,400 -5,600 -5,600 5,100 5,100 -5))'
                       if parent=='A' else 'POLYGON((200 -5,500 -5,500 5,200 5,200 -5))')
            cls.q('UPDATE milieux.ah_stockage SET geom=ST_Translate(ST_GeomFromText(%s,3950),1700000,9300000) WHERE ah_id=%s',
                  (polygon,uid(parent)))
            cls.q('INSERT INTO milieux.ah_sections(id,ah_id,cours_eau_id,debut_fraction,fin_fraction) '
                  'VALUES (%s,%s,%s,%s,%s)', (uid(name),uid(parent),uid('R'),start,end))
        cls.cases = {
            'P01-stockage': ('ah_stockage_id', 'SA', None, False),
            'P02-ouvrage': ('ah_ouvrage_id', 'OA', None, False),
            'P03-interieur': ('cours_eau_id','R','POINT(150 0)',True),
            'P04-hors': ('cours_eau_id','R','POINT(800 0)',False),
            'P05-deux-sections': ('cours_eau_id','R','LINESTRING(150 0,450 0)',True),
            'P06-deux-AH': ('cours_eau_id','R','POINT(250 0)',True),
            'P07-borne': ('cours_eau_id','R','POINT(100 0)',True),
            'P08-transversale': ('cours_eau_id','R','LINESTRING(250 -10,250 10)',True),
            'P09-tangence': ('cours_eau_id','R','POLYGON((280 0,290 10,270 10,280 0))',True),
            'P10-multipoint': ('cours_eau_id','R','MULTIPOINT((150 0),(800 0))',True),
            'P11-multiligne': ('cours_eau_id','R','MULTILINESTRING((160 -5,160 5),(800 10,810 10))',True),
            'P12-multipolygone': ('cours_eau_id','R','MULTIPOLYGON(((170 0,180 10,160 10,170 0)),((800 10,810 10,810 20,800 10)))',True),
            'P13-autre-riviere': ('cours_eau_id','R2','POINT(250 0)',False),
            'P14-sans-tolerance': ('cours_eau_id','R','POINT(250 0.5)',False),
            'P15-stockage-B': ('ah_stockage_id','SB',None,False),
            'P16-ouvrage-B': ('ah_ouvrage_id','OB',None,False),
            'P17-exterieur-section-A': ('cours_eau_id','R','POINT(350 0)',False),
        }
        for index, (name, (field, target, wkt, _)) in enumerate(cls.cases.items()):
            cls.q(f'INSERT INTO milieux.prestations(id,intitule,type_prestation_id,prestataire_id,'
                  f'technicien_id,statut_id,date_debut,date_fin,quantite,unite,{field},geom) '
                  "SELECT %s,%s,%s,%s,%s,id,'2026-01-02','2026-01-03',%s,'interventions',%s,"
                  "ST_Translate(ST_GeomFromText(%s,3950),1700000,9300000) "
                  "FROM milieux.statuts_prestations WHERE code='TERMINE'",
                  (uid(name),name,uid('T1' if index % 2 else 'T2'),uid('provider'),uid('tech'),index+1,uid(target),wkt))
        cls.db.commit()
        cls.initial = cls.fingerprint()
        cls.db.commit()

    @classmethod
    def q(cls, statement, args=None):
        with cls.db.cursor() as cur:
            cur.execute(statement, args)
            return cur.fetchall() if cur.description else []

    @classmethod
    def fingerprint(cls):
        return {table: cls.q(f"SELECT md5(string_agg(row_to_json(x)::text,',' ORDER BY x.id)) "
                            f'FROM milieux.{table} x')[0][0]
                for table in ('ah','ah_stockage','ah_ouvrage','cours_eau','ah_sections','prestations')}

    def tearDown(self):
        self.db.rollback()
        self.assertEqual(self.fingerprint(), self.initial)
        self.db.rollback()

    def records(self, filters=None):
        return prepare_rows(self.q(build_report_query(filters or {}, include_geometry=True)))

    def names(self, filters=None):
        rows = self.records(filters)
        self.assertEqual(len(rows), len({r['id'] for r in rows}))
        self.assertEqual(len(rows), self.q(build_report_query(filters or {}, count_only=True))[0][0])
        return {r['intitule'] for r in rows}

    def expected_a(self):
        return {n for n, (_, _, _, match) in self.cases.items() if match} | {'P01-stockage','P02-ouvrage'}

    def test_01_exact_intersection_all_allowed_geometry_types(self):
        self.assertEqual(self.names({'ah':[uid('A')]}), self.expected_a())
        # Independent SQL oracle, with no type discriminator or tolerance.
        oracle = self.q("SELECT DISTINCT p.intitule FROM milieux.prestations p "
                        "JOIN milieux.ah_sections_carte s ON s.cours_eau_id=p.cours_eau_id "
                        "WHERE s.ah_id=%s AND s.etat_reference='CONFORME' AND s.cours_eau_qualifie "
                        "AND ST_Intersects(p.geom,s.geom_reference)", (uid('A'),))
        self.assertEqual({r[0] for r in oracle}, self.expected_a()-{'P01-stockage','P02-ouvrage'})
        self.assertEqual(len(self.names()),17)

    def test_02_proofs_direct_relation_and_own_geometry(self):
        rows = {r['intitule']:r for r in self.records({'ah':[uid('A')]})}
        record = rows['P05-deux-sections']
        a = next(p for p in record['parents'] if p['id']==uid('A'))
        self.assertFalse(a['direct'])
        self.assertEqual(set(a['section_ids']), {uid('s1'),uid('s2')})
        self.assertIn('cours_eau',record['objects'])
        self.assertNotIn('AH fictif',record['objects'])
        self.assertEqual(record['reference_count'],1)
        self.assertEqual(len(record['reference_geometries']),1)
        self.assertTrue(record['reference_geometries'][0]['direct'])
        for row in rows.values():
            self.assertEqual(row['own_wkt'],self.q(
                'SELECT ST_AsText(geom) FROM milieux.prestations WHERE id=%s',(row['id'],))[0][0])
        self.assertEqual(record['quantite'],'5')

    def test_03_children_course_and_management_remain_direct(self):
        for field, target, name in (('ah_stockage','SA','P01-stockage'),('ah_ouvrage','OA','P02-ouvrage')):
            self.assertEqual(self.names({field:[uid(target)]}),{name})
        expected = {n for n, (field,target,_,_) in self.cases.items() if field=='cours_eau_id' and target=='R'}
        self.assertEqual(self.names({'cours_eau':[uid('R')]}),expected)
        managed = self.q(build_management_query({'ah':[uid('A')]}))
        self.assertEqual({row[0] for row in managed},{uid('P01-stockage'),uid('P02-ouvrage')})

    def test_04_filters_keep_and_between_families_or_within(self):
        self.assertEqual(self.names({'ah':[uid('A')],'cours_eau':[uid('R')]}),
                         self.expected_a()-{'P01-stockage','P02-ouvrage'})
        self.assertEqual(self.names({'ah':[uid('A')],'ah_stockage':[uid('SB')]}),set())
        self.assertEqual(self.names({'ah_stockage':[uid('SA')],'ah_ouvrage':[uid('OA')]}),set())
        self.assertEqual(self.names({'ah':[uid('A'),uid('B')]}),
                         self.names({'ah':[uid('A')]}) | self.names({'ah':[uid('B')]}))

    def test_05_shared_groups_scoped_and_global_totals(self):
        rows=self.records()
        entries=grouped_entries(rows+rows,('ah',))
        self.assertEqual(len(grouped_entries(rows+rows,())),17)
        self.assertEqual(own_totals(rows),own_totals(rows+rows))
        expected=self.q('SELECT COALESCE(sum(ST_Length(geom)) FILTER (WHERE ST_Dimension(geom)=1),0),'
                        'COALESCE(sum(ST_Area(geom)) FILTER (WHERE ST_Dimension(geom)=2),0) FROM milieux.prestations')[0]
        self.assertEqual(own_totals(rows),tuple(map(float,expected)))
        shared=[r for _,r in entries if r['intitule']=='P06-deux-AH']
        self.assertEqual(len(shared),2)
        self.assertEqual(sum(float(r['quantite']) for r in rows),153)
        self.assertTrue(any('groupes AH' in w for w in report_warnings(rows,{'groups':['ah']})))
        for path,_ in grouped_entries(self.records({'ah':[uid('A')]}),('ah',)):
            self.assertIn(uid('A'),path[0][1])
        self.assertEqual(sum(Counter(r['type'] for r in rows).values()),17)
        selected=self.records({'ah':[uid('A')]})
        self.assertEqual(own_totals(selected),(340,250))
        self.assertEqual(sum(float(r['quantite']) for r in selected),74)
        self.assertEqual(Counter(r['type'] for r in selected),
                         Counter({'Type fictif T1':5,'Type fictif T2':6}))

    def test_06_lost_qualification_excludes_indirect_only(self):
        for direction in (None,False):
            self.q('UPDATE milieux.cours_eau SET direction=%s WHERE id=%s',(direction,uid('R')))
            self.assertEqual(self.names({'ah':[uid('A')]}),{'P01-stockage','P02-ouvrage'})
        self.assertEqual(self.q('SELECT count(*) FROM milieux.ah_sections')[0][0],3)

    def test_07_changed_reference_excluded_without_recalculation(self):
        before=self.q('SELECT id,ST_AsEWKB(geom_reference) FROM milieux.ah_sections ORDER BY id')
        self.q('UPDATE milieux.cours_eau SET geom=ST_Translate(geom,0,1) WHERE id=%s',(uid('R'),))
        self.q('UPDATE milieux.cours_eau SET direction=true WHERE id=%s',(uid('R'),))
        self.assertEqual(self.names({'ah':[uid('A')]}),{'P01-stockage','P02-ouvrage'})
        self.assertEqual(before,self.q('SELECT id,ST_AsEWKB(geom_reference) FROM milieux.ah_sections ORDER BY id'))

    def test_08_attribute_and_identical_geometry_keep_recognition(self):
        self.q("UPDATE milieux.cours_eau SET nom='Nom modifié',geom=geom WHERE id=%s",(uid('R'),))
        self.assertEqual(self.names({'ah':[uid('A')]}),self.expected_a())

    def test_storage_change_keeps_indirect_and_global(self):
        before=self.q('SELECT id,ST_AsEWKB(geom_reference) FROM milieux.ah_sections ORDER BY id')
        self.q('UPDATE milieux.ah_stockage SET geom=ST_Translate(geom,0,1) WHERE ah_id=%s',(uid('A'),))
        self.assertEqual(self.names({'ah':[uid('A')]}),self.expected_a())
        self.assertEqual(len(self.records({})),17)
        self.assertEqual(before,self.q('SELECT id,ST_AsEWKB(geom_reference) FROM milieux.ah_sections ORDER BY id'))
        self.assertTrue(self.names({'ah':[uid('B')]}))

    def test_09_read_only_role_and_snapshot(self):
        self.q('CREATE ROLE report_reader; GRANT USAGE ON SCHEMA milieux,extensions TO report_reader; '
               'GRANT SELECT ON ALL TABLES IN SCHEMA milieux TO report_reader; SET ROLE report_reader')
        self.assertEqual(self.names({'ah':[uid('A')]}),self.expected_a())
        self.q('RESET ROLE')
        self.assertEqual(self.fingerprint(),self.initial)

    @unittest.skipUnless(os.environ.get('REPORT_AH_PDFS')=='1','PDF comparisons requested with REPORT_AH_PDFS=1')
    def test_10_pdf_comparisons(self):
        from qgis.core import QgsApplication, QgsVectorLayer
        OUT.mkdir(parents=True,exist_ok=True)
        os.chdir(OUT)
        app=QgsApplication.instance() or QgsApplication([],True)
        app.initQgis()
        from gemapi_app.report_pdf import export_detailed_report, export_report
        from gemapi_app.report_synthetic_portrait import export_synthetic_portrait_report, terminal_groups, group_layers_and_extent
        from gemapi_app.report_maps import location
        basemap=QgsVectorLayer('Polygon?crs=EPSG:2154','Fond fictif isolé','memory')
        current=self.records({'ah':[uid('A')]})
        direct=[r for r in current if r['intitule'] in {'P01-stockage','P02-ouvrage'}]
        comparisons={}
        for label,rows in (('avant-direct',direct),('apres-indirect',current)):
            detailed=OUT/f'AH-A-{label}-detaille.pdf'
            synthetic=OUT/f'AH-A-{label}-synthetique.pdf'
            export_detailed_report(rows+rows,str(detailed),export_dpi=90,_shared_basemap=basemap)
            export_synthetic_portrait_report(rows,{'ah':[uid('A')],'groups':['ah']},str(synthetic),basemap_layer=basemap)
            text=unicodedata.normalize('NFKC',command('pdftotext','-layout',str(detailed),'-').stdout)
            table=unicodedata.normalize('NFKC',command('pdftotext','-layout',str(synthetic),'-').stdout)
            for row in rows:
                self.assertEqual(text.count(row['intitule']),1)
                self.assertEqual(table.count(row['intitule']),1)
            for name in set(self.cases)-{r['intitule'] for r in rows}:
                self.assertNotIn(name,table)
            self.assertEqual(len([p for p in text.split('\f') if p.strip()]),len(rows))
            for visible in (text,table):
                self.assertNotRegex(visible,r'(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
                self.assertNotIn('cours_eau :',visible)
                self.assertNotIn('Sections justificatives',visible)
            if label=='apres-indirect':
                self.assertIn('reconnaissance indirecte',text)
                self.assertIn('reconnaissance indirecte',table.lower())
                self.assertIn('AH fictif A',text)
                self.assertIn('Rivière fictive R',text)
            comparisons[label]={'uuids':[r['id'] for r in rows], 'n':len(rows),
                                'totals':own_totals(rows), 'quantity':sum(float(r['quantite']) for r in rows)}
        rows=self.records()
        for row in rows:
            if row['own_wkt']:
                self.assertEqual(location(row)[0][0],row['own_wkt'])
                self.assertEqual(len(location(row)),1)
        global_pdf=OUT/'global-AH-synthetique.pdf'
        export_synthetic_portrait_report(rows+rows,{'groups':['ah']},str(global_pdf),basemap_layer=basemap)
        text=unicodedata.normalize('NFKC',command('pdftotext','-layout',str(global_pdf),'-').stdout)
        self.assertIn('17 prestations',text)
        self.assertNotRegex(text,r'(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
        self.assertIn('groupes AH se recouvrent',text)
        for path,members in terminal_groups(rows,{'groups':['ah']}):
            layers,extent=group_layers_and_extent(members)
            self.assertEqual(sum(l.featureCount() for l in layers),len(members))
            self.assertIsNotNone(extent)
        export_report(rows+rows,{},[],report_warnings(rows,{}),str(OUT/'global-tableau.pdf'))
        # A shared prestation with long business names must still fit one A4,
        # retain both AH, and keep its map and two photos in the native template.
        from qgis.core import QgsLayoutItemMap, QgsLayoutItemLabel
        from qgis.PyQt.QtGui import QImage, QColor, QFont
        from gemapi_app.report_pdf import _attachment_lines, _REPORT_FONT_FAMILY
        from qgis.core import QgsLayoutUtils
        long_record=deepcopy(next(r for r in rows if r['intitule']=='P06-deux-AH'))
        long_record['intitule']='P06 — Deux aménagements aux noms longs'
        river_name='La rivière des Prés et des Marais de la Haute Vallée, secteur des anciens moulins et des prairies humides'
        long_record['objects']='cours_eau : '+river_name
        long_names=[
            'Zone d’expansion des crues des Prés et Marais de la Haute Vallée, secteurs des anciens moulins et des prairies humides',
            'Aménagement hydraulique des Basses Terres et du Grand Marais, secteur de la confluence et des anciens pâturages communaux']
        for parent,name in zip((p for p in long_record['parents'] if p['kind']=='ah'),long_names):
            parent['nom']=name
        photo=OUT/'photo-fictive.png'
        image=QImage(600,400,QImage.Format_RGB32);image.fill(QColor('#467c92'))
        self.assertTrue(image.save(str(photo)))
        long_record.update(photo_1=str(photo),photo_2=str(photo),
                           photo_1_commentaire='Photographie fictive A',photo_2_commentaire='Photographie fictive B')
        layouts=[]
        self.assertEqual(export_detailed_report([long_record],str(OUT/'noms-longs-detaille.pdf'),
            include_photos=True,export_dpi=90,_shared_basemap=basemap,_layout_sink=lambda layout,retained,*_:layouts.append((layout,retained))),1)
        self.assertEqual(export_detailed_report([long_record],str(OUT/'noms-longs-detaille.pdf'),
            include_photos=True,export_dpi=90,_shared_basemap=basemap),1)
        long_pdf_text=unicodedata.normalize('NFKC',command('pdftotext','-layout',str(OUT/'noms-longs-detaille.pdf'),'-').stdout)
        normalized=' '.join(long_pdf_text.split())
        for name in [river_name,*long_names]:
            self.assertIn(name,normalized)
        self.assertNotRegex(long_pdf_text,r'(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
        self.assertEqual(long_record['own_wkt'],next(r for r in rows if r['id']==long_record['id'])['own_wkt'])
        maps=[i for i in layouts[0][0].items() if isinstance(i,QgsLayoutItemMap)]
        self.assertEqual(len(maps),1)
        self.assertAlmostEqual(maps[0].sizeWithUnits().width(),190)
        self.assertAlmostEqual(maps[0].sizeWithUnits().height(),73)
        for text in ['Rattachement : '+river_name,*ah_recognition_lines(long_record, explain=True)]:
            for part in _attachment_lines(text):
                self.assertLessEqual(QgsLayoutUtils.textWidthMM(QFont(_REPORT_FONT_FAMILY,7),part),182)
        # Attachment rows end above LOCALISATION; none overlays the map.
        attachment_items=[i for i in layouts[0][0].items() if isinstance(i,QgsLayoutItemLabel)
                          and i.positionWithUnits().x()==14 and i.positionWithUnits().y()>=98]
        self.assertTrue(attachment_items)
        self.assertTrue(all(i.positionWithUnits().y()+i.sizeWithUnits().height()
                            < maps[0].positionWithUnits().y()-5 for i in attachment_items))
        self.assertEqual(export_synthetic_portrait_report([long_record],{'groups':['ah']},
            str(OUT/'noms-longs-synthetique.pdf'),basemap_layer=basemap)[1],2)
        for name in ('global-tableau.pdf','noms-longs-synthetique.pdf'):
            visible=command('pdftotext','-layout',str(OUT/name),'-').stdout
            self.assertNotRegex(visible,r'(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
        photo.unlink()
        comparisons['memberships']=[{k:r[k] for k in ('id','intitule','parents','quantite','unite','own_length','own_area')} for r in rows]
        comparisons['unchanged_fingerprints']=self.initial
        comparisons['global']={'n':17,'quantity':153,'totals':own_totals(rows),
                               'types':dict(Counter(r['type'] for r in rows))}
        (OUT/'comparaisons.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2))
        self.assertEqual(self.fingerprint(),self.initial)
        # QGIS objects intentionally remain alive until process exit.
        self.__class__.app=app


if __name__=='__main__':
    unittest.main(verbosity=2)
