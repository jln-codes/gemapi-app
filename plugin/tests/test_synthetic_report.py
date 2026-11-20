"""Landscape synthesis: grouping depth, overlapping communes and pagination."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from qgis.core import QgsApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.report_data import grouped_entries, report_warnings
from gemapi_app.report_pdf import export_synthetic_report


class SyntheticReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication([], True)
        cls.app.initQgis()

    @classmethod
    def tearDownClass(cls):
        cls.app.exitQgis()

    def test_grouping_and_multipage(self):
        records = []
        for index in range(40):
            records.append({
                "id": f"00000000-0000-4000-8000-{index + 1:012d}",
                "intitule": f"Prestation {index + 1:02d}",
                "date_debut": "2026-01-01", "date_fin": "2026-01-15",
                "type": "Entretien" if index % 2 else "Étude",
                "statut": "Terminé" if index % 3 else "Planifié",
                "technician": "Alice", "provider": "Entreprise A",
                "communes": "A; B" if index == 0 else "B",
                "objects": "", "quantite": index + 1, "unite": "arbres",
                "own_length": 10.0, "own_area": None, "has_geometry": True,
                "reference_measures": None,
            })
        with tempfile.TemporaryDirectory() as directory:
            for groups in ((), ("year",), ("commune", "type"),
                           ("year", "commune", "status")):
                with self.subTest(groups=groups):
                    filters = {"groups": groups}
                    path = Path(directory) / f"synthetic-{len(groups)}.pdf"
                    pages = export_synthetic_report(
                        records, filters, "Démonstration", report_warnings(records, filters),
                        path)
                    info = subprocess.check_output(["pdfinfo", str(path)], text=True)
                    self.assertIn("Page size:       842 x 595 pts (A4)", info)
                    text = subprocess.check_output(
                        ["pdftotext", "-layout", str(path), "-"], text=True)
                    self.assertIn("Périmètre : Toutes les prestations — 40 interventions", text)
                    self.assertIn("Organisation :", text)
                    self.assertIn("Somme des longueurs cartographiées", text)
                    self.assertIn("Quantité", text)
                    self.assertNotIn("Filtres appliqués", text)
                    self.assertNotIn("Démonstration", text)
                    self.assertIn("40 prestations distinctes", text)
                    self.assertNotIn("Localisation", text)
                    self.assertNotIn("Photographies", text)
                    self.assertEqual(text.count("Prestation 01"), 2 if "commune" in groups else 1)
                    if len(groups) == 3:
                        self.assertGreater(pages, 1)
                        self.assertIn("Les groupes communaux se recouvrent", text)
            entries = grouped_entries(records, ("commune",))
            self.assertEqual(len(entries), 41)
            self.assertEqual(next(path[0][2] for path, _ in entries
                                  if path[0][1] == "A"), 1)
            self.assertEqual(next(path[0][2] for path, _ in entries
                                  if path[0][1] == "B"), 40)
            self.assertEqual(next(path[0][3] for path, _ in entries
                                  if path[0][1] == "A"), 10)
            self.assertEqual(next(path[0][3] for path, _ in entries
                                  if path[0][1] == "B"), 400)
            self.assertEqual(sum(record["own_length"] for record in records), 400)


if __name__ == "__main__":
    unittest.main()
