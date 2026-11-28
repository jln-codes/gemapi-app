"""LOC-03 shared metric search, Qt controls and temporary map reference.

Run offscreen with QGIS Python. SIG_PRESTATIONS_TEST_DSN optionally exercises
the exact production SQL in an already initialized disposable local PostGIS DB.
Without it, only the SQL preselection is simulated with planar GEOS distance.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

from qgis.PyQt import sip
from qgis.PyQt.QtCore import QEvent, Qt
from qgis.PyQt.QtGui import QKeyEvent
from qgis.PyQt.QtWidgets import QMainWindow
from qgis.core import (QgsApplication, QgsCoordinateReferenceSystem, QgsFeature,
                       QgsGeometry, QgsPointXY, QgsProject, QgsRectangle, QgsVectorLayer)
from qgis.gui import QgsMapCanvas, QgsMapToolPan

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.creation import CreationDialog
from gemapi_app.digitize import geometry_from_vertices
from gemapi_app.hydro_groups import search_key
from gemapi_app.patrimony_spatial import candidate_query


def uid(name):
    return str(uuid5(NAMESPACE_URL, "LOC-03/" + name))


FIGURES = (
    ("point", "vegetation", "MultiPoint", "MULTIPOINT((0 0))"),
    ("ligne", "vegetation", "MultiLineString", "MULTILINESTRING((1950 0,2050 0))"),
    ("polygone", "vegetation", "MultiPolygon", "MULTIPOLYGON(((4000 -10,4020 -10,4020 10,4000 10,4000 -10)))"),
    ("riviere", "cours_eau", "MultiLineString", "MULTILINESTRING((5950 0,6050 0))"),
    ("digue", "digues", "LineString", "LINESTRING(5950 0,6050 0)"),
    ("stockage", "ah_stockage", "Polygon", "POLYGON((5990 -10,6010 -10,6010 10,5990 10,5990 -10))"),
    ("ouvrage", "ah_ouvrage", "LineString", "LINESTRING(5990 0,6010 0)"),
    ("site", "sites_terrestres", "MultiPolygon", "MULTIPOLYGON(((-100 -100,6100 -100,6100 100,-100 100,-100 -100)))"),
)


class Form(CreationDialog):
    def _load_types(self): pass
    def _load_reference(self, *_): pass
    def _load_statuses(self): pass
    def _load_technicians(self): pass
    def _load_objects(self, *_): self._filter_objects()
    def _connection(self): return self.test_connection


class SpatialConnection:
    def __init__(self, form, database=None):
        self.form, self.database, self.calls = form, database, []

    def executeSql(self, query):
        geometry = self.form._reference_geometry()
        distance = self.form.distanceSpin.value() * self.form.distanceUnitCombo.currentData()
        assert query == candidate_query(geometry.asWkt(17), distance)
        self.calls.append((geometry.asWkt(), distance))
        if self.database:
            with self.database.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
        rows = []
        for name, family, _, wkt in FIGURES:
            if geometry.distance(QgsGeometry.fromWkt(wkt)) > distance + 1e-9:
                continue
            river = uid("riviere") if family == "digues" else None
            rows.append((family, uid(name), wkt if family in ("cours_eau", "digues") else None,
                         river, 0 if river else None, 1 if river else None, bool(river)))
        return rows


class SpatialFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = tempfile.TemporaryDirectory(prefix="loc03-")
        cls.app = QgsApplication([], True, cls.profile.name)
        cls.app.initQgis()
        cls.database = None
        dsn = os.environ.get("SIG_PRESTATIONS_TEST_DSN")
        if dsn:
            import psycopg2
            cls.database = psycopg2.connect(dsn)
            if cls.database.get_dsn_parameters()["host"] not in ("127.0.0.1", "localhost", "::1"):
                raise ValueError("Only a disposable local test database is allowed")
            with cls.database.cursor() as c:
                c.execute("INSERT INTO gemapi.ah(id,nom) VALUES (%s,'LOC03') ON CONFLICT DO NOTHING", (uid("ah"),))
                for name, family, _, wkt in FIGURES:
                    if family == "digues": continue
                    columns, values = ["id", "nom", "geom"], [uid(name), name, wkt]
                    if family == "cours_eau":
                        columns += ["type_ecoulement", "direction", "source"]
                        values += ["rivière", True, "TEST LOC03"]
                    elif family.startswith("ah_"):
                        columns += ["ah_id"]; values += [uid("ah")]
                    elif family == "vegetation":
                        columns += ["site_terrestre_id"]; values += [uid("site")]
                    # Parent site must precede its zones, all in one transaction.
                    if family == "vegetation": continue
                    params = ["%s", "%s", "ST_GeomFromText(%s,3950)"] + ["%s"]*(len(values)-3)
                    c.execute(f"INSERT INTO gemapi.{family}({','.join(columns)}) VALUES ({','.join(params)}) ON CONFLICT DO NOTHING", values)
                for name, family, _, wkt in FIGURES:
                    if family == "vegetation":
                        c.execute("INSERT INTO gemapi.vegetation(famille_vegetation,id,designation,geometry,site_terrestre_id) VALUES ('ARBRES',%s,%s,ST_GeomFromText(%s,3950),%s) ON CONFLICT DO NOTHING", (uid(name), name, wkt, uid("site")))
                c.execute("INSERT INTO gemapi.digues(id,nom) VALUES (%s,'LOC03') ON CONFLICT DO NOTHING", (uid("digue"),))
                c.execute("INSERT INTO gemapi.digues_reperes(digue_id,riviere_id,rive,debut_fraction,fin_fraction) SELECT %s,%s,'G',0,1 WHERE NOT EXISTS (SELECT 1 FROM gemapi.digues_reperes WHERE digue_id=%s)", (uid("digue"),uid("riviere"),uid("digue")))
            cls.database.commit()

    @classmethod
    def tearDownClass(cls):
        if cls.database: cls.database.close()
        QgsProject.instance().clear()
        cls.app.exitQgis()
        cls.profile.cleanup()

    def setUp(self):
        self.canvas = QgsMapCanvas()
        self.canvas.resize(600, 500)
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3950"))
        self.canvas.setExtent(QgsRectangle(-100, -100, 100, 100))
        self.pan = QgsMapToolPan(self.canvas)
        self.canvas.setMapTool(self.pan)
        self.window = QMainWindow()
        iface = SimpleNamespace(mapCanvas=lambda: self.canvas, mainWindow=lambda: self.window)
        self.form = Form(iface)
        self.connection = SpatialConnection(self.form, self.database)
        self.form.test_connection = self.connection
        self.layers, self.form.objects = [], []
        for name, family, kind, wkt in FIGURES:
            layer = QgsVectorLayer(f"{kind}?crs=EPSG:3950&field=site_terrestre_id:string", name, "memory")
            f = QgsFeature(layer.fields()); f.setAttributes([uid("site")])
            f.setGeometry(QgsGeometry.fromWkt(wkt))
            ok, features = layer.dataProvider().addFeatures([f]); assert ok
            self.layers.append(layer)
            self.form.objects.append((family,(uid(name),),name,(features[0].id(),),search_key(name),layer))
        self.form._filter_objects()

    def tearDown(self):
        self.form._disposing = True
        self.form._stop_map_selection(show_form=False)
        sip.delete(self.form); sip.delete(self.canvas); sip.delete(self.window)

    def proposals(self):
        return sorted(self.form.objectList.item(i).text() for i in range(self.form.objectList.count()))

    def capture(self, wkt, kind="point"):
        self.form._stop_map_selection(show_form=False)
        self.form._capture = SimpleNamespace(kind=kind)
        self.form._capture_finished(QgsGeometry.fromWkt(wkt), "Test")

    def click(self, x, y):
        if self.form._map_tool is None:
            self.form.mapSelectButton.click()
            self.assertFalse(self.form.isVisible())
        self.form._map_tool.canvasReleaseEvent(SimpleNamespace(button=lambda: Qt.LeftButton,
                                                              mapPoint=lambda: QgsPointXY(x,y)))
        self.assertTrue(self.form.nearbyOnly.isChecked())
        self.assertTrue(self.form.nearbyOnly.isEnabled())
        self.assertTrue(self.form.isVisible())

    def test_new_form_and_manual_suspension(self):
        self.assertFalse(self.form.nearbyOnly.isChecked())
        self.assertFalse(self.form.nearbyOnly.isEnabled())
        self.assertEqual(self.form.distanceSpin.value(), 500)
        self.assertEqual(len(self.proposals()), len(FIGURES))
        self.assertFalse(self.connection.calls)
        self.click(0,0)
        self.form.nearbyOnly.setChecked(False)
        self.form.distanceSpin.setValue(5)
        self.assertEqual(len(self.proposals()),len(FIGURES))
        self.assertEqual(self.form.distanceSpin.value(), 5)
        self.form.nearbyOnly.setChecked(True)
        self.assertEqual(self.connection.calls[-1][1],5)
        self.assertNotIn("ligne",self.proposals())

    def test_metric_matrix_same_in_both_modes(self):
        count = 0
        for name, x in (("point",0),("ligne",2000),("polygone",4010)):
            for radius in (0,5,50,500):
                for gap in (0,5,50,500):
                    # Polygon's upper border is y=10; point/line are at y=0.
                    y=gap+(10 if name=="polygone" else 0)
                    with self.subTest(name=name,radius=radius,gap=gap):
                        self.form.distanceSpin.setValue(radius)
                        self.capture(f"POINT({x} {y})")
                        from_geometry=self.proposals()
                        self.click(x,y)
                        self.assertEqual(self.proposals(),from_geometry)
                        self.assertEqual(name in from_geometry,gap<=radius)
                        self.assertEqual(self.form.selectedList.count(),0)
                        count += 1
        print(f"{count} spatial comparisons: point/line/polygon, 0/5/50/500 m")

    def test_reference_changes_geometry_and_snapshot_preserved(self):
        self.capture("LINESTRING(1950 0,2050 0)","line")
        self.form.distanceSpin.setValue(0)
        before=self.form.geometry.asWkt(); snapshot=self.form._snapshot()
        self.click(0,0)
        self.assertEqual(self.form.geometry.asWkt(),before)
        self.assertEqual(self.form._snapshot(),snapshot)
        self.assertIn("point",self.proposals());self.assertNotIn("ligne",self.proposals())
        self.click(2000,0)
        self.assertIn("ligne",self.proposals());self.assertNotIn("point",self.proposals())
        self.form.nearbyOnly.setChecked(False)
        self.capture("POLYGON((3990 -20,4030 -20,4030 20,3990 20,3990 -20))","polygon")
        self.assertIsNone(self.form._map_reference)
        self.assertTrue(self.form.nearbyOnly.isChecked())
        self.assertIn("polygone",self.proposals())
        self.form.nearbyOnly.setChecked(False)
        self.form._reset()
        self.assertIsNone(self.form._map_reference)
        self.assertFalse(self.form.nearbyOnly.isEnabled())
        self.assertEqual(self.form.distanceSpin.value(),500)

    def test_crs_and_zoom_independence(self):
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        expected=geometry_from_vertices("point",[QgsPointXY(2.3,48.8)],self.canvas.mapSettings().destinationCrs())
        self.click(2.3,48.8)
        self.assertTrue(self.form._map_reference.equals(expected))
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3950"))
        for extent in (QgsRectangle(-1,-1,1,1),QgsRectangle(-10000,-10000,10000,10000)):
            self.canvas.setExtent(extent);self.click(0,50)
            self.form.distanceSpin.setValue(50)
            self.assertIn("point",self.proposals())

    def test_hydro_text_family_and_single_attachment(self):
        self.click(6000,0);self.form.distanceSpin.setValue(0)
        self.assertIn("digue",self.proposals());self.assertNotIn("riviere",self.proposals())
        self.form.searchEdit.setText("stock")
        self.assertEqual(self.proposals(),["stockage"])
        self.form.searchEdit.clear()
        self.form._add_selection("ah_stockage",(uid("stockage"),),"stockage")
        self.form._filter_objects();self.assertEqual(self.proposals(),["stockage"])
        self.form.objectList.item(0).setSelected(True)
        self.assertFalse(self.form.addButton.isEnabled())

    def test_map_tool_stop_cancel_and_capture_cancel(self):
        self.click(0,0)
        reference=self.form._map_reference.asWkt()
        self.form._map_tool.keyPressEvent(QKeyEvent(QEvent.KeyPress,Qt.Key_Escape,Qt.NoModifier))
        self.assertIs(self.canvas.mapTool(),self.pan)
        self.assertEqual(self.form._map_reference.asWkt(),reference)
        self.assertTrue(self.form.nearbyOnly.isChecked())
        self.form._begin_capture("point")
        self.form.cancel_capture()
        self.assertEqual(self.form._map_reference.asWkt(),reference)
        self.assertTrue(self.form.nearbyOnly.isChecked())
        self.form.nearbyOnly.setChecked(False)
        self.form._begin_capture("point");self.form.cancel_capture()
        self.assertFalse(self.form.nearbyOnly.isChecked())
        self.assertEqual(self.form._map_reference.asWkt(),reference)
        self.form.mapSelectButton.click()
        replacement=QgsMapToolPan(self.canvas);self.canvas.setMapTool(replacement)
        self.assertIsNone(self.form._map_tool)
        self.assertFalse(self.form.mapSelectButton.isChecked())

    def test_child_preserves_own_geometry(self):
        self.capture("POINT(0 0)")
        self.form._add_selection("vegetation",(uid("point"),),"point")
        self.form._update_geometry_status()
        self.assertIsNotNone(self.form.geometry)
        self.assertIsNone(self.form._geometry_error())
        self.assertTrue(self.form.saveButton.isEnabled())
        self.form._remove_geometry();self.assertIsNone(self.form._geometry_error())
        self.click(0,0);self.assertIsNone(self.form.geometry)
        self.assertIn("point",self.proposals())

    def test_multipart_restriction_and_geometry_edit(self):
        self.capture("MULTIPOINT((0 0),(2000 0))")
        self.click(0,0)
        self.assertIn("point",self.proposals())
        self.form.nearbyOnly.setChecked(False)
        self.form._remove_last_part()
        self.assertIsNone(self.form._map_reference)
        self.assertTrue(self.form.nearbyOnly.isChecked())


if __name__ == "__main__":
    unittest.main()
