"""MOD-HYDRO-01: fictitious GPKG, source-schema parity and QGIS project."""

import hashlib
from itertools import combinations
from pathlib import Path
from shutil import copy2
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID
from xml.etree import ElementTree
from zipfile import ZipFile

from osgeo import ogr

ogr.UseExceptions()


ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo" / "gpkg" / "cours_eau.gpkg"


def structure(path):
    # Read the current fictional GeoPackage only.
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        fields = db.execute("PRAGMA table_info(cours_eau)").fetchall()
        geometry = db.execute("SELECT column_name,geometry_type_name,srs_id,z,m "
                              "FROM gpkg_geometry_columns WHERE table_name='cours_eau'").fetchall()
        index = db.execute("SELECT sql FROM sqlite_master WHERE type='index' "
                           "AND tbl_name='cours_eau'").fetchall()
    return fields, geometry, index


def signature(path):
    data = ogr.Open(str(path), 0)
    layer = data.GetLayerByName("cours_eau")
    rows = []
    for feature in layer:
        rows.append((feature.GetField("id"), feature.GetField("nom"),
                     feature.GetField("type_ecoulement"),
                     feature.GetField("valide"), feature.GetField("source"),
                     feature.GetGeometryRef().ExportToWkb().hex()))
    data = None
    return hashlib.sha256(repr(sorted(rows)).encode()).hexdigest()


class ModHydroTests(unittest.TestCase):
    def test_current_demo_structure(self):
        columns, geometry, _ = structure(DEMO)
        self.assertEqual([col[1] for col in columns],
                         ["fid", "geom", "id", "nom", "type_ecoulement",
                          "source", "valide", "direction", "section"])
        self.assertEqual(columns[6][2].upper(), "BOOLEAN")
        self.assertEqual(columns[6][3], 1)
        self.assertEqual(geometry, [("geom", "MULTILINESTRING", 3950, 0, 0)])

    def test_identity_geometry_and_demonstration_cases(self):
        data = ogr.Open(str(DEMO), 0)
        layer = data.GetLayerByName("cours_eau")
        self.assertEqual(layer.GetFeatureCount(), 58)
        ids, names, kinds = set(), {}, set()
        multipart = disjoint = unnamed = 0
        qualified=set()
        for feature in layer:
            uid = feature.GetField("id")
            self.assertEqual(str(UUID(uid)), uid)
            self.assertNotIn(uid, ids)
            ids.add(uid)
            name = feature.GetField("nom")
            if name:
                names.setdefault(name, []).append((uid, feature.GetGeometryRef().Clone()))
            else:
                unnamed += 1
            direction=feature.GetField('direction')
            if direction is not None:
                self.assertEqual(direction,1)
                qualified.add(uid)
            kinds.add(feature.GetField("type_ecoulement"))
            self.assertIn(feature.GetField("source"),
                          {"INVENTAIRE_RIVIERES", "RELEVE_FOSSES", "SYNTHESE_CARTOGRAPHIQUE"})
            geom = feature.GetGeometryRef()
            self.assertEqual(feature.GetField('section'),geom.GetGeometryCount())
            self.assertEqual(bool(feature.GetField('valide')),direction==1 and geom.GetGeometryCount()==1)
            self.assertEqual(ogr.GT_Flatten(geom.GetGeometryType()), ogr.wkbMultiLineString)
            self.assertTrue(geom.IsValid() and not geom.IsEmpty() and geom.Length() > 0)
            if geom.GetGeometryCount() > 1:
                multipart += 1
                if any(a.Distance(b) > 1 for a, b in
                       combinations([geom.GetGeometryRef(i) for i in range(geom.GetGeometryCount())], 2)):
                    disjoint += 1
        self.assertEqual(len(ids), 58)
        self.assertEqual(qualified,{'90368380-5d42-4a28-9889-6ae657f84a75'})
        self.assertGreaterEqual(multipart, 3)
        self.assertGreaterEqual(disjoint, 2)
        self.assertEqual(unnamed, 0)
        self.assertTrue({"rivière", "ruisseau", "fossé", "canal", "indéterminé"} <= kinds)
        homonyms = names["Ruisseau des Trois Saules"]
        self.assertEqual(len(homonyms), 3)
        self.assertTrue(any(a[1].Distance(b[1]) == 0 for a, b in combinations(homonyms, 2)))
        self.assertTrue(any(a[1].Distance(b[1]) > 1000 for a, b in combinations(homonyms, 2)))

    def test_generator_is_semantically_reproducible(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "demo"
            (root / "gpkg").mkdir(parents=True)
            (root / "data").mkdir()
            copy2(DEMO, root / "gpkg/cours_eau.gpkg")
            for name in ("generer_cours_eau.py",):
                copy2(ROOT / "demo/data" / name, root / "data" / name)
            subprocess.run([sys.executable, str(root / "data/generer_cours_eau.py")],
                           check=True, capture_output=True)
            self.assertEqual(signature(root / "gpkg/cours_eau.gpkg"), signature(DEMO))
            for name in ("11_cours_eau.sql",):
                self.assertEqual((root / "data" / name).read_bytes(),
                                 (ROOT / "demo/data" / name).read_bytes())

    def test_qgis_project_has_one_hydro_family(self):
        with ZipFile(ROOT / "demo/prestations_demo.qgz") as archive:
            self.assertIsNone(archive.testzip())
            root = ElementTree.fromstring(next(archive.read(name) for name in archive.namelist()
                                               if name.endswith(".qgs")))
        layers = root.findall("./projectlayers/maplayer")
        hydro = [layer for layer in layers if layer.findtext("layername") == "Cours d'eau"]
        self.assertEqual(len(layers), 33)
        for table in ('ah_sections','ah_sections_carte'):
            section_layers=[layer for layer in layers if f'"gemapi"."{table}"' in layer.findtext('datasource','')]
            self.assertEqual(len(section_layers),1)
            self.assertEqual(section_layers[0].get('readOnly'),'1')
        self.assertEqual(len({layer.findtext('id') for layer in layers}),len(layers))
        self.assertEqual(len(hydro), 1)
        self.assertIn('"gemapi"."cours_eau"', hydro[0].findtext("datasource"))
        self.assertIn("type=MultiLineString", hydro[0].findtext("datasource"))
        fields = hydro[0].find("fieldConfiguration")
        self.assertIsNotNone(fields.find("./field[@name='valide']/editWidget[@type='CheckBox']"))
        self.assertIsNone(fields.find("./field[@name='code_topage']"))
        self.assertEqual(hydro[0].get("readOnly"), "0")
        self.assertEqual(hydro[0].find("./editable/field[@name='valide']").get("editable"), "0")
        self.assertEqual(hydro[0].find("./editable/field[@name='section']").get("editable"), "0")

if __name__ == "__main__":
    unittest.main()
