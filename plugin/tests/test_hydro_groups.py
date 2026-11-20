"""Conservative watercourse display grouping using fictitious geometries only."""

import sys
import unittest
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

from qgis.core import QgsApplication, QgsFeature, QgsGeometry, QgsVectorLayer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.hydro_groups import build_options, search_key  # noqa: E402


ROOT = Path(__file__).resolve().parents[2]


class HydroGroupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication([], False)
        cls.app.initQgis()
        cls.demo = QgsVectorLayer(str(ROOT / "demo/gpkg/cours_eau.gpkg"),
                                  "cours_eau", "ogr")
        assert cls.demo.isValid()

    @classmethod
    def tearDownClass(cls):
        cls.demo = None
        # A later test module may use QGIS and GDAL in this same interpreter.
        # exitQgis() clears GDAL drivers and a second shutdown can crash Qt.

    def test_successive_homonym_multipart_and_business_names(self):
        before = {str(f["id"]): bytes(f.geometry().asWkb()) for f in self.demo.getFeatures()}
        options = build_options(self.demo.getFeatures())
        self.assertEqual(len(options), 57)
        triples = [option for option in options if "Trois Saules" in option.label]
        self.assertEqual(len(triples), 2)
        self.assertEqual(sorted(len(option.ids) for option in triples), [1, 2])
        self.assertEqual(len(set(uid for option in triples for uid in option.ids)), 3)
        self.assertTrue(all("secteur" in option.label for option in triples))
        canal = next(option for option in options if "Canal des Prairies" in option.label)
        self.assertEqual(len(canal.ids), 1)
        feature = next(f for f in self.demo.getFeatures() if str(f["id"]) == canal.ids[0])
        self.assertEqual(len(feature.geometry().asMultiPolyline()), 3)
        labels = {option.label for option in options}
        self.assertTrue({'Fossé démo A', 'Écoulement démo B', 'Fossé démo C'} <= labels)
        self.assertEqual(before, {str(f["id"]): bytes(f.geometry().asWkb())
                                  for f in self.demo.getFeatures()})

    def test_search_uses_names_without_changing_identity(self):
        options = build_options(self.demo.getFeatures())
        self.assertEqual(len([option for option in options
                              if search_key("  RUISSEAU DES TROIS SAULES ") in option.search]), 2)
        self.assertEqual(len([option for option in options
                              if search_key("demo-ce-101") in option.search]), 0)
        self.assertEqual(search_key("  CÁNAL  des   prairies "), "canal des prairies")

    def test_missing_names_are_rejected(self):
        for name in (None, "", "  ", "\t\n"):
            layer = QgsVectorLayer("MultiLineString?crs=EPSG:3950&field=id:string&field=nom:string", "fiction", "memory")
            feature = QgsFeature(layer.fields()); feature['id'] = str(uuid5(NAMESPACE_URL, 'missing-name'))
            feature['nom'] = name
            feature.setGeometry(QgsGeometry.fromWkt('MULTILINESTRING((0 0,10 0))'))
            layer.dataProvider().addFeatures([feature])
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'obligatoire'):
                build_options(layer.getFeatures())

    def test_confluence_duplicates_and_distinct_business_names_are_not_joined(self):
        layer = QgsVectorLayer("MultiLineString?crs=EPSG:3950", "fiction", "memory")
        layer.dataProvider().addAttributes(self.demo.fields().toList())
        layer.updateFields()
        cases = (
            ("a", "Ruisseau fictif", "MULTILINESTRING((0 0,10 0))"),
            ("b", "Ruisseau fictif", "MULTILINESTRING((10 0,20 0))"),
            ("c", "Affluent fictif", "MULTILINESTRING((10 0,10 10))"),
            ("d", "Même tracé fictif", "MULTILINESTRING((100 0,110 0))"),
            ("e", "Même tracé fictif", "MULTILINESTRING((100 0,110 0))"),
            ("f", "Branche fictive F", "MULTILINESTRING((200 0,210 0))"),
            ("g", "Branche fictive G", "MULTILINESTRING((210 0,220 0))"),
        )
        features = []
        for key, name, wkt in cases:
            feature = QgsFeature(layer.fields())
            feature.setAttribute("id", str(uuid5(NAMESPACE_URL, "ux-hydro-" + key)))
            feature.setAttribute("nom", name)
            feature.setAttribute("type_ecoulement", "ruisseau")
            feature.setAttribute("source", "DEMO_TEST")
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            features.append(feature)
        self.assertTrue(layer.dataProvider().addFeatures(features)[0])
        options = build_options(layer.getFeatures())
        self.assertEqual(len(options), 7)
        self.assertEqual(len([o for o in options if "Ruisseau fictif" in o.label]), 2)
        self.assertEqual(len([o for o in options if "Même tracé fictif" in o.label]), 2)
        self.assertEqual(len([o for o in options if "Branche fictive" in o.label]), 2)


if __name__ == "__main__":
    unittest.main()
