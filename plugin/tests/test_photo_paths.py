"""Photo references use the QGIS file directory on every platform."""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.photo_paths import project_root, reference_for, resolve_photo


class PhotoPathTests(unittest.TestCase):
    def test_project_photos_subfolders_and_moved_project(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first = base / "autre_projet"
            nested = first / "photos" / "2026" / "chantier"
            nested.mkdir(parents=True)
            project = first / "autre_projet.qgz"
            project.touch()
            image = nested / "Vue été 1.jpg"
            image.write_bytes(b"photo du projet")
            other = first / "photos" / "ailleurs" / image.name
            other.parent.mkdir()
            other.write_bytes(b"homonyme distinct")
            settings = {"SIG_PRESTATIONS_PROJECT_FILE": str(project),
                        "SIG_PRESTATIONS_PHOTOS_DIR": ""}
            with patch.dict(os.environ, settings):
                self.assertTrue(project_root().samefile(first))
                self.assertEqual(reference_for(image), "photos/2026/chantier/Vue été 1.jpg")
                for ref in ("photos/2026/chantier/Vue été 1.jpg",
                            r"photos\2026\chantier\Vue été 1.jpg"):
                    self.assertTrue(resolve_photo(ref).samefile(image))
                self.assertTrue(resolve_photo("photos/ailleurs/Vue été 1.jpg").samefile(other))
                self.assertIsNone(resolve_photo("photos/absente.jpg"))
                self.assertIsNone(resolve_photo("photos/2026/../../autre_projet.qgz"))
                self.assertIsNone(resolve_photo("photos/../autre_projet.qgz"))
                self.assertIsNone(resolve_photo(None))
                self.assertIsNone(resolve_photo(""))
                self.assertTrue(resolve_photo(str(image)).samefile(image))
                self.assertIsNone(resolve_photo(str(base / "introuvable.jpg")))

            moved = base / "deplace" / "autre_projet"
            moved.parent.mkdir()
            shutil.move(str(first), str(moved))
            with patch.dict(os.environ, {"SIG_PRESTATIONS_PROJECT_FILE": str(moved / project.name),
                                         "SIG_PRESTATIONS_PHOTOS_DIR": ""}):
                self.assertTrue(resolve_photo("photos/2026/chantier/Vue été 1.jpg")
                                .samefile(moved / "photos" / "2026" / "chantier" / image.name))
                self.assertIsNone(resolve_photo(str(image)))

    def test_unprefixed_legacy_reference_uses_only_configured_photo_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project_dir = base / "projet"
            (project_dir / "photos").mkdir(parents=True)
            project = project_dir / "projet.qgz"
            project.touch()
            local = project_dir / "photos" / "chantier" / "avant.jpg"
            local.parent.mkdir()
            local.write_bytes(b"locale")
            shared = base / "partage"
            (shared / "chantier").mkdir(parents=True)
            external = shared / "chantier" / "avant.jpg"
            external.write_bytes(b"partage")
            with patch.dict(os.environ, {"SIG_PRESTATIONS_PROJECT_FILE": str(project),
                                         "SIG_PRESTATIONS_PHOTOS_DIR": str(shared)}):
                self.assertTrue(resolve_photo("photos/chantier/avant.jpg").samefile(local))
                self.assertTrue(resolve_photo(r"chantier\avant.jpg").samefile(external))
                self.assertEqual(reference_for(local), "photos/chantier/avant.jpg")
                self.assertEqual(reference_for(external), str(external.resolve()))
                self.assertIsNone(resolve_photo("../hors-stockage.jpg"))
            with patch.dict(os.environ, {"SIG_PRESTATIONS_PROJECT_FILE": str(project),
                                         "SIG_PRESTATIONS_PHOTOS_DIR": ""}):
                self.assertTrue(resolve_photo("chantier/avant.jpg").samefile(local))
            with patch.dict(os.environ, {"SIG_PRESTATIONS_PROJECT_FILE": "",
                                         "SIG_PRESTATIONS_PHOTOS_DIR": ""}):
                self.assertIsNone(resolve_photo("photos/chantier/avant.jpg"))
                self.assertIsNone(resolve_photo("chantier/avant.jpg"))
                if os.name != "nt":
                    self.assertIsNone(resolve_photo(r"J:\photos\indisponible.jpg"))


if __name__ == "__main__":
    unittest.main()
