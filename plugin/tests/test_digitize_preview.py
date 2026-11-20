"""Render the plugin's temporary Point/Line/Polygon capture on a QGIS canvas."""

import sys
import gc
from pathlib import Path
from types import SimpleNamespace

from qgis.PyQt.QtCore import Qt, QCoreApplication, QEvent
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsApplication, QgsCoordinateReferenceSystem, QgsPointXY, QgsRectangle
from qgis.gui import QgsMapCanvas, QgsMapToolPan

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.digitize import (  # noqa: E402
    GeometryCapture, POINT_SIZE_MM, POLYGON_FILL_ALPHA, STROKE_WIDTH_MM,
)


def event(x, y, button=None):
    return SimpleNamespace(mapPoint=lambda: QgsPointXY(x, y), button=lambda: button)


def red_pixels(canvas):
    image = canvas.grab().toImage()
    return sum(1 for y in range(image.height()) for x in range(image.width())
               if (lambda color: color.red() > 180 and color.green() < 100
                   and color.blue() < 100)(image.pixelColor(x, y)))


def main():
    app = QgsApplication([], True)
    app.initQgis()
    canvas = QgsMapCanvas()
    canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3950"))
    canvas.setExtent(QgsRectangle(-100, -100, 100, 100))
    canvas.resize(500, 400)
    canvas.show()
    previous = QgsMapToolPan(canvas)
    canvas.setMapTool(previous)
    app.processEvents()
    results = []

    point = GeometryCapture(canvas, "point", lambda geom, message: results.append((geom, message)))
    point.start()
    point_marker = point.tool._vertices_preview
    point.tool.canvasMoveEvent(event(0, 0))
    app.processEvents()
    assert point_marker.strokeColor() == QColor(255, 0, 0)
    assert abs(point_marker.iconSize() - POINT_SIZE_MM * canvas.logicalDpiX() / 25.4) < 1
    assert red_pixels(canvas) > 50, "Le point rouge n'est pas rendu sur le canevas."
    point.tool.canvasReleaseEvent(event(0, 0, Qt.LeftButton))
    assert results[-1][0] is not None and canvas.mapTool() is previous
    assert point_marker.scene() is None

    line = GeometryCapture(canvas, "line", lambda geom, message: results.append((geom, message)))
    line.start()
    line_marker, line_band = line.tool._vertices_preview, line.tool._preview
    line.tool.canvasMoveEvent(event(0, 0))
    app.processEvents()
    assert red_pixels(canvas) > 0, "Le curseur de la ligne n'est pas visible."
    line.tool.canvasReleaseEvent(event(0, 0, Qt.LeftButton))
    line.tool.canvasMoveEvent(event(20, 0))
    app.processEvents()
    assert line_band.asGeometry().length() > 0
    assert line_band.strokeColor() == QColor(255, 0, 0)
    assert abs(line_band.width() - STROKE_WIDTH_MM * canvas.logicalDpiX() / 25.4) < 1
    assert red_pixels(canvas) > 50, "Le segment rouge n'est pas rendu."
    line.tool.canvasReleaseEvent(event(20, 0, Qt.LeftButton))
    line.tool.canvasMoveEvent(event(20, 20))
    assert line_band.asGeometry().length() > 20  # Segment en cours jusqu'au curseur.
    line.tool.canvasReleaseEvent(event(20, 20, Qt.RightButton))
    assert results[-1][0] is not None and canvas.mapTool() is previous
    assert line_band.scene() is None and line_marker.scene() is None

    polygon = GeometryCapture(canvas, "polygon", lambda geom, message: results.append((geom, message)))
    polygon.start()
    poly_marker = polygon.tool._vertices_preview
    poly_band = polygon.tool._preview
    segment_band = polygon.tool._segment_preview
    polygon.tool.canvasReleaseEvent(event(0, 0, Qt.LeftButton))
    polygon.tool.canvasMoveEvent(event(20, 0))
    assert segment_band.asGeometry().length() > 0
    polygon.tool.canvasReleaseEvent(event(20, 0, Qt.LeftButton))
    polygon.tool.canvasMoveEvent(event(20, 20))
    app.processEvents()
    assert poly_band.asGeometry().area() > 0
    assert poly_band.strokeColor() == QColor(255, 0, 0)
    assert poly_band.fillColor().alpha() == POLYGON_FILL_ALPHA
    assert abs(poly_band.width() - STROKE_WIDTH_MM * canvas.logicalDpiX() / 25.4) < 1
    assert red_pixels(canvas) > 50, "Le contour rouge du polygone n'est pas rendu."
    polygon.tool.canvasReleaseEvent(event(20, 20, Qt.LeftButton))
    polygon.tool.canvasReleaseEvent(event(20, 20, Qt.RightButton))
    assert results[-1][0] is not None and canvas.mapTool() is previous
    assert all(band.scene() is None for band in (poly_marker, poly_band, segment_band))

    cancelled = GeometryCapture(canvas, "line", lambda geom, message: results.append((geom, message)))
    cancelled.start()
    cancelled.tool.canvasReleaseEvent(event(0, 0, Qt.LeftButton))
    cancelled.cancel()
    assert results[-1][0] is None and canvas.mapTool() is previous
    assert cancelled.tool._preview is None
    canvas.close()
    # Release SIP-owned canvas items before QApplication/QGIS shutdown.
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    del point, line, polygon, cancelled, previous
    del point_marker, line_marker, line_band, poly_marker, poly_band, segment_band
    del canvas
    gc.collect()
    app.exitQgis()
    print("Prévisualisation PyQGIS : Point/Ligne/Polygone rouges, curseur, sommets et nettoyage OK")


if __name__ == "__main__":
    main()
