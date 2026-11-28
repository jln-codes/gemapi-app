"""DIG-02 : projet, symbologie et capture QGIS sur PostGIS jetable.

Exécuter avec le Python de QGIS, QT_QPA_PLATFORM=offscreen et Docker.
La capture est produite à partir de deux digues fictives sur le même intervalle.
"""

import tempfile
import time
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile
from xml.etree import ElementTree as etree

from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from qgis.core import (
    QgsApplication, QgsDataSourceUri, QgsMapRendererSequentialJob,
    QgsMapSettings, QgsProject, QgsRectangle, QgsVectorDataProvider,
)

from test_postgres_integration import ROOT, command, sql


PROJECT_PATH = ROOT / "demo" / "prestations_demo.qgz"
CAPTURE_PATH = ROOT / "audits" / "captures" / "dig02_sections_rives.png"
LAYER_ID = "digues_carte_139241e4_8ec7_4e65_ab4a_90dc6bca849a"


def project_copy(target, port):
    with ZipFile(PROJECT_PATH) as archive:
        assert archive.testzip() is None
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    root = etree.fromstring(next(data for info, data in entries
                                 if info.filename.endswith(".qgs")))
    layers = root.findall("./projectlayers/maplayer")
    assert len(layers) == 33
    sections = next(layer for layer in layers if layer.findtext("id") == LAYER_ID)
    river = next(layer for layer in layers if '"gemapi"."cours_eau"'
                 in layer.findtext("datasource", ""))
    assert sections.get("readOnly") == "1"
    assert sections.findtext("provider") == "postgres"
    assert sections.findtext("layername") == "digues_carte"
    assert '"gemapi"."digues_carte"' in sections.findtext("datasource")
    assert sections.find("renderer-v2").get("type") == "RuleRenderer"
    assert sections.get("hasScaleBasedVisibilityFlag") == "1"
    assert sections.get("minScale") == "75000"
    assert sections.get("labelsEnabled") == "1"
    river_id = river.findtext("id")
    tree = root.find("./layer-tree-group/layer-tree-group[@name='Digues']")
    assert tree is not None
    ids = [node.get("id") for node in tree if node.tag == "layer-tree-layer"]
    assert LAYER_ID in ids
    assert root.find(".//layer-tree-layer[@id='" + river_id + "']") is not None
    assert tree.find("./layer-tree-layer[@id='" + LAYER_ID + "']").get(
        "checked") == "Qt::Checked"
    order = [node.get("id") for node in root.findall("./layerorder/layer")]
    assert LAYER_ID in order and river_id in order
    old_river_style = etree.tostring(river.find("renderer-v2"))

    for layer in layers:
        if layer.findtext("provider") != "postgres":
            continue
        if layer.findtext("id") in (LAYER_ID, river_id):
            source = QgsDataSourceUri(layer.findtext("datasource").replace("service='gemapi_demo'", ""))
            source.setConnection("127.0.0.1", port, "postgres", "dig02_read", "")
            layer.find("datasource").text = source.uri(False)
        else:
            layer.find("datasource").text = "LineString?crs=EPSG:3950"
            layer.find("provider").text = "memory"
    for node in root.findall(".//layer-tree-layer"):
        if node.get("id") not in (LAYER_ID, river_id):
            continue
        source = QgsDataSourceUri(node.get("source").replace("service='gemapi_demo'", ""))
        source.setConnection("127.0.0.1", port, "postgres", "dig02_read", "")
        node.set("source", source.uri(False))
    assert etree.tostring(river.find("renderer-v2")) == old_river_style
    changed = etree.tostring(root, encoding="UTF-8", xml_declaration=False)
    with ZipFile(target, "w") as archive:
        for info, data in entries:
            archive.writestr(info, changed if info.filename.endswith(".qgs") else data)


def map_image(layers, scale):
    settings = QgsMapSettings()
    settings.setLayers(layers)
    settings.setDestinationCrs(layers[0].crs())
    settings.setOutputSize(QSize(1200, 620))
    settings.setOutputDpi(96)
    settings.setBackgroundColor(QColor("white"))
    settings.setFlag(QgsMapSettings.DrawLabeling, True)
    # 1200 pixels at 96 DPI span 0.3175 m on paper.
    width = scale * 0.3175
    height = width * 620 / 1200
    settings.setExtent(QgsRectangle(1675000 - width / 2, 9259000 - height / 2,
                                    1675000 + width / 2, 9259000 + height / 2))
    assert abs(settings.scale() - scale) / scale < 0.02, settings.scale()
    job = QgsMapRendererSequentialJob(settings)
    job.start()
    job.waitForFinished()
    rendered = job.renderedImage()
    result = QImage(rendered.size(), QImage.Format_ARGB32)
    painter = QPainter(result)
    painter.drawImage(0, 0, rendered)
    painter.end()
    return result


def colored_pixels(image, side):
    positions = []
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            if c.red() < 65 and 95 < c.green() < 190 and c.blue() > 140 \
                    and ((side == "G" and y < image.height() / 2 - 2) or
                         (side == "D" and y > image.height() / 2 + 2)):
                positions.append(y)
    return positions


def main():
    container = "sig-prestations-dig02-" + uuid4().hex[:10]
    command("docker", "run", "--rm", "-d", "--name", container,
            "-p", "127.0.0.1::5432", "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
            "postgis/postgis:16-3.4")
    app = None
    try:
        for _ in range(60):
            if command("docker", "exec", container, "pg_isready", "-h", "127.0.0.1",
                       "-U", "postgres", check=False).returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("PostGIS de test indisponible")
        sql(container, "CREATE EXTENSION IF NOT EXISTS postgis;")
        sql(container, (ROOT / "model" / "schema.sql").read_text(encoding="utf-8"))
        digue, digue_droite, river = str(uuid4()), str(uuid4()), str(uuid4())
        sql(container, f"BEGIN; INSERT INTO gemapi.digues(id,nom) VALUES ('{digue}',"
                       "'Digue de démonstration'); "
                       f"INSERT INTO gemapi.digues(id,nom) VALUES ('{digue_droite}',"
                       "'Digue de démonstration — rive droite'); "
                       f"INSERT INTO gemapi.cours_eau(id,nom,source,direction,geom) VALUES ('{river}',"
                       "'Rivière de démonstration','TEST',TRUE,"
                       "ST_Multi(ST_GeomFromText('LINESTRING(1674500 9259000,1675500 9259000)',3950))); "
                       "INSERT INTO gemapi.digues_reperes "
                       "(digue_id,riviere_id,rive,debut_fraction,fin_fraction) "
                       f"VALUES ('{digue}','{river}','G',0.2,0.8),"
                       f"('{digue_droite}','{river}','D',0.2,0.8); COMMIT; "
                       "CREATE ROLE dig02_read LOGIN; "
                       "GRANT USAGE ON SCHEMA gemapi TO dig02_read; "
                       "GRANT SELECT ON gemapi.digues_carte, "
                       "gemapi.digues_reperes, gemapi.digues, gemapi.cours_eau "
                       "TO dig02_read;")
        count = sql(container, "SET ROLE dig02_read; SELECT count(*) FROM "
                    "gemapi.digues_carte;").stdout.strip()
        assert count.endswith("2")
        forbidden = sql(container, "SET ROLE dig02_read; INSERT INTO gemapi.digues(nom) "
                        "VALUES ('interdit');", check=False)
        assert forbidden.returncode != 0 and "permission denied" in forbidden.stderr
        frozen = sql(container, "SELECT string_agg(encode(ST_AsEWKB(geom_reference),"
                     "'hex'),',' ORDER BY rive) FROM gemapi.digues_reperes;").stdout

        port = command("docker", "port", container, "5432").stdout.strip().rsplit(":", 1)[-1]
        app = QgsApplication([], True)
        app.initQgis()
        if not QFontDatabase().families():
            for font_path in (Path("C:/Windows/Fonts/arial.ttf"),
                              Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
                if font_path.is_file():
                    assert QFontDatabase.addApplicationFont(str(font_path)) >= 0
                    break
        assert QFontDatabase().families(), "Aucune police accessible au rendu QGIS"
        with tempfile.TemporaryDirectory() as directory:
            project_copy(Path(directory) / "dig02_test.qgz", port)
            project = QgsProject.instance()
            assert project.read(str(Path(directory) / "dig02_test.qgz"))
            assert len(project.mapLayers()) == 33
            sections = project.mapLayer(LAYER_ID)
            river_layer = next(layer for layer in project.mapLayers().values()
                               if QgsDataSourceUri(layer.source()).table() == "cours_eau")
            assert sections.isValid() and river_layer.isValid()
            assert sections.readOnly() and sections.featureCount() == 2
            assert river_layer.featureCount() == 1
            assert not sections.dataProvider().capabilities() & QgsVectorDataProvider.AddFeatures
            assert sections.isInScaleRange(5000)
            assert sections.isInScaleRange(50000)
            assert not sections.isInScaleRange(100000)
            rules = sections.renderer().rootRule().children()
            assert len(rules) == 4
            offsets = [rule.symbol().symbolLayer(0).offset() for rule in rules]
            assert any(offset < 0 for offset in offsets), offsets
            assert any(offset > 0 for offset in offsets), offsets
            assert [f["rive"] for f in sections.getFeatures()] == ["G", "D"] or \
                   {f["rive"] for f in sections.getFeatures()} == {"G", "D"}
            assert {f["etat_referentiel"] for f in sections.getFeatures()} == {"CONFORME"}
            for name in ("digue_nom", "riviere_nom", "rive", "etat_referentiel"):
                assert name in sections.fields().names()
            image = map_image([sections, river_layer], 5000)
            left, right = colored_pixels(image, "G"), colored_pixels(image, "D")
            assert len(left) > 200 and len(right) > 200, (len(left), len(right))
            assert sum(left) / len(left) < sum(right) / len(right)
            CAPTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
            painter = QPainter(image)
            assert painter.isActive()
            painter.setPen(QColor("#17324a"))
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            painter.drawText(20, 32, "Digues · repérage sur l’axe du cours d’eau")
            painter.setFont(QFont("Arial", 9))
            painter.drawText(20, image.height() - 18,
                             "Données fictives · G/D selon le sens de numérisation · décalage graphique uniquement")
            painter.end()
            assert image.save(str(CAPTURE_PATH))
            assert any(image.pixelColor(x, y).lightness() < 150
                       for y in range(5, 45) for x in range(15, 600))
            for scale in (50000, 100000):
                rendered = map_image([sections, river_layer], scale)
                g, d = colored_pixels(rendered, "G"), colored_pixels(rendered, "D")
                assert (len(g) > 0 and len(d) > 0) if scale == 50000 else not (g or d)
            assert sql(container, "SELECT string_agg(encode(ST_AsEWKB(geom_reference),"
                       "'hex'),',' ORDER BY rive) FROM gemapi.digues_reperes;"
                       ).stdout == frozen

            sql(container, f"UPDATE gemapi.cours_eau SET direction=NULL WHERE id='{river}';")
            sections.reload()
            assert {f['etat_referentiel'] for f in sections.getFeatures()} == {'COURS_EAU_NON_QUALIFIE'}
            unqualified_image = map_image([sections, river_layer], 5000)
            red_unqualified = sum(1 for y in range(unqualified_image.height())
                                  for x in range(unqualified_image.width())
                                  if (lambda c: c.red() > 150 and c.green() < 90 and c.blue() < 110)
                                  (unqualified_image.pixelColor(x,y)))
            assert red_unqualified > 30, red_unqualified
            sql(container, f"UPDATE gemapi.cours_eau SET geom=ST_Translate(geom,0,20) "
                           f"WHERE id='{river}';")
            sections.reload()
            assert {f["etat_referentiel"] for f in sections.getFeatures()} == {
                "REFERENTIEL_MODIFIE"}
            changed_image = map_image([sections, river_layer], 5000)
            red = sum(1 for y in range(changed_image.height())
                      for x in range(changed_image.width())
                      if (lambda c: c.red() > 150 and c.green() < 90
                          and c.blue() < 110)(changed_image.pixelColor(x, y)))
            assert red > 30, red
            assert sql(container, "SELECT string_agg(encode(ST_AsEWKB(geom_reference),"
                       "'hex'),',' ORDER BY rive) FROM gemapi.digues_reperes;"
                       ).stdout == frozen
            project.clear()
        print("DIG-02 : projet rouvert, rives G/D séparées, échelles 1:5k/50k/100k, "
              "états non qualifié/modifié visibles et capture QGIS validés")
    finally:
        if app is not None:
            app.exitQgis()
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
