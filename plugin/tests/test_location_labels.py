"""LOC-LIB-01: display context never changes persisted association UUIDs."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QMainWindow
from qgis.core import QgsApplication, QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer
from qgis.gui import QgsMapCanvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.creation import CreationDialog
from gemapi_app.patrimony_spatial import resolve_candidates
from gemapi_app.record import LINKS, build_insert, build_update
from gemapi_app.watercourse_labels import location_label
from test_record import REQUIRED, OBJECT

RIVER = '11111111-0000-0000-0000-000000000001'
AH = '22222222-0000-0000-0000-000000000001'
DIGUE = '33333333-0000-0000-0000-000000000001'


class Form(CreationDialog):
    def _load_types(self): pass
    def _load_reference(self, *_): pass
    def _load_statuses(self): pass
    def _load_technicians(self): pass
    def _load_objects(self, *_): pass


class LocationLabels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = tempfile.TemporaryDirectory(prefix='loc-lib-')
        cls.app = QgsApplication([], True, cls.profile.name)
        cls.app.initQgis()

    @classmethod
    def tearDownClass(cls):
        QgsProject.instance().clear()
        cls.app.exitQgis()
        cls.profile.cleanup()

    def setUp(self):
        self.canvas = QgsMapCanvas()
        self.window = QMainWindow()
        self.form = Form(SimpleNamespace(mapCanvas=lambda: self.canvas,
                                         mainWindow=lambda: self.window))
        self.layer = QgsVectorLayer('MultiLineString?crs=EPSG:3950&field=id:string&field=nom:string',
                                    'cours_eau', 'memory')
        f = QgsFeature(self.layer.fields())
        f.setAttributes([RIVER, 'Rivière test'])
        f.setGeometry(QgsGeometry.fromWkt('MULTILINESTRING((0 0,100 0))'))
        _, features = self.layer.dataProvider().addFeatures([f])
        self.fid = features[0].id()
        self.form.objects = [('cours_eau', (RIVER,), 'Rivière test', (self.fid,),
                              'riviere test', self.layer)]
        self.form.nearbyOnly.setChecked(False)

    def tearDown(self):
        self.form.shutdown()
        self.form.deleteLater()
        self.canvas.deleteLater()
        self.window.deleteLater()
        self.app.processEvents()

    def row(self):
        self.form._filter_objects()
        self.assertEqual(self.form.objectList.count(), 1)
        return self.form.objectList.item(0)

    def test_course_without_structure(self):
        self.form.geometry = QgsGeometry.fromWkt('POINT(50 0)')
        self.assertEqual(self.row().text(), 'Rivière test')
        self.assertEqual(self.form._associations(), [])

    def test_near_levee_is_only_a_candidate(self):
        self.form.geometry = QgsGeometry.fromWkt('POINT(50 1)')
        self.form.nearbyOnly.setChecked(True)
        allowed = {family: set() for family in LINKS}
        allowed['cours_eau'].add(RIVER)
        allowed['digues'].add(DIGUE)
        with patch.object(self.form, '_spatial_candidates', return_value=allowed):
            self.assertEqual(self.row().text(), 'Rivière test')
        self.assertEqual(self.form._associations(), [])

    def test_section_intersection_and_explicit_course_selection(self):
        self.form.geometry = QgsGeometry.fromWkt('POINT(50 0)')
        row = self.row()
        self.assertEqual(row.text(), 'Rivière test')
        self.assertIn('ne constitue pas un rattachement', row.toolTip())
        family, ids, label, _, _ = row.data(Qt.UserRole)
        before = build_insert(REQUIRED, [(family, ids[0])], 'POINT(50 0)')
        self.form._add_selection(family, ids, label)
        self.assertEqual(self.form._associations(), [('cours_eau', RIVER)])
        self.assertNotIn('AH métier', self.form.selectedList.item(0).text())
        self.assertEqual(build_insert(REQUIRED, self.form._associations(), 'POINT(50 0)'), before)

    def test_multiple_candidates_are_context_not_multiple_links(self):
        allowed, _ = resolve_candidates(QgsGeometry.fromWkt('POINT(50 0)'), [
            ('cours_eau', RIVER, 'LINESTRING(0 0,100 0)', None, None, None, None),
            ('ah_sections', AH, None, RIVER, 0.2, 0.8, True),
            ('digues', DIGUE, None, RIVER, 0.2, 0.8, True),
        ])
        self.assertEqual(allowed['ah_sections'], {AH})
        self.assertEqual(allowed['digues'], {DIGUE})
        self.assertEqual(location_label('Rivière test', ('Digue A', 'AH B', 'Digue A')),
                         'Rivière test (Digue A, AH B)')
        self.assertEqual(self.form._associations(), [])

    def test_existing_levee_uses_same_label_and_uuid_in_edit(self):
        self.form.objects = [('digues', (DIGUE,), 'Rivière test (Digue métier)',
                              (self.fid,), 'riviere test digue metier', self.layer)]
        self.form.mode = 'edit'
        row = [OBJECT, '', None, None, None, '2026-10-29', '2026-10-30', None,
               '', '', '', '', '', '', 'POINT(50 0)', '', '', '', '1', None, '',
               'Indéfini', 'Indéfinie']
        with patch('gemapi_app.creation.load_prestation',
                   return_value=(row, [('digues', DIGUE, 'Digue métier')])):
            self.form.load_existing(None, OBJECT)
        self.assertIn('Rivière test (Digue métier)', self.form.selectedList.item(0).text())
        self.assertEqual(self.form._associations(), [('digues', DIGUE)])
        self.assertIsNone(build_update(OBJECT, '1', REQUIRED, REQUIRED,
                                      [('digues', DIGUE)], self.form._associations(),
                                      'POINT(50 0)', 'POINT(50 0)'))

    def test_uncertain_location_has_no_invented_context(self):
        for wkt in (None, 'POINT(50 5)'):
            self.form.geometry = QgsGeometry.fromWkt(wkt) if wkt else None
            self.assertEqual(self.row().text(), 'Rivière test')
        self.assertEqual(self.form._associations(), [])

    def test_catalogue_uses_reference_course_and_ah_parent_names(self):
        def layer(fields, values=()):
            result = QgsVectorLayer('None?' + '&'.join('field=' + name + ':string' for name in fields),
                                    'fixture', 'memory')
            for attributes in values:
                feature = QgsFeature(result.fields())
                feature.setAttributes(list(attributes))
                result.dataProvider().addFeatures([feature])
            return result
        parent = layer(('id', 'nom'), [(AH, 'AH parent métier')])
        levee = layer(('digue_id', 'digue_nom', 'riviere_id', 'riviere_nom'),
                      [(DIGUE, 'Digue métier', RIVER, 'Rivière test')])
        stock = layer(('id', 'nom', 'ah_id'), [(OBJECT, 'Enfant technique', AH)])
        empty = layer(('id', 'nom', 'ah_id'))
        tables = {'cours_eau': self.layer, 'digues': levee, 'ah_stockage': stock,
                  'ah_ouvrage': empty, 'sites_terrestres': empty}
        connection = SimpleNamespace(executeSql=lambda query: [
            (AH, RIVER, 'AH parent métier', 'LINESTRING(20 0,80 0)')])
        option = SimpleNamespace(ids=(RIVER,), fids=(self.fid,), label='Rivière test',
                                 search='riviere test', named=True)
        with patch.object(self.form, '_connection', return_value=connection), \
             patch.object(self.form, '_canonical_layer', side_effect=lambda table: parent if table == 'ah' else empty), \
             patch.object(self.form, '_object_layer', side_effect=tables.get), \
             patch.object(self.form, '_hydro_options', return_value=(option,)):
            CreationDialog._load_objects(self.form)
        labels = {(family, ids[0]): text for family, ids, text, _, _, _ in self.form.objects}
        self.assertEqual(labels['digues', DIGUE], 'Rivière test (Digue métier)')
        self.assertEqual(labels['ah_stockage', OBJECT], 'AH parent métier — Stockage AH : Enfant technique')
        self.assertEqual(self.form._associations(), [])


if __name__ == '__main__':
    unittest.main()
