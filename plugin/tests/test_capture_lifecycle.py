"""Capture shutdown regression on a real QGIS canvas, without database access."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from qgis.PyQt.QtCore import Qt, QEvent, QCoreApplication
from qgis.PyQt.QtGui import QKeyEvent
from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsPointXY
from qgis.gui import QgsMapToolPan

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).parent)]
from gemapi_app.digitize import GeometryCapture
from gemapi_app.creation import CreationDialog
from gemapi_app.plugin import SigMilieuxUX
from test_qgis_runtime import Interface


def mouse(x=0, y=0, button=Qt.LeftButton):
    return SimpleNamespace(mapPoint=lambda: QgsPointXY(x, y), button=lambda: button)


class Form(CreationDialog):
    def _load_types(self): pass
    def _load_reference(self, *_): pass
    def _load_statuses(self): pass
    def _load_technicians(self): pass
    def _load_objects(self, *_): pass
    def _activate_distance(self): pass


class CaptureLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication.instance() or QgsApplication([], True)
        cls.app.initQgis()

    def setUp(self):
        self.iface = Interface()
        self.canvas = self.iface.mapCanvas()
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:3950'))
        self.previous = self.canvas.mapTool()
        self.results = []

    def tearDown(self):
        self.iface.window.close()
        self.canvas.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()

    def capture(self, kind='line'):
        cap = GeometryCapture(self.canvas, kind, lambda *args: self.results.append(args))
        cap.start()
        self.assertIs(self.canvas.mapTool(), cap.tool)
        return cap

    def assert_retired(self, cap, expected_tool):
        self.assertTrue(cap.finished)
        self.assertFalse(cap.active)
        self.assertIs(self.canvas.mapTool(), expected_tool)
        self.assertIsNone(cap.callback)
        for field in ('_snap_marker', '_preview', '_vertices_preview', '_segment_preview'):
            self.assertIsNone(getattr(cap.tool, field))
        before = len(self.results)
        # A sentinel with no event methods proves handlers do not inspect late
        # input or touch a deleted C++ canvas item after termination.
        for _ in range(2):
            cap.tool.canvasMoveEvent(object())
            cap.tool.canvasReleaseEvent(object())
            cap.tool.keyPressEvent(object())
            cap.tool._draw_preview(QgsPointXY(10, 10))
            cap.tool._complete()
            cap.cancel()
            cap.tool.clear_preview()
            cap.start()
        self.assertEqual(len(self.results), before)
        self.assertIs(self.canvas.mapTool(), expected_tool)
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        cap.tool.canvasMoveEvent(object())

    def test_successive_points_lines_polygons_and_finish(self):
        for _ in range(3):
            for kind, points in (('point',[(0,0)]), ('line',[(0,0),(10,0)]),
                                 ('polygon',[(0,0),(10,0),(10,10)])):
                cap = self.capture(kind)
                items = [item for item in (cap.tool._vertices_preview, cap.tool._preview,
                                           cap.tool._segment_preview, cap.tool._snap_marker) if item]
                for x,y in points:
                    cap.tool.canvasMoveEvent(mouse(x,y))
                    cap.tool.canvasReleaseEvent(mouse(x,y))
                if kind != 'point':cap.tool._complete()
                self.assertIsNotNone(self.results[-1][0])
                self.assertTrue(all(item.scene() is None for item in items))
                self.assert_retired(cap, self.previous)
        self.assertEqual(len(self.results), 9)

    def test_escape_and_repeated_cancellation(self):
        cap = self.capture()
        cap.tool.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier))
        self.assertEqual(len(self.results), 1)
        self.assert_retired(cap, self.previous)

    def test_external_tool_change_keeps_replacement(self):
        cap = self.capture()
        other = QgsMapToolPan(self.canvas)
        self.canvas.setMapTool(other)
        self.assertEqual(len(self.results), 1)
        self.assert_retired(cap, other)

    def test_crs_change(self):
        cap = self.capture()
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        self.assertEqual(len(self.results), 1)
        self.assertIn('SCR', self.results[0][1])
        self.assert_retired(cap, self.previous)

    def test_no_previous_tool(self):
        self.canvas.unsetMapTool(self.previous)
        cap = self.capture();cap.cancel()
        self.assert_retired(cap, None)

    def test_overlapping_captures_never_restore_retired_tool(self):
        first = self.capture()
        second = self.capture('point')
        self.assertTrue(first.finished)
        second.cancel()
        self.assert_retired(first, self.previous)
        self.assert_retired(second, self.previous)

    def test_dialog_close_and_plugin_unload(self):
        for how in ('close', 'reject', 'unload'):
            with self.subTest(how=how):
                plugin = SigMilieuxUX(self.iface)
                form = Form(self.iface)
                plugin.creation = form
                form.show();form._begin_capture('line')
                cap = form._capture
                self.assertIsNotNone(cap)
                if how == 'unload':plugin.unload()
                else:
                    form._close_confirmed = True
                    getattr(form,how)()
                    plugin.unload()
                plugin.unload()
                self.assertIsNone(form._capture)
                self.assert_retired(cap, self.previous)

    def test_finish_button_after_multiple_parts(self):
        form = Form(self.iface)
        form._begin_capture('line')
        first = form._capture
        first.tool.canvasReleaseEvent(mouse(0,0))
        first.tool.canvasReleaseEvent(mouse(10,0))
        first.tool._complete()
        form._add_part()
        second = form._capture
        second.tool.canvasReleaseEvent(mouse(20,0))
        second.tool.canvasReleaseEvent(mouse(30,0))
        second.tool._complete()
        self.assertTrue(form.finishGeometryButton.isEnabled())
        geometry = form.geometry.asWkb()
        form.finishGeometryButton.click()
        self.assertFalse(form._geometry_building)
        self.assertEqual(form.geometry.asWkb(), geometry)
        self.assert_retired(first, self.previous)
        self.assert_retired(second, self.previous)
        form.shutdown()

    def test_detach_precedes_graphics_cleanup(self):
        cap = self.capture()
        original = cap.tool.clear_preview
        def checked():
            self.assertIsNot(self.canvas.mapTool(), cap.tool)
            original()
        cap.tool.clear_preview = checked
        cap.cancel()
        self.assert_retired(cap, self.previous)


if __name__ == '__main__':unittest.main(verbosity=2)
