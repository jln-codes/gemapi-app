"""CARTO-03: use real QGIS mouse events and the project's snapping settings."""

import sys
import gc
from pathlib import Path

from qgis.PyQt.QtCore import QEvent, QPoint, Qt
from qgis.core import (Qgis, QgsApplication, QgsCoordinateReferenceSystem,
                       QgsCoordinateTransform, QgsFeature, QgsGeometry,
                       QgsPointXY, QgsProject, QgsRectangle,
                       QgsSnappingConfig, QgsVectorLayer)
from qgis.gui import QgsMapCanvas, QgsMapMouseEvent, QgsMapToolPan

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.digitize import GeometryCapture  # noqa: E402


def close_to(point, x, y, tolerance=0.25):
    assert abs(point.x() - x) <= tolerance and abs(point.y() - y) <= tolerance, point


def main():
    app = QgsApplication([], True)
    app.initQgis()
    project = QgsProject.instance()
    crs = QgsCoordinateReferenceSystem("EPSG:3950")
    project.setCrs(crs)
    canvas = QgsMapCanvas()
    canvas.setDestinationCrs(crs)
    canvas.resize(500, 500)
    canvas.setExtent(QgsRectangle(-50, -50, 50, 50))
    canvas.show()

    def add_layer(name, kind, wkt):
        layer = QgsVectorLayer(f"{kind}?crs=EPSG:3950", name, "memory")
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        assert layer.dataProvider().addFeatures([feature])[0]
        layer.updateExtents()
        project.addMapLayer(layer)
        return layer

    fosse = add_layer("Fossé", "LineString", "LINESTRING(0 0,10 0)")
    riviere = add_layer("Rivière", "LineString", "LINESTRING(-20 20,20 20)")
    zec = add_layer("ZEC", "Polygon", "POLYGON((30 -10,40 -10,40 10,30 10,30 -10))")
    canvas.setLayers([fosse, riviere, zec])
    previous = QgsMapToolPan(canvas)
    canvas.setMapTool(previous)
    app.processEvents()

    def configure(enabled=True, layers=()):
        config = project.snappingConfig()
        config.setEnabled(enabled)
        config.setMode(Qgis.SnappingMode.AdvancedConfiguration)
        config.clearIndividualLayerSettings()
        for layer, snap_type in layers:
            config.setIndividualLayerSettings(layer,
                QgsSnappingConfig.IndividualLayerSettings(
                    True, Qgis.SnappingTypes(snap_type), 12,
                    Qgis.MapToolUnit.Pixels))
        project.setSnappingConfig(config)
        # A standalone canvas has no QGIS main-window project synchronizer.
        canvas.snappingUtils().setConfig(config)
        return config

    def mouse(x, y, kind=QEvent.MouseMove, button=Qt.NoButton):
        pixel = canvas.mapSettings().mapToPixel().transform(x, y)
        return QgsMapMouseEvent(canvas, kind, QPoint(round(pixel.x()), round(pixel.y())),
                                button)

    def capture(kind):
        results = []
        session = GeometryCapture(canvas, kind,
                                  lambda geometry, message: results.append((geometry, message)))
        session.start()
        assert canvas.mapTool() is session.tool
        return session, results

    # A vertex of a ditch is used for both preview and stored point.
    original = configure(layers=[(fosse, Qgis.SnappingType.Vertex)])
    point, results = capture("point")
    move = mouse(0.7, 0.5)
    point.tool.canvasMoveEvent(move)
    assert point.tool._snap_marker.isVisible()
    close_to(point.tool._snap_marker.center(), 0, 0)
    close_to(point.tool._vertices_preview.asGeometry().asPoint(), 0, 0)
    point.tool.canvasReleaseEvent(mouse(0.7, 0.5, QEvent.MouseButtonRelease, Qt.LeftButton))
    close_to(results[-1][0].asPoint(), 0, 0)
    assert point.tool._snap_marker is None and canvas.mapTool() is previous
    assert project.snappingConfig() == original

    # A river segment and ZEC boundary are snapped at their projected positions.
    original = configure(layers=[(riviere, Qgis.SnappingType.Segment)])
    line, results = capture("line")
    line.tool.canvasReleaseEvent(mouse(-5, 0, QEvent.MouseButtonRelease, Qt.LeftButton))
    line.tool.canvasMoveEvent(mouse(3, 20.6))
    assert line.tool._snap_marker.isVisible()
    close_to(line.tool._snap_marker.center(), 3, 20)
    close_to(line.tool._preview.asGeometry().asPolyline()[-1], 3, 20)
    line.tool.canvasReleaseEvent(mouse(3, 20.6, QEvent.MouseButtonRelease, Qt.LeftButton))
    preview = line.tool._preview.asGeometry().asWkt()
    line.tool.canvasReleaseEvent(mouse(3, 20.6, QEvent.MouseButtonRelease, Qt.RightButton))
    assert results[-1][0].asWkt() == preview, (results[-1][0].asWkt(), preview)
    assert project.snappingConfig() == original

    original = configure(layers=[(zec, Qgis.SnappingType.Segment)])
    polygon, results = capture("polygon")
    polygon.tool.canvasReleaseEvent(mouse(10, -5, QEvent.MouseButtonRelease, Qt.LeftButton))
    polygon.tool.canvasReleaseEvent(mouse(20, -5, QEvent.MouseButtonRelease, Qt.LeftButton))
    polygon.tool.canvasMoveEvent(mouse(30.6, 5))
    assert polygon.tool._snap_marker.isVisible()
    close_to(polygon.tool._snap_marker.center(), 30, 5)
    polygon.tool.canvasReleaseEvent(mouse(30.6, 5, QEvent.MouseButtonRelease, Qt.LeftButton))
    preview = polygon.tool._preview.asGeometry()
    polygon.tool.canvasReleaseEvent(mouse(30.6, 5, QEvent.MouseButtonRelease, Qt.RightButton))
    assert results[-1][0].asPolygon()[0] == preview.asMultiPolygon()[0][0]
    assert project.snappingConfig() == original

    # A layer omitted from the project settings cannot attract the cursor.
    configure(layers=[(fosse, Qgis.SnappingType.Vertex)])
    limited, results = capture("point")
    limited.tool.canvasMoveEvent(mouse(3, 20.6))
    assert not limited.tool._snap_marker.isVisible()
    limited.tool.canvasReleaseEvent(mouse(3, 20.6, QEvent.MouseButtonRelease, Qt.LeftButton))
    assert abs(results[-1][0].asPoint().y() - 20) > 0.25

    # Disabled snapping leaves the actual map coordinates free.
    original = configure(enabled=False, layers=[(fosse, Qgis.SnappingType.Vertex)])
    free, results = capture("point")
    free.tool.canvasMoveEvent(mouse(0.7, 0.5))
    assert not free.tool._snap_marker.isVisible()
    free.tool.canvasReleaseEvent(mouse(0.7, 0.5, QEvent.MouseButtonRelease, Qt.LeftButton))
    assert results[-1][0].asPoint().distance(QgsPointXY(0, 0)) > 0.5
    assert project.snappingConfig() == original

    # Cancel and external tool changes clear the indicator without changing config.
    configure(layers=[(fosse, Qgis.SnappingType.Vertex)])
    cancelled, results = capture("line")
    cancelled.tool.canvasMoveEvent(mouse(0.7, 0.5))
    assert cancelled.tool._snap_marker.isVisible()
    cancelled.cancel()
    assert results[-1][0] is None and canvas.mapTool() is previous
    assert cancelled.tool._snap_marker is None

    # Snapped map coordinates are transformed to EPSG:3950 before validation.
    geographic = QgsCoordinateReferenceSystem("EPSG:4326")
    target = QgsCoordinateTransform(geographic, crs, project).transform(QgsPointXY(2.3, 48.8))
    reference = add_layer("Repère projeté", "Point",
                          f"POINT({target.x()} {target.y()})")
    canvas.setDestinationCrs(geographic)
    canvas.setExtent(QgsRectangle(2.29, 48.79, 2.31, 48.81))
    canvas.setLayers([reference])
    app.processEvents()
    original = configure(layers=[(reference, Qgis.SnappingType.Vertex)])
    projected, results = capture("point")
    projected.tool.canvasMoveEvent(mouse(2.30005, 48.80005))
    assert projected.tool._snap_marker.isVisible()
    projected.tool.canvasReleaseEvent(mouse(2.30005, 48.80005,
                                            QEvent.MouseButtonRelease, Qt.LeftButton))
    assert results[-1][0].asPoint().distance(target) < 0.05
    assert project.snappingConfig() == original

    canvas.setLayers([])
    canvas.close()
    app.processEvents()
    project.clear()
    app.processEvents()
    del point, line, polygon, limited, free, cancelled, projected, previous
    del fosse, riviere, zec, reference, canvas
    gc.collect()
    app.exitQgis()
    print("CARTO-03 : sommets et segments accrochés, aperçu, CRS, couches ciblées et configuration inchangée OK")


if __name__ == "__main__":
    main()
