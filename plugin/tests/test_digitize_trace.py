"""Trace existing geometry with QGIS's canvas tracer, without editing a layer."""

import gc
import sys
from pathlib import Path

from qgis.PyQt.QtCore import QEvent, QPoint, Qt, QCoreApplication
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (Qgis, QgsApplication, QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform, QgsFeature, QgsGeometry,
                       QgsPointXY, QgsProject, QgsRectangle, QgsSnappingConfig,
                       QgsVectorLayer)
from qgis.gui import QgsMapCanvas, QgsMapCanvasTracer, QgsMapMouseEvent, QgsMapToolPan

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.digitize import GeometryCapture  # noqa: E402


def near(point, x, y, tolerance=0.25):
    assert abs(point.x() - x) < tolerance and abs(point.y() - y) < tolerance, point


def main():
    app = QgsApplication([], True)
    app.initQgis()
    project = QgsProject.instance()
    target = QgsCoordinateReferenceSystem('EPSG:3950')
    project.setCrs(target)
    canvas = QgsMapCanvas()
    canvas.setDestinationCrs(target)
    canvas.resize(800, 600)
    canvas.setExtent(QgsRectangle(-20, -20, 100, 80))
    canvas.show()
    previous = QgsMapToolPan(canvas)
    canvas.setMapTool(previous)
    tracer = QgsMapCanvasTracer(canvas)
    trace_action = QAction('Tracer', canvas)
    trace_action.setCheckable(True)
    tracer.setActionEnableTracing(trace_action)
    snapping_action = QAction('Accrocher', canvas)
    snapping_action.setCheckable(True)
    snapping_action.setChecked(True)
    tracer.setActionEnableSnapping(snapping_action)

    def layer(name, family, wkts):
        result = QgsVectorLayer(f'{family}?crs=EPSG:3950', name, 'memory')
        features = []
        for wkt in wkts:
            feature = QgsFeature(result.fields())
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            features.append(feature)
        assert result.dataProvider().addFeatures(features)[0]
        result.updateExtents()
        project.addMapLayer(result)
        return result

    winding = layer('Winding', 'LineString', ['LINESTRING(0 0,10 0,10 10,20 10)'])
    contour = layer('Contour', 'Polygon', [
        'POLYGON((40 0,50 0,60 0,60 10,60 20,50 20,40 20,40 10,40 0))'])
    connected = layer('Connected', 'LineString', [
        'LINESTRING(0 30,10 30,20 30)', 'LINESTRING(20 30,20 40,30 40)'])
    disconnected = layer('Disconnected', 'LineString', [
        'LINESTRING(0 50,10 50)', 'LINESTRING(20 50,30 50)'])
    network = layer('Network', 'LineString', [
        'LINESTRING(40 30,50 30,60 30)', 'LINESTRING(40 30,40 40,50 40,60 40)',
        'LINESTRING(60 30,60 40)'])
    cross_a = layer('Cross A', 'LineString', ['LINESTRING(70 0,75 0,80 0)'])
    cross_b = layer('Cross B', 'LineString', ['LINESTRING(80 0,80 10,90 10)'])

    def configure(layers):
        canvas.setLayers(layers)
        config = project.snappingConfig()
        config.setEnabled(True)
        config.setMode(Qgis.SnappingMode.AdvancedConfiguration)
        config.clearIndividualLayerSettings()
        for item in layers:
            config.setIndividualLayerSettings(item,
                QgsSnappingConfig.IndividualLayerSettings(
                    True, Qgis.SnappingTypes(Qgis.SnappingType.Vertex |
                                              Qgis.SnappingType.Segment),
                    12, Qgis.MapToolUnit.Pixels))
        project.setSnappingConfig(config)
        canvas.snappingUtils().setConfig(config)
        app.processEvents()

    def mouse(x, y, kind=QEvent.MouseButtonRelease, button=Qt.LeftButton):
        pixel = canvas.mapSettings().mapToPixel().transform(x, y)
        return QgsMapMouseEvent(canvas, kind, QPoint(round(pixel.x()), round(pixel.y())), button)

    def capture(kind):
        outcomes = []
        session = GeometryCapture(canvas, kind,
                                  lambda geometry, message: outcomes.append((geometry, message)))
        session.start()
        assert canvas.mapTool() is session.tool
        return session, outcomes

    def click(session, x, y):
        session.tool.canvasReleaseEvent(mouse(x, y))

    def finish(session, outcomes):
        session.tool.canvasReleaseEvent(mouse(0, 0, button=Qt.RightButton))
        assert outcomes and outcomes[-1][0] is not None, outcomes
        assert canvas.mapTool() is previous
        return outcomes[-1][0]

    # Disabled tracing preserves the exact two-click straight segment.
    configure([winding])
    trace_action.setChecked(False)
    manual, outcomes = capture('line')
    click(manual, 0, 0)
    manual.tool.canvasMoveEvent(mouse(20, 10, QEvent.MouseMove, Qt.NoButton))
    assert len(manual.tool._preview.asGeometry().asPolyline()) == 2
    click(manual, 20, 10)
    assert len(finish(manual, outcomes).asPolyline()) == 2

    # Enabling trace reproduces every intermediate vertex in preview and result.
    trace_action.setChecked(True)
    traced, outcomes = capture('line')
    click(traced, 0, 0)
    traced.tool.canvasMoveEvent(mouse(20, 10, QEvent.MouseMove, Qt.NoButton))
    preview = traced.tool._preview.asGeometry().asPolyline()
    assert len(preview) == 4, preview
    near(preview[1], 10, 0); near(preview[2], 10, 10)
    click(traced, 20, 10)
    recorded = finish(traced, outcomes).asPolyline()
    assert recorded == preview, (recorded, preview)
    assert len(recorded) == 4

    # Segment snapping can start and end between the reference vertices.
    middle, outcomes = capture('line')
    click(middle, 5, 0)
    middle.tool.canvasMoveEvent(mouse(15, 10, QEvent.MouseMove, Qt.NoButton))
    assert len(middle.tool._preview.asGeometry().asPolyline()) == 4
    click(middle, 15, 10)
    middle_result = finish(middle, outcomes).asPolyline()
    assert len(middle_result) == 4
    near(middle_result[1], 10, 0); near(middle_result[2], 10, 10)

    point, outcomes = capture('point')
    click(point, 0, 0)
    assert outcomes[-1][0].asPoint() == QgsPointXY(0, 0)
    assert canvas.mapTool() is previous

    # A polygon border contributes intermediate corners to the final ring.
    configure([contour])
    polygon, outcomes = capture('polygon')
    click(polygon, 40, 0)
    polygon.tool.canvasMoveEvent(mouse(60, 10, QEvent.MouseMove, Qt.NoButton))
    click(polygon, 60, 10)
    assert len(polygon.tool.vertices) >= 4, polygon.tool.vertices
    polygon.tool.canvasMoveEvent(mouse(40, 20, QEvent.MouseMove, Qt.NoButton))
    click(polygon, 40, 20)
    polygon.tool.canvasMoveEvent(mouse(40, 0, QEvent.MouseMove, Qt.NoButton))
    assert len(polygon.tool._preview.asGeometry().asMultiPolygon()[0][0]) == 9
    click(polygon, 40, 0)
    ring = finish(polygon, outcomes).asPolygon()[0]
    assert len(ring) == 9 and ring[0] == ring[-1], ring
    assert any(abs(p.x()-50) < 0.25 and abs(p.y()) < 0.25 for p in ring), ring

    # Connected features in one reference layer form a single route.
    configure([connected])
    trace_action.setChecked(True)
    joined, outcomes = capture('line')
    click(joined, 0, 30)
    joined.tool.canvasMoveEvent(mouse(30, 40, QEvent.MouseMove, Qt.NoButton))
    assert len(joined.tool._preview.asGeometry().asPolyline()) == 5
    click(joined, 30, 40)
    joined_result = finish(joined, outcomes).asPolyline()
    assert len(joined_result) == 5
    near(joined_result[2], 20, 30); near(joined_result[3], 20, 40)

    # QGIS can trace through two connected, enabled reference layers.
    configure([cross_a, cross_b])
    across, outcomes = capture('line')
    click(across, 70, 0)
    across.tool.canvasMoveEvent(mouse(90, 10, QEvent.MouseMove, Qt.NoButton))
    assert len(across.tool._preview.asGeometry().asPolyline()) == 5
    click(across, 90, 10)
    across_result = finish(across, outcomes).asPolyline()
    assert len(across_result) == 5
    near(across_result[2], 80, 0); near(across_result[3], 80, 10)

    # A disconnected snapped endpoint is rejected, while manual capture remains available.
    configure([disconnected])
    rejected, outcomes = capture('line')
    errors = []
    rejected.tool.trace_failed.connect(errors.append)
    click(rejected, 0, 50)
    rejected.tool.canvasMoveEvent(mouse(30, 50, QEvent.MouseMove, Qt.NoButton))
    assert rejected.tool._preview.asGeometry().isNull()
    click(rejected, 30, 50)
    assert len(rejected.tool.vertices) == 1 and errors and 'Aucun chemin' in errors[-1]
    trace_action.setChecked(False)
    click(rejected, 30, 50)
    assert len(finish(rejected, outcomes).asPolyline()) == 2

    # Distinct layers without a shared topological path must not create a line.
    configure([winding, connected])
    trace_action.setChecked(True)
    mixed, outcomes = capture('line')
    errors = []
    mixed.tool.trace_failed.connect(errors.append)
    click(mixed, 0, 0)
    click(mixed, 0, 30)
    assert len(mixed.tool.vertices) == 1
    assert errors and 'Aucun chemin' in errors[-1]
    mixed.cancel()
    assert outcomes[-1][0] is None and canvas.mapTool() is previous

    # An intersection with multiple possible routes shows QGIS's chosen shortest path.
    configure([network])
    trace_action.setChecked(True)
    choice, outcomes = capture('line')
    click(choice, 40, 30)
    choice.tool.canvasMoveEvent(mouse(60, 40, QEvent.MouseMove, Qt.NoButton))
    visible_route = choice.tool._preview.asGeometry().asPolyline()
    assert len(visible_route) >= 3
    click(choice, 60, 40)
    assert finish(choice, outcomes).asPolyline() == visible_route

    # A CRS change uses canvas coordinates for tracing and EPSG:3950 for storage.
    geographic = QgsCoordinateReferenceSystem('EPSG:4326')
    to_geo = QgsCoordinateTransform(target, geographic, project)
    canvas.setDestinationCrs(geographic)
    start = to_geo.transform(QgsPointXY(0, 0))
    end = to_geo.transform(QgsPointXY(20, 10))
    canvas.setExtent(QgsRectangle(min(start.x(), end.x()) - .001,
                                  min(start.y(), end.y()) - .001,
                                  max(start.x(), end.x()) + .001,
                                  max(start.y(), end.y()) + .001))
    configure([winding])
    projected, outcomes = capture('line')
    click(projected, start.x(), start.y())
    projected.tool.canvasMoveEvent(mouse(end.x(), end.y(), QEvent.MouseMove, Qt.NoButton))
    assert len(projected.tool._preview.asGeometry().asPolyline()) == 4
    click(projected, end.x(), end.y())
    projected_result = finish(projected, outcomes).asPolyline()
    assert len(projected_result) == 4
    near(projected_result[1], 10, 0, .5)
    near(projected_result[2], 10, 10, .5)

    # Escape during a trace clears graphics, ignores late events and restores the old tool.
    interrupted, outcomes = capture('line')
    click(interrupted, start.x(), start.y())
    interrupted.tool.canvasMoveEvent(mouse(end.x(), end.y(), QEvent.MouseMove, Qt.NoButton))
    interrupted.cancel()
    assert interrupted.finished and outcomes[-1][0] is None
    assert canvas.mapTool() is previous and interrupted.tool._preview is None
    interrupted.tool.canvasReleaseEvent(object())
    assert len(outcomes) == 1

    canvas.setLayers([])
    canvas.close()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    project.clear()
    del manual, traced, middle, point, polygon, joined, across, rejected, mixed, choice, projected, interrupted
    del winding, contour, connected, disconnected, network, cross_a, cross_b, tracer, canvas, previous
    gc.collect()
    app.exitQgis()
    print('DIGITIZE-TRACE-01 : tracé, aperçu, sommets, échecs, SCR et cycle de vie OK')


if __name__ == '__main__':
    main()
