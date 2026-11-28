"""Creation writes geometry and refreshes an existing, renamed QGIS PostGIS layer."""

import sys
import time
from pathlib import Path
from uuid import uuid4

from qgis.PyQt.QtCore import QDate
from qgis.core import (QgsApplication, QgsDataSourceUri, QgsGeometry, QgsProject,
                       QgsRectangle, QgsVectorLayer, QgsWkbTypes)
from qgis.gui import QgsMapCanvas, QgsMapToolIdentify

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.creation import CreationDialog  # noqa: E402
from test_postgres_integration import ROOT, command, sql  # noqa: E402


def main():
    container = "sig-prestations-visibility-" + uuid4().hex[:10]
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
        sql(container, (ROOT / "model/schema.sql").read_text())
        provider_id, type_id, technician_id, ah_id, storage_id, ouvrage_id = (str(uuid4()) for _ in range(6))
        sql(container, f"INSERT INTO gemapi.prestataires (id,nom) "
                       f"VALUES ('{provider_id}','Prestataire test'); "
                       "INSERT INTO gemapi.types_prestations (id,code,libelle, categorie_id) "
                       f"VALUES ('{type_id}','VISIBILITE','Test visibilité', 'cf2572fb-9365-5ac5-bdf4-0d66581d9aaa'); "
                       f"INSERT INTO gemapi.techniciens(id,nom,prenom) VALUES ('{technician_id}','Test','Alice'); "
                       f"INSERT INTO gemapi.ah(id,nom) VALUES ('{ah_id}','AH de test'); "
                       f"INSERT INTO gemapi.ah_stockage(id,ah_id,nom,geom) VALUES ('{storage_id}','{ah_id}','Stockage',ST_GeomFromText('POLYGON((-100 -100,100 -100,100 100,-100 100,-100 -100))',3950)); "
                       f"INSERT INTO gemapi.ah_ouvrage(id,ah_id,nom,geom) VALUES ('{ouvrage_id}','{ah_id}','Ouvrage',ST_GeomFromText('LINESTRING(0 0,20 0)',3950));")
        port = command("docker", "port", container, "5432").stdout.strip().rsplit(":", 1)[-1]
        app = QgsApplication([], True)
        app.initQgis()
        canvas = QgsMapCanvas()
        canvas.setExtent(QgsRectangle(-100, -100, 100, 100))
        canvas.resize(500, 400)
        canvas.show()

        def make_layer(table, geometry_column, display_name, kind=QgsWkbTypes.Point):
            uri = QgsDataSourceUri()
            uri.setConnection("127.0.0.1", port, "postgres", "postgres", "")
            uri.setDataSource("gemapi", table, geometry_column, "", "id")
            if geometry_column:
                uri.setWkbType(kind)
                uri.setSrid("3950")
            layer = QgsVectorLayer(uri.uri(False), display_name, "postgres")
            assert layer.isValid(), (layer.source(), layer.error().summary())
            QgsProject.instance().addMapLayer(layer)
            return layer

        prestations = make_layer("prestations_carte", "geom", "Travaux personnalisés")
        make_layer("prestataires", "", "Partenaires actifs")
        make_layer("types_prestations", "", "Catalogue des travaux")
        canvas.setDestinationCrs(prestations.crs())
        canvas.setLayers([prestations])
        canvas.refresh()
        app.processEvents()
        assert prestations.featureCount() == 0
        symbol_before = prestations.renderer().symbol().dump()
        repaints = []
        prestations.repaintRequested.connect(lambda *_: repaints.append(True))

        class Interface:
            def mapCanvas(self):
                return canvas

        dialog = CreationDialog(Interface())
        assert dialog._canonical_layer("prestations_carte") is prestations
        dialog.typeCombo.setCurrentIndex(dialog.typeCombo.findData(type_id))
        dialog.prestataireCombo.setCurrentIndex(dialog.prestataireCombo.findData(provider_id))
        assert dialog.typeCombo.currentData() == type_id
        assert dialog.prestataireCombo.currentData() == provider_id
        assert dialog.statutCombo.count() == 5
        dialog.statutCombo.setCurrentIndex(1)  # Planifié
        dialog.technicienCombo.setCurrentIndex(dialog.technicienCombo.findData(technician_id))
        dialog._add_selection('ah_stockage',(storage_id,),'Stockage')
        dialog.debutDate.setDate(QDate(2027, 1, 1))
        dialog.finDate.setDate(QDate(2027, 1, 15))
        dialog.intituleEdit.setText("Point enregistré")
        dialog.geometry = QgsGeometry.fromWkt("POINT(0 0)")
        dialog.geometry_kind = "point"
        dialog._save()
        assert "enregistrées" in dialog.statusLabel.text(), dialog.statusLabel.text()
        assert repaints, "La couche PostGIS existante n'a pas été rafraîchie."
        assert prestations.featureCount() == 1
        feature = next(prestations.getFeatures())
        assert feature.geometry().asWkt().upper().startswith("POINT")
        assert prestations.renderer().symbol().dump() == symbol_before
        assert sql(container, "SELECT ST_AsText(geom) FROM gemapi.prestations").stdout.strip() == "POINT(0 0)"
        canvas.refresh()
        app.processEvents()
        assert canvas.layers() == [prestations]
        dialog.shutdown()
        canvas.setRenderFlag(False)
        lines = make_layer('prestations_carte', 'geom', 'Travaux lignes', QgsWkbTypes.MultiLineString)
        areas = make_layer('prestations_carte', 'geom', 'Travaux surfaces', QgsWkbTypes.MultiPolygon)
        layers = (prestations, lines, areas)
        canvas.setLayers(list(layers))
        symbols = [layer.renderer().symbol().dump() for layer in layers]
        repainted = set()
        for layer in layers:
            layer.repaintRequested.connect(lambda *_, uid=layer.id(): repainted.add(uid))

        def create(family, parent, title):
            form = CreationDialog(Interface())
            for combo, uid in ((form.typeCombo, type_id),
                               (form.prestataireCombo, provider_id),
                               (form.technicienCombo, technician_id)):
                combo.setCurrentIndex(combo.findData(uid))
            form.statutCombo.setCurrentIndex(1)
            form._add_selection(family, (parent,), title)
            form.debutDate.setDate(QDate(2027, 1, 1))
            form.finDate.setDate(QDate(2027, 1, 15))
            form.intituleEdit.setText(title)
            form.quantiteEdit.setText('3')
            assert form.geometry is None
            form._save()
            assert 'enregistrées' in form.statusLabel.text(), form.statusLabel.text()
            uid = sql(container, "SELECT id FROM gemapi.prestations WHERE intitule='" + title + "'").stdout.strip()
            assert uid
            form.shutdown()
            return uid

        storage_prestation = create('ah_stockage', storage_id, 'Stockage sans forme propre')
        ouvrage_prestation = create('ah_ouvrage', ouvrage_id, 'Ouvrage sans forme propre')
        assert [layer.featureCount() for layer in layers] == [1, 1, 1]
        assert repainted == {layer.id() for layer in layers}
        fields = {'nombre_points', 'longueur_m', 'surface_m2', 'surface_ha',
                  'type_geometrie', 'type_geometrie_postgis', 'possede_geometrie', 'origine_mesures'}
        identifier = QgsMapToolIdentify(canvas)
        for layer, uid, metric, value in ((areas, storage_prestation, 'surface_m2', 40000),
                                           (lines, ouvrage_prestation, 'longueur_m', 20)):
            assert fields <= set(layer.fields().names())
            feature = next(f for f in layer.getFeatures() if str(f['id']) == uid)
            assert feature[metric] == value and feature['origine_mesures'] == 'Patrimoine de rattachement'
            layer.selectByIds([feature.id()])
            assert str(layer.selectedFeatures()[0]['id']) == uid
            results = identifier.identify(QgsGeometry.fromRect(QgsRectangle(-2, -2, 2, 2)),
                QgsMapToolIdentify.TopDownAll, [layer], QgsMapToolIdentify.VectorLayer)
            assert any(str(result.mFeature['id']) == uid and result.mFeature[metric] == value
                       for result in results)
            layer.removeSelection()

        # A real plugin edit moves the same UUID between geometry families;
        # removing its optional own geometry reveals the storage again.
        for own, expected in (('POINT(5 5)', [2, 1, 0]), (None, [1, 1, 1])):
            form = CreationDialog(Interface(), mode='edit')
            form.load_existing(form._connection(), storage_prestation)
            form.geometry = QgsGeometry.fromWkt(own) if own else None
            form.geometry_kind = 'point' if own else None
            form._save()
            assert form._edit_saved
            assert [layer.featureCount() for layer in layers] == expected
            assert sql(container, "SELECT quantite=3,geom IS NULL FROM gemapi.prestations "
                       f"WHERE id='{storage_prestation}'").stdout.strip() == ('t|f' if own else 't|t')
            form.shutdown()
        assert [layer.renderer().symbol().dump() for layer in layers] == symbols
        print('PERF08-GEOM: création AH sans forme, huit mesures, identification, édition et trois rafraîchissements validés')
        canvas.close()
        QgsProject.instance().clear()
        app.exitQgis()
        print("Après sauvegarde : géométrie PostGIS visible dans la couche existante, rafraîchie sans changement de symbole")
    finally:
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
