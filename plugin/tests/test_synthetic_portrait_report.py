"""Grouping, own-geometry extent and overflow of the portrait register."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from qgis.core import (QgsApplication, QgsCoordinateTransform, QgsGeometry,
                       QgsProject, QgsVectorLayer)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.report_maps import DATA_CRS, MAP_CRS
from gemapi_app.report_data import report_context
from gemapi_app.report_synthetic_portrait import (
    _cell_lines, export_synthetic_portrait_report, group_layers_and_extent, terminal_groups)
from gemapi_app.report_pdf import _restore_qgis_pdf_metadata


def record(number, *, year=2026, kind="Curage", status="En cours",
           communes="Dury", geometry="POINT(1674500 9259000)"):
    return {"id": f"00000000-0000-4000-8000-{number:012d}",
            "intitule": f"Prestation {number}", "date_debut": f"{year}-01-01",
            "date_fin": f"{year}-01-15", "type": kind, "statut": status,
            "technician": "Technicien A", "provider": "Prestataire B",
            "communes": communes, "objects": "", "quantite": number,
            "unite": "interventions", "own_length": None, "own_area": None,
            "own_wkt": geometry,
            "reference_geometries": [{"wkt": "POINT(0 0)", "direct": True}]}


class SyntheticPortraitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication([], True)
        cls.app.initQgis()

    @classmethod
    def tearDownClass(cls):
        cls.app.exitQgis()

    def test_grouping_depth_and_commune_overlap(self):
        records = [record(1, communes="Dury; Cagnicourt"), record(2),
                   record(3, year=2027, kind="Étude", status="Terminé")]
        for groups, sizes in (((), [3]), (("year",), [2, 1]),
                              (("year", "type"), [2, 1]),
                              (("year", "type", "status"), [2, 1])):
            terminal = terminal_groups(records, {"groups": groups})
            self.assertEqual([len(members) for _, members in terminal], sizes)
        terminal = terminal_groups(records, {"groups": ("commune",)})
        self.assertEqual(len(terminal), 2)
        self.assertEqual(sum(len(members) for _, members in terminal), 4)
        self.assertEqual(len({row["id"] for row in records}), 3)

    def test_parent_zone_measure_is_separate_from_declared_quantity(self):
        polygon = record(1)
        polygon.update(objects="sites_zones : Zone fictive", parent_zone_area=1250)
        text = " ".join(_cell_lines(polygon, ())[3])
        self.assertIn("Surface de la zone (géométrie parente) : 1 250,0 m²", text)
        self.assertIn("Quantité déclarée : 1 interventions", text)
        point = record(2)
        point.update(objects="sites_zones : Point fictif")
        self.assertNotIn("Surface de la zone", " ".join(_cell_lines(point, ())[3]))

    def test_business_scope_reflects_combined_filters_and_group_order(self):
        records = [record(1), record(2)]
        scope, organization = report_context(records, {"groups": ()})
        self.assertEqual(scope, "Périmètre : Toutes les prestations — 2 interventions")
        self.assertEqual(organization, "Organisation : sans regroupement")
        scope, organization = report_context(records, {
            "completion": "completed", "years": (2026,),
            "communes": ("00000000-0000-4000-8000-000000000001",),
            "technicians": ("00000000-0000-4000-8000-000000000002",),
            "groups": ("year", "type", "status"),
        })
        self.assertIn("Prestations terminées", scope)
        self.assertIn("année 2026", scope)
        self.assertIn("commune sélectionnée", scope)
        self.assertIn("technicien sélectionné", scope)
        self.assertNotIn("Toutes les prestations", scope)
        self.assertEqual(organization, "Organisation : année → type de prestation → statut")

    def test_six_geometry_types_and_own_extent(self):
        x, y = 1674500, 9259000
        shapes = (
            f"POINT({x} {y})",
            f"MULTIPOINT(({x+10} {y}),({x+20} {y}))",
            f"LINESTRING({x} {y},{x+30} {y+10})",
            f"MULTILINESTRING(({x} {y},{x+20} {y}),({x} {y+20},{x+20} {y+20}))",
            f"POLYGON(({x} {y},{x+30} {y},{x+30} {y+30},{x} {y+30},{x} {y}))",
            f"MULTIPOLYGON((({x} {y},{x+10} {y},{x+10} {y+10},{x} {y+10},{x} {y})),"
            f"(({x+20} {y+20},{x+30} {y+20},{x+30} {y+30},{x+20} {y+30},{x+20} {y+20})))",
        )
        records = [record(i + 1, geometry=shape) for i, shape in enumerate(shapes)]
        layers, extent = group_layers_and_extent(records)
        self.assertEqual(len(layers), 6)
        self.assertEqual(sum(layer.featureCount() for layer in layers), 6)
        transform = QgsCoordinateTransform(DATA_CRS, MAP_CRS, QgsProject.instance())
        for row in records:
            geometry = QgsGeometry.fromWkt(row["own_wkt"])
            geometry.transform(transform)
            bounds = geometry.boundingBox()
            self.assertLessEqual(extent.xMinimum(), bounds.xMinimum())
            self.assertLessEqual(extent.yMinimum(), bounds.yMinimum())
            self.assertGreaterEqual(extent.xMaximum(), bounds.xMaximum())
            self.assertGreaterEqual(extent.yMaximum(), bounds.yMaximum())
        self.assertLess(extent.width(), 1000)  # The distant patrimonial point is ignored.

    def test_table_overflow_does_not_repeat_map(self):
        records = [record(i, geometry=f"POINT({1674500+i*3} 9259000)")
                   for i in range(1, 19)]
        for row in records:
            row["objects"] = "Objet lié de démonstration, " * 8
        records[0]["position"] = "Talus côté rivière / stockage"
        basemap = QgsVectorLayer("Polygon?crs=EPSG:2154", "Fond de test", "memory")
        self.assertTrue(basemap.isValid())
        with tempfile.TemporaryDirectory() as directory:
            for groups in ((), ("year",)):
                with self.subTest(groups=groups):
                    output = Path(directory) / f"registre-{len(groups)}.pdf"
                    pages, maps = export_synthetic_portrait_report(
                        records, {"groups": groups}, output, basemap_layer=basemap)
                    self.assertGreater(pages, 1)
                    self.assertEqual(maps, 1)
                    self.assertGreater(output.stat().st_size, 1000)
                    if shutil.which("pdftotext"):
                        content = subprocess.check_output(
                            ["pdftotext", "-layout", str(output), "-"], text=True)
                        self.assertEqual(content.count("© IGN - Géoplateforme"), 1)
                        self.assertIn("Quantité déclarée", content)
                        self.assertIn("Position : Talus côté rivière / stockage",
                                      " ".join(content.split()))
                        self.assertIn("Somme des longueurs cartographiées", content)
                        self.assertGreaterEqual(content.count("Dates"), pages)
                        self.assertNotIn("Photographies", content)

    def test_two_and_three_level_exports_start_each_terminal_group_on_new_page(self):
        records = [record(1), record(2, status="Terminé"),
                   record(3, year=2027, kind="Étude", status="Terminé")]
        basemap = QgsVectorLayer("Polygon?crs=EPSG:2154", "Fond de test", "memory")
        self.assertTrue(basemap.isValid())
        with tempfile.TemporaryDirectory() as directory:
            for groups, expected_maps in ((('year', 'type'), 2),
                                          (('year', 'type', 'status'), 3)):
                with self.subTest(groups=groups):
                    output = Path(directory) / f"registre-{len(groups)}.pdf"
                    pages, maps = export_synthetic_portrait_report(
                        records, {"groups": groups}, output, basemap_layer=basemap)
                    self.assertEqual((pages, maps), (expected_maps, expected_maps))
                    if shutil.which("pdftotext"):
                        content = subprocess.check_output(
                            ["pdftotext", "-layout", str(output), "-"], text=True)
                        self.assertEqual(content.count("© IGN - Géoplateforme"), maps)
                        self.assertEqual(len([page for page in content.split("\f")
                                              if page.strip()]), pages)

    def test_many_terminal_groups_keep_one_summary_and_global_page_numbers(self):
        records = [record(number, year=2020 + number,
                          geometry=f"POINT({1674500 + number * 3} 9259000)")
                   for number in range(1, 13)]
        basemap = QgsVectorLayer("Polygon?crs=EPSG:2154", "Fond de test", "memory")
        self.assertTrue(basemap.isValid())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "registre-12-groupes.pdf"
            stages = []
            pages, maps = export_synthetic_portrait_report(
                records, {"groups": ("year",)}, output, basemap_layer=basemap,
                progress=lambda stage, current, total: stages.append((stage, current, total)))
            self.assertEqual((pages, maps), (12, 12))
            self.assertEqual(stages[-1][0], "Finalisation du document")
            self.assertIn("Rendu cartographique", [stage for stage, _, _ in stages])
            batches = [(stage, current, total) for stage, current, total in stages
                       if stage.startswith("Rendu cartographique et export PDF")]
            self.assertEqual([(current, total) for _, current, total in batches],
                             [(0, 2), (1, 2), (2, 2)])
            self.assertIn("10 groupes", batches[0][0])
            self.assertIn("2 groupes", batches[1][0])
            if shutil.which("pdfinfo"):
                _restore_qgis_pdf_metadata(output)
                info = subprocess.check_output(["pdfinfo", str(output)], text=True)
                self.assertIn("Creator:         QGIS ", info)
                self.assertIn("Producer:        QGIS ", info)
            if shutil.which("pdftotext"):
                content = subprocess.check_output(
                    ["pdftotext", "-layout", str(output), "-"], text=True)
                self.assertEqual(content.count("© IGN - Géoplateforme"), 12)
                self.assertEqual(content.count("Total général :"), 1)
                for number in range(1, 13):
                    self.assertIn(f"Page {number} / 12", content)


if __name__ == "__main__":
    unittest.main()
