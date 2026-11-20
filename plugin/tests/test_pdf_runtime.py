"""Interpreter selection for the QGIS PDF worker, without PyQGIS or Docker."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.pdf_runtime import select_python, worker_environment


class PdfRuntimeTests(unittest.TestCase):
    def test_windows_uses_current_qgis_installation_not_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "QGIS"
            prefix = root / "apps/qgis-ltr"
            prefix.mkdir(parents=True)
            (prefix / "python").mkdir()
            (root / "apps/Python312").mkdir()
            (root / "bin").mkdir()
            bundled = root / "bin/python3.exe"
            bundled.touch()
            unrelated = Path(directory) / "foreign/python.exe"
            unrelated.parent.mkdir()
            unrelated.touch()
            environment = {
                "PATH": str(unrelated.parent),
                "PYTHONEXECUTABLE": str(unrelated),
                "PYTHONHOME": str(unrelated.parent),
                "PYTHONPATH": str(unrelated.parent),
            }
            selected = select_python(
                str(prefix), environment=environment,
                executable=str(root / "bin/qgis-ltr-bin.exe"),
                platform="win32",
            )
            self.assertEqual(Path(selected), bundled)
            worker = worker_environment(
                str(prefix), selected, environment=environment, platform="win32"
            )
            self.assertEqual(worker["QT_QPA_PLATFORM"], "windows")
            self.assertEqual(Path(worker["PYTHONHOME"]), root / "apps/Python312")
            self.assertEqual(worker["QGIS_PREFIX_PATH"], str(prefix))
            self.assertEqual(worker["PYTHONEXECUTABLE"], str(bundled))
            self.assertTrue(worker["PYTHONPATH"].startswith(str(prefix / "python")))
            self.assertNotIn(str(unrelated.parent), worker["PYTHONPATH"])
            self.assertTrue(worker["PATH"].startswith(str(prefix / "bin")))

    def test_unix_uses_current_python_without_path_search(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "qgis"
            prefix.mkdir()
            current = Path(directory) / "bin/python3"
            current.parent.mkdir()
            current.touch()
            selected = select_python(
                str(prefix), environment={"PATH": "/unrelated"},
                executable=str(current), platform="linux",
            )
            self.assertEqual(selected, str(current))
            worker = worker_environment(
                str(prefix), selected, environment={"PATH": "/unrelated"},
                platform="linux",
            )
            self.assertEqual(worker["PATH"], "/unrelated")
            self.assertEqual(worker["QT_QPA_PLATFORM"], "offscreen")

    def test_missing_python_reports_qgis_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix = Path(directory) / "apps/qgis-ltr"
            prefix.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "installation QGIS Windows"):
                select_python(
                    str(prefix), environment={"PATH": "/foreign"},
                    executable=str(Path(directory) / "bin/qgis-ltr-bin.exe"),
                    platform="win32",
                )

    def test_override_remains_a_diagnostic_option(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostic-python"
            path.touch()
            self.assertEqual(
                select_python(
                    "", environment={"SIG_PRESTATIONS_PYTHON": str(path)},
                    executable="/missing/qgis", platform="linux",
                ),
                str(path),
            )
            with self.assertRaisesRegex(ValueError, "diagnostic"):
                select_python(
                    "", environment={"SIG_PRESTATIONS_PYTHON": str(path) + ".missing"},
                    executable="/missing/qgis", platform="linux",
                )


if __name__ == "__main__":
    unittest.main()
