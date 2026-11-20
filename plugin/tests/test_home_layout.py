"""Compact home geometry, native fonts and action routing under actual PyQGIS."""
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from qgis.PyQt.QtCore import QEvent, QPoint, QRect, Qt
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QAction, QApplication, QMainWindow, QToolBar, QStyleFactory
from qgis.core import QgsApplication
from qgis.gui import QgsMapCanvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app import classFactory

BUTTONS = (("createButton", "Créer une prestation", "show_creation"),
           ("manageButton", "Gérer les prestations", "show_management"),
           ("reportButton", "Éditer un rapport", "show_report"),
           ("assistantButton", "Assistant IA", "show_assistant"),
           ("helpButton", "Aide", "show_help"))


class Interface:
    def __init__(self):
        self.window = QMainWindow()
        self.canvas = QgsMapCanvas(self.window)
        self.window.setCentralWidget(self.canvas)
        self.window.resize(600, 420)
        self.window.move(60, 70)
        self.window.show()
    def mainWindow(self): return self.window
    def mapCanvas(self): return self.canvas
    def addPluginToMenu(self, *_): pass
    def removePluginMenu(self, *_): pass


class HomeLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication([], True)
        cls.app.initQgis()
    @classmethod
    def tearDownClass(cls): cls.app.exitQgis()

    def setUp(self):
        self.iface = Interface()
        self.plugin = classFactory(self.iface)
        self.plugin.initGui()
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(self.plugin.session, 'connection', return_value=object()))
        self.stack.enter_context(patch('gemapi_app.plugin.prestation_permissions', return_value={'insert': True}))
    def tearDown(self):
        self.plugin.unload()
        self.stack.close()
        self.iface.window.close()
        self.iface.window.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)

    def test_compact_single_column_preserves_fonts_buttons_and_actions(self):
        actions = {action: self.stack.enter_context(patch.object(self.plugin, action)) for _, _, action in BUTTONS}
        self.plugin.show_dialog()
        self.app.processEvents()
        home = self.plugin.home
        self.assertFalse(home.isWindow())
        self.assertIs(home.parentWidget(), self.iface.canvas)
        self.assertNotIn(home, QApplication.topLevelWidgets())
        self.assertEqual(home.windowModality(), Qt.NonModal)
        longest = 0
        heights = 0
        for row, (name, text, action) in enumerate(BUTTONS):
            button = getattr(home, name)
            self.assertIs(home.actionsLayout.itemAtPosition(row, 0).widget(), button)
            self.assertEqual(button.text(), text)
            self.assertEqual(button.height(), 31)
            self.assertEqual(button.font().pointSizeF(), self.iface.window.font().pointSizeF())
            longest = max(longest, button.sizeHint().width())
            heights += button.height()
            self.assertEqual(button.width(), home.createButton.width())
            button.click()
            actions[action].assert_called_once()
        self.assertLessEqual(home.width(), longest + 24)
        self.assertLessEqual(home.height(), heights + 32)
        self.assertEqual(home.actionsLayout.columnCount(), 1)

    def test_top_right_repositions_after_resize_and_move(self):
        self.plugin.show_dialog()
        self.app.processEvents()
        for width, height, x, y in ((600, 420, 60, 70), (650, 450, 30, 40), (550, 400, 90, 50)):
            self.iface.window.resize(width, height)
            self.iface.window.move(x, y)
            self.app.processEvents()
            QTest.qWait(30)
            frame = self.plugin.home.frameGeometry()
            corner = QPoint(self.iface.canvas.width(), 0)
            self.assertLessEqual(abs(frame.right() - (corner.x() - 11)), 2)
            self.assertLessEqual(abs(frame.top() - (corner.y() + 10)), 2)
            self.assertTrue(self.iface.canvas.rect().contains(frame))

    def test_overlay_follows_parent_and_does_not_intercept_other_map_points(self):
        self.plugin.show_dialog()
        self.app.processEvents()
        home = self.plugin.home
        for origin in (QPoint(-900, 20), QPoint(20, 40)):
            self.iface.window.move(origin)
            self.app.processEvents()
            self.assertTrue(self.iface.canvas.rect().contains(home.geometry()))
            child = self.iface.canvas.childAt(home.geometry().center())
            self.assertTrue(child is home or home.isAncestorOf(child))
            outside = self.iface.canvas.childAt(QPoint(10, self.iface.canvas.height() - 10))
            self.assertTrue(outside is None or (outside is not home and not home.isAncestorOf(outside)))
            self.assertFalse(home.windowFlags() & Qt.Window)
    def test_toolbar_toggle_preserves_session_and_matches_real_visibility(self):
        plugin = self.plugin
        session = plugin.session
        session._values['reference.keep'] = marker = object()
        self.assertTrue(plugin.action.isCheckable())
        self.assertFalse(plugin.action.isChecked())
        plugin.action.trigger()
        self.app.processEvents()
        home = plugin.home
        self.assertTrue(home.isVisible())
        self.assertTrue(plugin.action.isChecked())
        button = plugin.toolbar.widgetForAction(plugin.action)
        original_style = self.app.style().objectName()
        try:
            for style in QStyleFactory.keys():
                self.app.setStyle(style)
                self.app.processEvents()
                self.assertTrue(button.isCheckable() and button.isChecked(), style)
                checked_image = button.grab().toImage()
                plugin.action.trigger()
                self.app.processEvents()
                self.assertFalse(home.isVisible())
                self.assertFalse(plugin.action.isChecked())
                self.assertFalse(button.isChecked(), style)
                self.assertNotEqual(button.grab().toImage(), checked_image, style)
                self.assertIs(plugin.session, session)
                self.assertIs(session._values['reference.keep'], marker)
                plugin.action.trigger()
                self.app.processEvents()
                self.assertIs(plugin.home, home)
                self.assertTrue(home.isVisible())
        finally:
            self.app.setStyle(original_style)
        home.hide()
        self.app.processEvents()
        self.assertFalse(plugin.action.isChecked())
        home.show()
        self.app.processEvents()
        self.assertTrue(plugin.action.isChecked())


    def test_standard_action_and_home_reuse_conversation_on_shared_toolbar(self):
        # A peer action represents any independent plugin sharing the toolbar.
        iface = Interface()
        toolbar = QToolBar("SIG-Milieux", iface.window)
        toolbar.setObjectName("SIGMilieuxToolbar")
        iface.window.addToolBar(toolbar)
        stable_action = QAction("SIG-Prestations", iface.window)
        toolbar.addAction(stable_action)
        plugin = classFactory(iface)
        try:
            plugin.initGui()
            action = plugin.action
            self.assertFalse(action.icon().isNull())
            self.assertIs(plugin.toolbar, toolbar)
            self.assertEqual(len(toolbar.actions()), 2)
            plugin.initGui()
            self.assertIs(plugin.action, action)
            self.assertEqual(toolbar.actions().count(action), 1)
            self.assertEqual(len(iface.window.findChildren(QToolBar, "SIGMilieuxToolbar")), 1)
            with patch.object(plugin.session, "connection", return_value=object()), patch(
                    "gemapi_app.plugin.prestation_permissions", return_value={"insert": True}):
                action.trigger()
            self.assertTrue(plugin.home.isVisible())
            self.assertTrue(action.isChecked())
            plugin.home.assistantButton.click()
            assistant = plugin.assistant
            self.assertIsNotNone(assistant)
            self.assertTrue(assistant.isVisible())
            self.assertFalse(plugin.home.isVisible())
            assistant._append("Vous", "Conversation conservée entre les deux accès.")
            assistant.hide()
            with patch.object(plugin.session, "connection", return_value=object()), patch(
                    "gemapi_app.plugin.prestation_permissions", return_value={"insert": True}):
                plugin.show_dialog()
                plugin.home.assistantButton.click()
            self.assertIs(plugin.assistant, assistant)
            self.assertIn("Conversation conservée", assistant.history.toPlainText())
            action.trigger()
            self.assertFalse(assistant.isVisible())
            self.assertFalse(action.isChecked())
            action.trigger()
            self.assertTrue(assistant.isVisible())
            self.assertIs(plugin.assistant, assistant)
            self.assertEqual(len(toolbar.actions()), 2)
            plugin.unload()
            plugin.unload()
            self.assertNotIn(action, toolbar.actions())
            self.assertEqual(toolbar.actions(), [stable_action])
            self.assertIs(iface.window.findChild(QToolBar, "SIGMilieuxToolbar"), toolbar)
            # Re-enable the standard plugin while the other plugins remain loaded.
            plugin = classFactory(iface)
            plugin.initGui()
            self.assertEqual(len(toolbar.actions()), 2)
        finally:
            plugin.unload()
            self.assertEqual(toolbar.actions(), [stable_action])
            iface.window.close()
            iface.window.deleteLater()

    def test_empty_toolbar_is_removed_on_unload_without_duplicates(self):
        iface = Interface()
        plugin = classFactory(iface)
        plugin.initGui()
        plugin.initGui()
        self.assertEqual(plugin.toolbar.actions(), [plugin.action])
        plugin.unload()
        plugin.unload()
        self.assertIsNone(iface.window.findChild(QToolBar, "SIGMilieuxToolbar"))
        iface.window.deleteLater()


if __name__ == '__main__': unittest.main()
