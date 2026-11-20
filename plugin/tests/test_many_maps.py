"""Offscreen PDF stress check: 30 records with maps and photographs."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from qgis.PyQt.QtGui import QColor, QImage
from qgis.core import QgsApplication, QgsProject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.report_pdf import export_report


def main():
    app = QgsApplication([], True)
    app.initQgis()
    records = []
    for index in range(30):
        x = 1674475 + index * 20
        y = 9259011 + index * 20
        geometry = (f"POINT({x} {y})" if index % 3 == 0 else
                    f"LINESTRING({x} {y},{x + 1} {y + 15000})" if index % 3 == 1 else
                    f"POLYGON(({x} {y},{x + 100} {y},{x + 100} {y + 100},"
                    f"{x} {y + 100},{x} {y}))")
        records.append({
            "id": str(index), "intitule": f"Essai {index:02d}", "date_debut": None,
            "date_fin": None, "type": "Test", "technician": "Technicien",
            "provider": "Prestataire", "communes": "Béthune", "objects": "",
            "own_length": None, "own_area": None, "has_geometry": True,
            "reference_measures": None, "quantite": None, "unite": "",
            "description": "Essai de pagination", "photo_1": "", "photo_2": "",
            "own_wkt": geometry,
            "reference_geometries": [],
        })
    output = Path(__file__).resolve().parents[2] / "audits" / "pdf" / "rapport_cartes_30_prestations_test.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as photo_directory:
        photo = Path(photo_directory) / "chantier.png"
        image = QImage(800, 400, QImage.Format_RGB32)
        image.fill(QColor("#416f91"))
        assert image.save(str(photo))
        for record in records:
            record["photo_1"] = str(photo)
            record["photo_1_commentaire"] = "Photographie fictive"
        if os.environ.get("SIG_PRESTATIONS_TEST_IGN") != "1":
            before = set(QgsProject.instance().mapLayers())
            with patch("gemapi_app.report_pdf.background", return_value=None):
                pages = export_report(records, {"groups": ()}, "Trente prestations fictives",
                                      [], str(output), include_maps=True, include_photos=True)
            assert pages >= 10 and set(QgsProject.instance().mapLayers()) == before
            if shutil.which("pdftotext"):
                text = subprocess.check_output(["pdftotext", "-layout", str(output), "-"]).decode()
                assert text.count("Cadrage :") == 30
                assert text.count("Photographies") == 30
                assert f"Page {pages} / {pages}" in text
                assert "Fond IGN indisponible" in text
            print(f"Cartes sans fond et photos : 30 prestations, {pages} pages, aucune coupure, projet intact")
        if os.environ.get("SIG_PRESTATIONS_TEST_IGN") == "1":
            payload = Path(photo_directory) / "worker.json"
            real_output = output.with_name("rapport_cartes_30_prestations_ign_test.pdf")
            payload.write_text(json.dumps({
                "records": records, "filters": {"groups": ()},
                "summary": "Trente prestations fictives", "warnings": [],
                "include_photos": True, "include_maps": True,
                "map_background": "epure",
            }), encoding="utf-8")
            worker = Path(__file__).resolve().parents[1] / "gemapi_app" / "report_worker.py"
            completed = subprocess.run([sys.executable, str(worker), str(payload),
                                        str(real_output)], capture_output=True, text=True,
                                       timeout=900, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
            assert completed.returncode == 0, completed.stderr + completed.stdout
            updates = [json.loads(line) for line in completed.stdout.splitlines()
                       if line.startswith("{")]
            assert any(item.get("current") == 30 for item in updates)
            assert real_output.is_file() and real_output.stat().st_size > 1000
            if shutil.which("pdftotext"):
                real_text = subprocess.check_output(["pdftotext", "-layout",
                                                     str(real_output), "-"]).decode()
                assert real_text.count("Cadrage :") == 30
                assert real_text.count("Photographies") == 30
                print("Fond IGN :", "présent" if "© IGN" in real_text else "indisponible")
    app.exitQgis()


if __name__ == "__main__":
    main()
