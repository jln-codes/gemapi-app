"""Portrait detailed PDF: page format, business fields, maps and real photos."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QImage, QImageReader
from qgis.core import QgsApplication, QgsLayoutItemLabel, QgsLayoutItemPicture

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.report_data import resolve_report_editor
from gemapi_app.session_data import connection_login
from gemapi_app.report_pdf import export_detailed_report, _restore_qgis_pdf_metadata


class DetailedReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication([], True)
        cls.app.initQgis()

    @classmethod
    def tearDownClass(cls):
        cls.app.exitQgis()

    def test_editor_uses_login_not_record_technician(self):
        class Connection:
            def executeSql(self, sql):
                if sql == "SELECT current_user::text":
                    return [["report_editor"]]
                self.query = sql
                return [["Alice Dupont"]]
        connection = Connection()
        self.assertEqual(resolve_report_editor(connection), ("report_editor", "Alice Dupont"))
        self.assertIn("lower(login)", connection.query)
        self.assertIn("report_editor", connection.query)

    def test_editor_uses_configured_postgres_login_and_explicit_fallback(self):
        class Connection:
            def executeSql(self, sql):
                if sql == "SELECT current_user::text":
                    return [["postgres"]]
                if "postgres.zejhfmmupakuowqoywpx" in sql:
                    return [["Julien Dubois"]]
                return []
        connection = Connection()
        self.assertEqual(resolve_report_editor(
            connection, "postgres.zejhfmmupakuowqoywpx"),
            ("postgres.zejhfmmupakuowqoywpx", "Julien Dubois"))
        self.assertEqual(resolve_report_editor(connection, "autre.compte"),
                         ("autre.compte", None))
        self.assertEqual(resolve_report_editor(connection), ("postgres", None))

    def test_connection_login_comes_from_project_uri(self):
        class Layer:
            def isValid(self): return True
            def providerType(self): return "postgres"
            def source(self):
                return ("dbname='postgres' host=localhost user='postgres.exemple' "
                        "key='id' srid=3950 type=Geometry table=\"milieux\".\"prestations\" (geom)")
        class Project:
            def mapLayers(self): return {"one": Layer()}
        self.assertEqual(connection_login(Project()), "postgres.exemple")

    def test_photo_section_is_always_built(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "autre_projet.qgz"
            project.touch()
            photos = root / "photos" / "2026"
            photos.mkdir(parents=True)
            for name in ("Vue été 1.png", "Vue été 2.png"):
                image = QImage(80, 60, QImage.Format_RGB32)
                image.fill(QColor("#56789a"))
                self.assertTrue(image.save(str(photos / name)))
            base = {"id": "11111111-1111-4111-8111-111111111111",
                    "intitule": "Fiche photo", "type": "Test", "statut": "Terminé",
                    "technician": "Technicien", "provider": "Prestataire",
                    "communes": "Commune", "reference_geometries": [],
                    "own_wkt": None, "photo_1": None, "photo_2": ""}
            cases = ((None, "", 0, "Aucune photographie associée"),
                     ("photos/2026/Vue été 1.png", "", 1, "Vue 1"),
                     ("photos/2026/Vue été 1.png", "photos\\2026\\Vue été 2.png", 2, "Vue 2"),
                     ("photos/2026/introuvable.png", "", 0, "Photographie indisponible"))
            with patch.dict(os.environ, {"SIG_PRESTATIONS_PROJECT_FILE": str(project)}):
                for first, second, expected_images, expected_text in cases:
                    with self.subTest(first=first, second=second):
                        layouts = []
                        record = dict(base, photo_1=first, photo_2=second,
                                      photo_1_commentaire="Vue 1",
                                      photo_2_commentaire="Vue 2")
                        pages = export_detailed_report(
                            [record], root / "unused.pdf", include_photos=False,
                            _shared_basemap=None,
                            _layout_sink=lambda layout, *_: layouts.append(layout))
                        self.assertEqual(pages, 1)
                        labels = [item.text() for item in layouts[0].items()
                                  if isinstance(item, QgsLayoutItemLabel)]
                        pictures = [item for item in layouts[0].items()
                                    if isinstance(item, QgsLayoutItemPicture)
                                    and Path(item.picturePath()).name.startswith("Vue été")]
                        self.assertIn("PHOTOGRAPHIES", labels)
                        self.assertIn(expected_text, labels)
                        self.assertNotIn("Photographies non demandées", labels)
                        self.assertEqual(len(pictures), expected_images)
                        if first:
                            self.assertNotIn("Aucune photographie associée", labels)
                layouts = []
                records = [dict(base, id=f"11111111-1111-4111-8111-{n:012d}",
                                photo_1="photos/2026/Vue été 1.png" if n == 2 else None)
                           for n in (1, 2)]
                pages = export_detailed_report(
                    records, root / "unused.pdf", include_photos=False,
                    _shared_basemap=None,
                    _layout_sink=lambda layout, *_: layouts.append(layout))
                self.assertEqual(pages, 2)
                labels = [item.text() for item in layouts[0].items()
                          if isinstance(item, QgsLayoutItemLabel)]
                self.assertEqual(labels.count("PHOTOGRAPHIES"), 2)
                self.assertEqual(labels.count("Aucune photographie associée"), 1)

    def test_parent_measure_and_description_share_existing_card_space(self):
        record = {
            "id": "11111111-1111-4111-8111-111111111111",
            "intitule": "Mesure de zone", "type": "Test", "statut": "Terminé",
            "technician": "Technicien", "provider": "Prestataire",
            "communes": "Commune", "quantite": 7, "unite": "arbres",
            "description": "Description courte du contrôle.",
            "objects": "vegetation : Zone fictive", "site_child_area": 1250,
            "reference_geometries": [], "own_wkt": None,
            "photo_1": None, "photo_2": None,
        }
        with tempfile.TemporaryDirectory() as directory:
            for reference_measures in (
                    None,
                    "Cours d'eau : 450,0 m ; Digue de contrôle : 120,0 m ; "
                    "Ouvrage hydraulique : 87,5 m²"):
                with self.subTest(reference_measures=reference_measures):
                    layouts = []
                    current = dict(record, reference_measures=reference_measures)
                    pages = export_detailed_report(
                        [current], Path(directory) / "unused.pdf",
                        _shared_basemap=None,
                        _layout_sink=lambda layout, *_: layouts.append(layout))
                    self.assertEqual(pages, 1)
                    labels = [item for item in layouts[0].items()
                              if isinstance(item, QgsLayoutItemLabel)]
                    by_text = {item.text(): item for item in labels}
                    measure = "Surface du patrimoine (géométrie parente) : 1 250,0 m²"
                    self.assertIn(measure, " ".join(by_text))
                    self.assertEqual(by_text["7 arbres"].pos().y(),
                                     by_text["Quantité déclarée"].pos().y())
                    self.assertEqual(by_text["Description"].pos().y(),
                                     by_text[record["description"]].pos().y())
                    attachment = next(item for item in labels
                                      if item.text().startswith("Rattachement :"))
                    self.assertGreater(attachment.pos().y(),
                                       by_text["Description"].pos().y())
                    if reference_measures:
                        self.assertIn("Réf. patrimoniale", " ".join(by_text))
                        self.assertGreater(by_text["Description"].pos().y(),
                                           by_text["Mesures"].pos().y() + 7)

    def test_zero_one_two_photos_and_long_text(self):
        if not shutil.which("pdfinfo") or not shutil.which("pdftotext"):
            self.skipTest("Poppler absent")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photos = []
            for n in (1, 2):
                path = root / f"photo{n}.png"
                image = QImage(600, 400, QImage.Format_RGB32)
                image.fill(QColor("#56789a" if n == 1 else "#9a7856"))
                self.assertTrue(image.save(str(path)))
                photos.append(path)
            record = {
                "id": "11111111-1111-1111-1111-111111111111",
                "intitule": "Prestation de test", "date_debut": "2026-01-01",
                "date_fin": "2026-01-15", "type": "Restauration écologique", "statut": "Terminé",
                "position": "Talus côté rivière / stockage",
                "provider": "Entreprise A", "technician": "Responsable différent",
                "quantite": 3, "unite": "arbres", "communes": "Commune A",
                "description": "Description métier complète", "objects": "Cible A",
                "has_geometry": True, "own_length": None, "own_area": None,
                "reference_measures": None, "own_wkt": "POINT(700000 6600000)",
                "reference_geometries": [], "photo_1": "", "photo_2": "",
            }
            with patch("gemapi_app.report_pdf.background", return_value=None):
                for count in (0, 1, 2):
                    current = dict(record, photo_1=str(photos[0]) if count >= 1 else "",
                                   photo_2=str(photos[1]) if count == 2 else "")
                    path = root / f"detailed-{count}.pdf"
                    self.assertEqual(export_detailed_report(
                        [current], path, include_photos=False if count == 2 else True,
                        editor_login="report_editor", editor_name="Alice Dupont"), 1)
                    info = subprocess.check_output(["pdfinfo", str(path)], text=True)
                    self.assertIn("Pages:           1", info)
                    self.assertIn("Page size:       595 x 842 pts (A4)", info)
                    text = subprocess.check_output(
                        ["pdftotext", "-layout", str(path), "-"], text=True)
                    text = text.replace("ﬀ", "ff").replace("ﬁ", "fi")
                    for value in ("Rapport de prestations — GEMAPI-App", "Alice Dupont",
                                  "Responsable différent", "Description métier complète",
                                  "Cible A", "Quantité déclarée", "3 arbres", "LOCALISATION"):
                        self.assertIn(value, text)
                    self.assertIn("Position : Talus côté rivière / stockage", text)
                    self.assertNotIn("Photo 1", text)
                    self.assertEqual("Aucune photographie associée" in text, count == 0)
                    self.assertIn("PHOTOGRAPHIES", text)
                    self.assertNotIn("Photographies non demandées", text)
                    if count:
                        images = subprocess.check_output(
                            ["pdfimages", "-list", str(path)], text=True)
                        self.assertGreaterEqual(images.count("image"), count + 1)
                missing = dict(record, photo_1=r"J:\photos\absente.jpg",
                               photo_1_commentaire="photo aléatoire distante",
                               photo_2="")
                unavailable_pdf = root / "unavailable.pdf"
                self.assertEqual(export_detailed_report(
                    [missing], unavailable_pdf, include_photos=True,
                    editor_name="Alice Dupont"), 1)
                unavailable_text = subprocess.check_output(
                    ["pdftotext", "-layout", str(unavailable_pdf), "-"], text=True)
                self.assertIn("Photographie indisponible", unavailable_text)
                self.assertIn("photo aléatoire distante", unavailable_text)
                self.assertIn("absente.jpg", unavailable_text)
                self.assertNotIn("Aucune photographie associée", unavailable_text)
                project = root / "autre_projet.qgz"
                project.touch()
                relative_photo = root / "photos" / "2026" / "Vue été.png"
                relative_photo.parent.mkdir(parents=True)
                shutil.copyfile(photos[0], relative_photo)
                relative_record = dict(record, photo_1="photos/2026/Vue été.png",
                                       photo_1_commentaire="Vue relative")
                with patch.dict(os.environ, {"SIG_PRESTATIONS_PROJECT_FILE": str(project)}):
                    relative_pdf = root / "relative.pdf"
                    export_detailed_report([relative_record], relative_pdf)
                relative_text = subprocess.check_output(
                    ["pdftotext", "-layout", str(relative_pdf), "-"], text=True)
                self.assertIn("Vue relative", relative_text)
                self.assertNotIn("Photographie indisponible", relative_text)
                self.assertIn("image", subprocess.check_output(
                    ["pdfimages", "-list", str(relative_pdf)], text=True))
                unknown = root / "unresolved-editor.pdf"
                export_detailed_report([record], unknown, include_photos=False,
                                       editor_login="compte.inconnu", editor_name=None)
                unknown_text = subprocess.check_output(
                    ["pdftotext", "-layout", str(unknown), "-"], text=True)
                self.assertIn("identité non résolue (login : compte.inconnu)", unknown_text)
                long_record = dict(record, description="Description étendue " * 80,
                                   photo_1=str(photos[0]),
                                   photo_1_commentaire="Légende longue " * 20)
                self.assertGreaterEqual(export_detailed_report(
                    [long_record], root / "long.pdf", include_photos=True), 2)
                long_text = subprocess.check_output(
                    ["pdftotext", "-layout", str(root / "long.pdf"), "-"], text=True)
                self.assertIn("Description étendue", long_text)
                self.assertNotIn("Description complète en page suivante", long_text)
                self.assertIn("Légende photographie 1", long_text)

    def test_photo_slots_center_images_and_follow_with_captions(self):
        photos = Path(__file__).resolve().parents[2] / "demo/photos"
        with tempfile.TemporaryDirectory() as directory:
            small = Path(directory) / "petite.png"
            image = QImage(60, 40, QImage.Format_RGB32)
            image.fill(QColor("#477a64"))
            self.assertTrue(image.save(str(small)))
            for name in ("photo_4x3.jpg", "photo_3x4.jpg", "photo_16x9.jpg",
                         "photo_9x16.jpg", "photo_1x1.jpg", str(small)):
                with self.subTest(photo=name):
                    path = Path(name) if Path(name).is_absolute() else photos / name
                    record = {
                        "id": "11111111-1111-4111-8111-000000000001",
                        "intitule": "Entretien des berges", "date_debut": "2026-01-01",
                        "date_fin": "2026-01-15", "type": "Entretien", "statut": "Terminé",
                        "provider": "Entreprise A", "technician": "Technicien B",
                        "quantite": 1, "unite": "intervention", "communes": "Commune A",
                        "description": "Entretien courant", "objects": "", "has_geometry": True,
                        "own_length": None, "own_area": None,
                        "own_wkt": "POINT(700000 6600000)", "reference_geometries": [],
                        "photo_1": str(path), "photo_1_commentaire": "Vue des berges",
                        "photo_2": None,
                    }
                    captured = []
                    with patch("gemapi_app.report_pdf.background", return_value=None):
                        export_detailed_report(
                            [record], Path(directory) / "unused.pdf", include_photos=True,
                            _layout_sink=lambda layout, *_: captured.append(layout))
                    layout = captured[0]
                    picture = next(item for item in layout.items()
                                   if isinstance(item, QgsLayoutItemPicture)
                                   and item.picturePath() == str(path))
                    position = picture.positionWithUnits()
                    size = picture.sizeWithUnits()
                    pixels = QImageReader(str(path)).size()
                    self.assertAlmostEqual(position.x() + size.width() / 2, 56.5, places=2)
                    self.assertAlmostEqual(position.y() + size.height() / 2, 243, places=2)
                    self.assertAlmostEqual(size.width() / size.height(),
                                           pixels.width() / pixels.height(), places=2)
                    self.assertLessEqual(size.width(), 93.01)
                    self.assertLessEqual(size.height(), 70.01)
                    self.assertLessEqual(size.width(), pixels.width() * 25.4 / 150 + .01)
                    self.assertFalse(picture.frameEnabled())
                    caption = next(item for item in layout.items()
                                   if isinstance(item, QgsLayoutItemLabel)
                                   and item.text() == "Vue des berges")
                    self.assertEqual(caption.hAlign(), Qt.AlignHCenter)
                    self.assertAlmostEqual(caption.positionWithUnits().y(),
                                           position.y() + size.height() + 1, places=2)

    def test_batched_export_keeps_global_page_numbers_and_photos(self):
        if not shutil.which("pdfinfo") or not shutil.which("pdftotext"):
            self.skipTest("Poppler absent")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            photo = root / "photo.png"
            image = QImage(600, 400, QImage.Format_RGB32)
            image.fill(QColor("#56789a"))
            self.assertTrue(image.save(str(photo)))
            records = []
            for number in range(1, 13):
                records.append({
                    "id": f"11111111-1111-4111-8111-{number:012d}",
                    "intitule": f"Intervention {number:02d}",
                    "date_debut": "2026-01-01", "date_fin": "2026-01-15",
                    "type": "Entretien", "statut": "Terminé",
                    "provider": "Entreprise A", "technician": "Technicien B",
                    "quantite": 1, "unite": "intervention", "communes": "Commune A",
                    "description": "Description étendue " * 80 if number == 1 else "Entretien courant",
                    "objects": "", "has_geometry": True,
                    "own_length": None, "own_area": None,
                    "own_wkt": f"POINT({700000 + number} 6600000)",
                    "reference_geometries": [],
                    "photo_1": str(photo) if number in (2, 11) else "",
                    "photo_1_commentaire": "Vue 1",
                    "photo_2": str(photo) if number == 11 else "",
                    "photo_2_commentaire": "Vue 2",
                })
            path = root / "batched.pdf"
            stages = []
            with patch("gemapi_app.report_pdf.background", return_value=None):
                pages = export_detailed_report(
                    records, path, include_photos=True, editor_name="Alice Dupont",
                    progress=lambda stage, current, total: stages.append((stage, current, total)))
            self.assertGreater(pages, 12)
            info = subprocess.check_output(["pdfinfo", str(path)], text=True)
            self.assertIn(f"Pages:           {pages}", info)
            _restore_qgis_pdf_metadata(path)
            info = subprocess.check_output(["pdfinfo", str(path)], text=True)
            self.assertIn("Creator:         QGIS ", info)
            self.assertIn("Producer:        QGIS ", info)
            text = subprocess.check_output(
                ["pdftotext", "-layout", str(path), "-"], text=True,
                stderr=subprocess.DEVNULL)
            text = text.replace("ﬁ", "fi")
            self.assertEqual(text.count("Rapport de prestations — GEMAPI-App"), 12)
            for number in range(1, pages + 1):
                self.assertIn(f"Page {number} / {pages}", text)
            for number in range(1, 13):
                self.assertIn(f"Intervention {number:02d}", text)
            self.assertIn("Vue 1", text)
            self.assertIn("Vue 2", text)
            batches = [(stage, current, total) for stage, current, total in stages
                       if stage.startswith("Rendu cartographique et export PDF")]
            self.assertEqual([(current, total) for _, current, total in batches],
                             [(0, 2), (1, 2), (2, 2)])
            self.assertIn("lot 1/2", batches[0][0])
            self.assertIn("lot 2/2", batches[1][0])
            self.assertIn("pages", batches[0][0])
            self.assertEqual(stages[-1][0], "Finalisation du document")


if __name__ == "__main__":
    unittest.main()
