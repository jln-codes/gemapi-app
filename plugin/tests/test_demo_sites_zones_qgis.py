"""Render fictitious site zones through a QGIS project copy and disposable PostGIS.

Run: QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_demo_sites_zones_qgis.py
"""

import time
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import ZipFile

from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QColor, QFont, QImage, QPainter
from qgis.PyQt.QtWidgets import QMainWindow
from qgis.core import (QgsApplication, QgsDataSourceUri, QgsGeometry, QgsMapRendererSequentialJob,
                       QgsMapSettings, QgsProject, QgsProviderRegistry, QgsVectorLayer)
from qgis.gui import QgsMapCanvas

from test_postgres_integration import ROOT, command, sql
from gemapi_app.patrimony_spatial import candidate_query
from gemapi_app.report_data import build_report_query, filter_option_queries
from gemapi_app.report_data import prepare_rows
from gemapi_app.report_pdf import export_detailed_report
from gemapi_app.report_synthetic_portrait import export_synthetic_portrait_report
from gemapi_app.creation import CreationDialog


def main():
    container = "sig-sites-zones-" + uuid4().hex[:10]
    command("docker", "run", "--rm", "-d", "--name", container,
            "-p", "127.0.0.1::5432", "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
            "postgis/postgis:16-3.4")
    try:
        for _ in range(60):
            if command("docker", "exec", container, "pg_isready", "-h", "127.0.0.1",
                       "-U", "postgres", check=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("PostGIS de test indisponible")
        sql(container, "CREATE EXTENSION IF NOT EXISTS postgis;")
        sql(container, (ROOT / "model/schema.sql").read_text())
        statements = []
        for source in sorted((ROOT / "demo/data").glob("[0-9][0-9]_*.sql")):
            statements.append(source.read_text())
            if source.name == "11_cours_eau.sql":
                statements.append((ROOT / "demo/data/digues.sql").read_text())
        sql(container, "\n".join(statements))
        assert len(sql(container, filter_option_queries()["sites_zones"]).stdout.splitlines()) == 25
        for kind in ("ST_MultiPoint", "ST_MultiLineString", "ST_MultiPolygon"):
            uid, wkt = sql(container, "SELECT id::text,ST_AsText(geom) FROM milieux.sites_zones "
                           f"WHERE ST_GeometryType(geom)='{kind}' ORDER BY id LIMIT 1").stdout.strip().split("|", 1)
            candidates = sql(container, candidate_query(wkt, 10)).stdout
            assert any(line.startswith("sites_zones|" + uid + "|") for line in candidates.splitlines())
        parent_id = "6fb4c2ae-3be1-5ba1-cc5f-31daadd0c6f4"
        assert sql(container, build_report_query({"site_terrestre": [parent_id]},
                                                count_only=True)).stdout.strip() == "8"
        port = command("docker", "port", container, "5432").stdout.strip().rsplit(":", 1)[-1]

        with ZipFile(ROOT / "demo/prestations_demo.qgz") as archive:
            xml_name = next(name for name in archive.namelist() if name.endswith(".qgs"))
            document = ElementTree.fromstring(archive.read(xml_name))
        for map_layer in document.findall("./projectlayers/maplayer"):
            if map_layer.findtext("provider") != "postgres":
                continue
            source = map_layer.find("datasource")
            uri = QgsDataSourceUri(source.text)
            uri.setConnection("127.0.0.1", port, "postgres", "postgres", "")
            source.text = uri.uri(False)

        app = QgsApplication([], True)
        app.initQgis()
        with TemporaryDirectory() as directory:
            local = Path(directory) / "sites_local.qgs"
            ElementTree.ElementTree(document).write(local, encoding="utf-8", xml_declaration=True)
            project = QgsProject.instance()
            assert project.read(str(local))
            assert len(project.mapLayers()) == 25
            assert all(layer.isValid() for layer in project.mapLayers().values()
                       if layer.providerType() == "postgres")
            layers = {name: next(layer for layer in project.mapLayers().values()
                                 if layer.name() == name)
                      for name in ("sites_zones-points", "sites_zones-lignes", "sites_zones-polygones", "sites_terrestres")}
            assert all(layer.isValid() and layer.crs().authid() == "EPSG:3950"
                       for layer in layers.values())
            assert {name: layers[name].featureCount() for name in
                    ("sites_zones-points", "sites_zones-lignes", "sites_zones-polygones")} == {
                        "sites_zones-points": 4, "sites_zones-lignes": 4, "sites_zones-polygones": 17}
            assert len(project.relationManager().relations()) == 62
            assert all(relation.isValid() for relation in
                       project.relationManager().relations().values())
            nodes = [node for node in project.layerTreeRoot().findLayers()
                     if node.name() in ("sites_zones-points", "sites_zones-lignes", "sites_zones-polygones")]
            assert [node.name() for node in nodes] == ["sites_zones-points", "sites_zones-lignes", "sites_zones-polygones"]
            assert layers["sites_zones-polygones"].renderer().symbol().symbolLayer(0).fillColor().alpha() < 255
            class Interface:
                def __init__(self):
                    self.window = QMainWindow()
                    self.canvas = QgsMapCanvas()

                def mainWindow(self):
                    return self.window

                def mapCanvas(self):
                    return self.canvas

            form = CreationDialog(Interface())
            assert not form._object_load_failures
            assert len([row for row in form.objects if row[0] == "sites_zones"]) == 25
            point = next(layers["sites_zones-points"].getFeatures())
            # Une recherche cartographique propose une zone sans dessiner
            # une géométrie propre, interdite pour ce rattachement.
            form._map_reference = QgsGeometry.fromPointXY(point.geometry().asMultiPoint()[0])
            form.nearbyOnly.setChecked(True)
            form.distanceSpin.setValue(10)
            form._filter_objects()
            assert any(item.data(Qt.UserRole)[0] == "sites_zones" and
                       point["id"] in item.data(Qt.UserRole)[1]
                       for item in (form.objectList.item(i)
                                    for i in range(form.objectList.count())))
            form.shutdown()
            site_layer = layers["sites_terrestres"]
            sites = {feature["nom"]: feature.geometry().boundingBox()
                     for feature in site_layer.getFeatures()}
            canvas = QImage(1600, 650, QImage.Format_ARGB32)
            canvas.fill(QColor("white"))
            painter = QPainter(canvas)
            painter.setPen(QColor("#203d4d"))
            painter.setFont(QFont("Sans Serif", 15))
            rendered_sites = sql(container,"SELECT s.nom FROM milieux.sites_terrestres s JOIN milieux.sites_zones z ON z.site_terrestre_id=s.id GROUP BY s.id,s.nom HAVING count(*)>1 ORDER BY s.id LIMIT 2").stdout.strip().splitlines()
            assert len(rendered_sites)==2
            for index, name in enumerate(rendered_sites):
                settings = QgsMapSettings()
                settings.setDestinationCrs(site_layer.crs())
                settings.setLayers([layers[key] for key in
                                    ("sites_zones-points", "sites_zones-lignes", "sites_zones-polygones", "sites_terrestres")])
                settings.setOutputSize(QSize(780, 580))
                settings.setBackgroundColor(QColor("white"))
                extent = sites[name]
                extent.scale(1.18)
                settings.setExtent(extent)
                job = QgsMapRendererSequentialJob(settings)
                job.start()
                job.waitForFinished()
                painter.drawText(10 + index * 800, 28, name)
                painter.drawImage(10 + index * 800, 45, job.renderedImage())
            painter.end()
            output = ROOT / "audits/demo_sites_zones_02_carte.png"
            output.parent.mkdir(exist_ok=True)
            assert canvas.save(str(output))
            connection_uri = QgsDataSourceUri(layers["sites_zones-polygones"].source())
            connection = QgsProviderRegistry.instance().providerMetadata("postgres").createConnection(
                connection_uri.connectionInfo(False), {})
            selected = prepare_rows(connection.executeSql(build_report_query(
                {"site_terrestre": [parent_id]}, include_geometry=True)))
            assert len(selected) == 8
            basemap = QgsVectorLayer("Polygon?crs=EPSG:2154", "Fond local de contrôle", "memory")
            assert basemap.isValid()
            detailed = ROOT / "audits/demo_sites_zones_02_fiches_controle.pdf"
            synthetic = ROOT / "audits/demo_sites_zones_02_registre_controle.pdf"
            assert export_detailed_report(selected[:1], str(detailed),
                                          _shared_basemap=basemap) == 1
            pages, maps = export_synthetic_portrait_report(
                selected, {"site_terrestre": [parent_id], "groups": ()}, str(synthetic),
                basemap_layer=basemap)
            assert pages >= 1 and maps == 1 and detailed.stat().st_size > 1000
            assert synthetic.stat().st_size > 1000
            project.clear()
        app.exitQgis()
        print("QGIS : trois couches chargées et rendues, 4 points, 4 lignes, 17 polygones")
    finally:
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
