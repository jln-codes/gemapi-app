"""The installed-style PDF worker runs independently and reports progress."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from qgis.PyQt.QtGui import QColor, QImage
from qgis.core import QgsApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.pdf_runtime import select_python, worker_environment


WORKER = Path(__file__).resolve().parents[1] / "gemapi_app" / "report_worker.py"


def main():
    record = {
        "id": "00000000-0000-4000-8000-000000000001", "intitule": "Essai d’export",
        "date_debut": "2027-01-01", "date_fin": "2027-01-15",
        "type": "Test", "statut": "Planifié",
        "technician": "Technicien", "provider": "Prestataire", "communes": "Béthune",
        "objects": "Stockage AH : Bois A",
        "own_length": None, "own_area": None,
        "has_geometry": True, "reference_measures": None, "quantite": "7",
        "unite": "arbres", "description": "Description interne cachée",
        "photo_1": "", "photo_2": "",
        "own_wkt": "POINT(700000 6600000)", "reference_geometries": [],
    }
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        payload = root / "input.json"
        output = root / "report.pdf"
        data = {"records": [record], "filters": {"groups": ()},
                "summary": "Essai", "warnings": [], "include_photos": False,
                "include_maps": True, "map_background": "epure",
                "report_kind": "synthetic"}
        payload.write_text(json.dumps(data), encoding="utf-8")
        if sys.platform == "win32":
            prefix = QgsApplication.prefixPath() or os.environ.get("QGIS_PREFIX_PATH", "")
            program = select_python(prefix)
            environment = worker_environment(prefix, program)
        else:
            program = sys.executable
            environment = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        result = subprocess.run([program, str(WORKER), str(payload), str(output)],
                                env=environment, capture_output=True, text=True, timeout=90)
        assert result.returncode == 0, result.stderr + result.stdout
        updates = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        font_diagnostics = [item["font_diagnostic"] for item in updates
                            if "font_diagnostic" in item]
        assert len(font_diagnostics) == 1
        assert any(family.split(" [", 1)[0].casefold() ==
                   font_diagnostics[0]["selected"].split(" [", 1)[0].casefold()
                   for family in font_diagnostics[0]["available_families"])
        assert font_diagnostics[0]["platform"] == environment["QT_QPA_PLATFORM"]
        assert any(item.get("current") == 1 and item.get("total") == 1 for item in updates)
        stages = [item["stage"] for item in updates if "stage" in item]
        assert "Rendu cartographique" in stages
        assert any(stage.startswith("Rendu cartographique et export PDF — lot 1/1")
                   for stage in stages)
        assert stages[-1] == "Finalisation du document"
        assert updates[-1]["done"] >= 1
        assert output.is_file() and output.stat().st_size > 1000
        if shutil.which("pdfinfo"):
            info = subprocess.check_output(["pdfinfo", str(output)], text=True)
            assert "595 x 842 pts (A4)" in info
        pdf_bytes = output.read_bytes()
        assert b"/Type /Font" in pdf_bytes, "Le PDF ne contient aucun objet de police"
        assert b"/ToUnicode" in pdf_bytes, "Le PDF ne contient aucune table Unicode"
        assert Path(updates[0]["python"]).resolve() == Path(program).resolve()
        if shutil.which("pdftotext"):
            visible = subprocess.check_output(["pdftotext", "-layout", str(output), "-"]).decode()
            visible = visible.replace("ﬁ", "fi")
            for value in ("Registre cartographique des prestations",
                          "Béthune", "© IGN - Géoplateforme (Plan Épuré)",
                          "Planifié", "7 arbres"):
                assert value in visible, value
            assert "Essai d’export" in visible
            assert "Description interne cachée" not in visible
            assert "Photographies" not in visible
            assert visible.count("© IGN - Géoplateforme (Plan Épuré)") == 1
        data["records"] = []
        payload.write_text(json.dumps(data), encoding="utf-8")
        failed = subprocess.run([program, str(WORKER), str(payload),
                                 str(root / "invalid.pdf")], env=environment,
                                capture_output=True, text=True, timeout=90)
        assert failed.returncode != 0
        assert any("error" in json.loads(line) for line in failed.stdout.splitlines()
                   if line.startswith("{"))
        assert not (root / "invalid.pdf").exists()

        photo = root / "chantier.png"
        image = QImage(640, 320, QImage.Format_RGB32)
        image.fill(QColor("#416f91"))
        assert image.save(str(photo))
        record.update(
            own_wkt="POINT(700000 6600000)", has_geometry=True,
            photo_1=str(photo), photo_1_commentaire="Vue du chantier",
        )
        data.update(
            records=[record], include_maps=True, include_photos=False,
            report_kind="detailed",
        )
        payload.write_text(json.dumps(data), encoding="utf-8")
        mapped = root / "mapped.pdf"
        with_maps = subprocess.run(
            [program, str(WORKER), str(payload), str(mapped)],
            env=environment, capture_output=True, text=True, timeout=90,
        )
        assert with_maps.returncode == 0, with_maps.stderr + with_maps.stdout
        assert mapped.is_file() and mapped.stat().st_size > output.stat().st_size
        mapped_updates = [json.loads(line) for line in with_maps.stdout.splitlines()
                          if line.startswith("{")]
        mapped_stages = [item["stage"] for item in mapped_updates if "stage" in item]
        assert any(stage.startswith("Rendu cartographique et export PDF — lot 1/1")
                   for stage in mapped_stages)
        assert mapped_stages[-1] == "Finalisation du document"
        assert mapped_updates[-1]["done"] >= 1
        assert b"/Subtype /Image" in mapped.read_bytes()
        records = []
        for number in range(1, 13):
            entry = dict(record)
            entry["id"] = f"00000000-0000-4000-8000-{number:012d}"
            entry["intitule"] = f"Essai d’export {number:02d}"
            entry["photo_1"] = ""
            entry["photo_1_commentaire"] = ""
            records.append(entry)
        data.update(records=records, include_photos=False, include_maps=True,
                    report_kind="detailed")
        payload.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        registry = root / "registre_12_pages.pdf"
        registry_result = subprocess.run(
            [program, str(WORKER), str(payload), str(registry)],
            env=environment, capture_output=True, text=True, timeout=180)
        assert registry_result.returncode == 0, registry_result.stderr + registry_result.stdout
        registry_updates = [json.loads(line) for line in registry_result.stdout.splitlines()
                            if line.startswith("{")]
        assert registry_updates[-1]["done"] == 12, registry_updates[-1]
        assert b"/FontFile" in registry.read_bytes(), "Aucune police incorporée au registre"
        extractor = shutil.which("pdftotext")
        if extractor:
            readable = subprocess.check_output(
                [extractor, "-enc", "UTF-8", "-layout", str(registry), "-"]).decode("utf-8")
            pages = [page for page in readable.split("\f") if page.strip()]
            assert len(pages) == 12, len(pages)
            assert readable.count("LOCALISATION") == 12
            for number, page in enumerate(pages, 1):
                assert "Rapport de prestations — GEMAPI-App" in page, number
                assert f"Page {number} / 12" in page, number
        else:
            print("pdftotext absent : extraction à vérifier lors de la recette Windows")
    print("Moteur PDF isolé : progression, PDF valide et erreur sans fichier partiel OK")


if __name__ == "__main__":
    main()
