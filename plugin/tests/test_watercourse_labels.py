"""Business names and static QGZ configuration, without a QGIS qualification run."""
import sqlite3
import sys
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as E

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'plugin'))
from gemapi_app.watercourse_labels import label_sql, labels_query_sql, location_label, QGIS_LABEL
from gemapi_app.report_data import filter_option_queries, build_report_query


class WatercourseLabels(unittest.TestCase):
    def test_sql_exposes_business_name_without_replacement(self):
        self.assertEqual(label_sql('c'), 'c.nom')
        self.assertEqual(labels_query_sql(), 'SELECT c.id::text,c.nom FROM milieux.cours_eau c ORDER BY 2,1')
        self.assertEqual(filter_option_queries()['cours_eau'], labels_query_sql())
        self.assertIn('cours_eau_reference_admissible', labels_query_sql(qualifications=True))
        self.assertNotIn('generate_series(0,', build_report_query({}))
        self.assertEqual(location_label('La Lawe', ['ZEC Gosnay1']), 'La Lawe (ZEC Gosnay1)')
        self.assertEqual(QGIS_LABEL, '"nom"')

    def test_sources_only_contain_named_watercourses(self):
        for base, count in (('demo',58),('cabbalr',170)):
            path=ROOT/base/'gpkg/cours_eau.gpkg'
            with sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
                rows=db.execute('SELECT id,nom FROM cours_eau').fetchall()
            self.assertEqual(len(rows),count)
            self.assertTrue(all(name and name.strip() for _,name in rows))
            self.assertEqual(len({uid for uid,_ in rows}),count)

    def test_projects_keep_relations_and_plain_name_expression(self):
        for base in ('demo','cabbalr'):
            with ZipFile(ROOT/base/f'prestations_{base}.qgz') as z:
                root=E.fromstring(next(z.read(n) for n in z.namelist() if n.endswith('.qgs')))
            self.assertEqual(len(root.findall('./relations/relation')),66)
            self.assertEqual(len(root.findall("./projectlayers/maplayer[provider='postgres']")),25)
            expression_fields=[field for field in root.findall('.//expressionfields/field')
                               if field.get('name')=='libelle_cours_eau']
            self.assertTrue(expression_fields)
            self.assertTrue(all(f.get('expression')==QGIS_LABEL for f in expression_fields))

if __name__=='__main__':unittest.main()
