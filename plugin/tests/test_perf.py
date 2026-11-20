"""Safe timing traces, portable audit launchers and SQL NULL equivalence."""

import sys
import os
import ast
import runpy
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app import perf  # noqa: E402


class FakeConnection:
    def executeSql(self, _sql):
        return [[1], [2]]


class FakeMetadata:
    def createConnection(self, _info, _options):
        return FakeConnection()


class PerfTests(unittest.TestCase):
    def test_nested_spans_and_safe_query_trace(self):
        messages = []
        with patch.object(perf, "ENABLED", True), patch.object(perf, "_log", messages.append):
            with perf.measure("parent"):
                with perf.measure("child"):
                    connection = perf.connect(FakeMetadata(), "secret connection")
                    self.assertEqual(connection.executeSql("SELECT 'private prestation'"), [[1], [2]])
        self.assertEqual(len(messages), 4)
        self.assertIn("rows=2", messages[1])
        for message in messages[2:]:
            self.assertIn("queries=1 connections=1", message)
        self.assertNotIn("private prestation", " ".join(messages))
        self.assertNotIn("secret connection", " ".join(messages))

    def test_disabled_connection_has_no_proxy(self):
        with patch.object(perf, "ENABLED", False):
            self.assertIsInstance(perf.connect(FakeMetadata(), "connection"), FakeConnection)


class PerfLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audits = Path(__file__).resolve().parents[2] / "audits"
        cls.probe = runpy.run_path(str(cls.audits / "PERF-QGIS-02-probe.py"))

    def test_ubuntu_launchers(self):
        desktop, python = self.probe["qgis_launchers"]("posix")
        self.assertEqual(desktop, Path("/usr/bin/qgis"))
        self.assertEqual(python, Path("/usr/bin/python3"))

    def test_windows_reference_launchers(self):
        with patch.dict(os.environ, {"ProgramFiles": r"C:\Program Files"}):
            desktop, python = self.probe["qgis_launchers"]("nt")
        directory = PureWindowsPath(r"C:\Program Files\QGIS 3.44.13\bin")
        self.assertEqual(PureWindowsPath(desktop), directory / "qgis-ltr-bin.exe")
        self.assertEqual(PureWindowsPath(python), directory / "python-qgis-ltr.bat")

    def test_later_launchers_use_same_detection(self):
        for name in ("PERF-QGIS-03B-probe.py", "PERF-QGIS-03C-local-recipe.py",
                     "PERF-QGIS-04-probe.py"):
            with self.subTest(script=name):
                probe = runpy.run_path(str(self.audits / name))
                self.assertEqual(probe["QGIS_DESKTOP"], self.probe["QGIS"])
                self.assertEqual(probe["QGIS_PY"], self.probe["QGIS_PY"])

    def test_provider_null_and_wrapper_none_are_the_same_relation_value(self):
        try:
            from qgis.core import QgsVariantUtils
            from qgis.PyQt.QtCore import QVariant
        except ImportError:
            self.skipTest("PyQGIS unavailable")
        # Load the pure predicate without launching the Desktop script's timer.
        tree = ast.parse((self.audits / "PERF-QGIS-04-desktop.py").read_text(encoding="utf-8"))
        definition = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                          and node.name == "relation_values_equal")
        namespace = {"QgsVariantUtils": QgsVariantUtils}
        exec(compile(ast.Module(body=[definition], type_ignores=[]), "relation_predicate", "exec"), namespace)
        equal = namespace["relation_values_equal"]
        self.assertTrue(equal(QVariant(), None))
        self.assertTrue(equal(None, QVariant()))
        uid = "00000000-0000-0000-0000-000000000001"
        self.assertTrue(equal(uid, uid))
        self.assertFalse(equal(QVariant(), uid))
        self.assertFalse(equal(uid, "00000000-0000-0000-0000-000000000002"))

    def test_disposable_project_uses_explicit_reader_without_password(self):
        source = "dbname='old' host=old port=5432 user='postgres' sslmode=require table=\"milieux\".\"prestations\" (geom)"
        root = ET.Element("qgis")
        layers = ET.SubElement(root, "projectlayers")
        pg = ET.SubElement(layers, "maplayer")
        ET.SubElement(pg, "provider").text = "postgres"
        ET.SubElement(pg, "datasource").text = source
        other = ET.SubElement(layers, "maplayer")
        ET.SubElement(other, "provider").text = "wms"
        ET.SubElement(other, "datasource").text = "url=https://example.invalid/tiles"
        tree = ET.SubElement(root, "layer-tree-group")
        ET.SubElement(tree, "layer-tree-layer", source=source)
        with tempfile.TemporaryDirectory(dir=self.audits) as folder:
            path = Path(folder) / "copy.qgz"
            with ZipFile(path, "w") as archive:
                archive.writestr("project.qgs", ET.tostring(root))
                archive.writestr("styles.qgd", b"unchanged style database")
            changed = self.probe["patch_account_copy"](
                path, {"utilisateur": "reader.demo"},
                {"hote": "db.demo.invalid", "port": "5432", "base": "postgres"})
            self.assertEqual(changed, 1)
            with ZipFile(path) as archive:
                result = ET.fromstring(archive.read("project.qgs"))
                self.assertEqual(archive.read("styles.qgd"), b"unchanged style database")
            uri = result.findtext("./projectlayers/maplayer/datasource")
            self.assertIn("user='reader.demo'", uri)
            self.assertIn("host='db.demo.invalid'", uri)
            self.assertNotIn("password=", uri)
            self.assertEqual(uri.partition(" table=")[2], source.partition(" table=")[2])
            self.assertEqual(result.find("./layer-tree-group/layer-tree-layer").get("source"), uri)
            self.assertEqual(result.findall("./projectlayers/maplayer")[1].findtext("datasource"),
                             "url=https://example.invalid/tiles")

    def test_official_project_connection_override_is_refused(self):
        with self.assertRaisesRegex(RuntimeError, "QGZ officiel"):
            self.probe["patch_account_copy"](self.probe["PROJECTS"]["demo"], {}, {})

    @unittest.skipIf(os.name == "nt", "Linux process inventory")
    def test_linux_process_inventory_does_not_read_command_arguments(self):
        messages = []
        function = self.probe["qgis_processes"]
        with patch.dict(function.__globals__, {"emit": messages.append}), \
             patch("subprocess.run", return_value=SimpleNamespace(
                 stdout="123 qgis 20\n456 bash 10\n789 qgis-bin 5\n")) as command:
            function()
        self.assertEqual(command.call_args.args[0], ["ps", "-eo", "pid=,comm=,etimes="])
        self.assertEqual([message["pid"] for message in messages], [123, 789])
        self.assertTrue(all(set(message) == {"kind", "pid", "created_utc"}
                            for message in messages))


if __name__ == "__main__":
    unittest.main()
