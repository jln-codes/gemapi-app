"""Exercise the hierarchy with Qt events and the actual fictitious reference."""
import sqlite3
import sys
from pathlib import Path
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QSizePolicy, QVBoxLayout, QWidget
from qgis.core import QgsApplication

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugin"))
from gemapi_app.type_picker import TypePicker


def check_popup_width(app, categories, types):
    window = QWidget()
    layout = QVBoxLayout(window)
    picker = TypePicker(window)
    picker.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
    layout.addWidget(picker)
    long_category = categories[0][1] * 15
    long_type = types[0][1] * 15
    picker.set_reference([(categories[0][0], long_category)],
                         [(types[0][0], long_type, categories[0][0], True)])
    window.show()
    for width in (180, 420, 150):
        window.resize(width, 100)
        app.processEvents()
        picker.showPopup()
        app.processEvents()
        assert picker.popup.width() == picker.width()
        assert picker.entries.item(0).toolTip() == long_category + "  ›"
        window.resize(width + 30, 100)
        app.processEvents()
        assert picker.popup.width() == picker.width()
        assert picker.entries.item(0).data(Qt.UserRole) == ("category", categories[0][0])
        picker._choose(picker.entries.item(0))
        app.processEvents()
        assert picker.popup.width() == picker.width()
        assert picker.entries.item(1).toolTip() == long_type
        assert picker.entries.textElideMode() == Qt.ElideRight
        assert picker.entries.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
        assert picker.entries.fontMetrics().horizontalAdvance(long_type) > picker.entries.viewport().width()
        # Resize the containing window while the types are still open.
        window.resize(width + 60, 100)
        app.processEvents()
        assert picker.popup.width() == picker.width()
        assert picker.entries.item(1).data(Qt.UserRole) == ("type", types[0][0])
        picker._choose(picker.entries.item(0))
        app.processEvents()
        assert picker.popup.width() == picker.width()
        picker.hidePopup()
    window.close()


def main():
    app = QgsApplication([], True)
    app.initQgis()
    try:
        with sqlite3.connect(ROOT / "demo/gpkg/referentiels.gpkg") as db:
            categories = db.execute("SELECT id,libelle FROM prestations_categorie ORDER BY ordre").fetchall()
            types = db.execute("SELECT id,libelle,categorie_id,actif FROM types_prestations ORDER BY libelle").fetchall()
        assert len(types) == 9 and len(categories) == 4
        check_popup_width(app, categories, types)
        picker = TypePicker()
        picker.addItem("— Choisir un type —", "")
        picker.set_reference(categories + [("empty", "Vide")], types)
        picker.show()
        app.processEvents()

        def click(row):
            item = picker.entries.item(row)
            QTest.mouseClick(picker.entries.viewport(), Qt.LeftButton,
                             pos=picker.entries.visualItemRect(item).center())
            app.processEvents()

        for category_id, label in categories:
            picker.showPopup()
            app.processEvents()
            assert picker.entries.count() == 5
            click(next(i for i, c in enumerate(categories) if c[0] == category_id))
            expected = [t for t in types if t[2] == category_id]
            assert picker.entries.count() == len(expected) + 1
            click(0)
            assert picker.entries.count() == 5
            click(next(i for i, c in enumerate(categories) if c[0] == category_id))
            click(1)
            assert picker.currentData() == expected[0][0]
            assert picker.currentText() == expected[0][1]
            assert not picker.popup.isVisible()
        picker.showPopup()
        app.processEvents()
        previous = picker.currentData()
        click(4)
        assert picker.entries.item(1).text() == "Aucun type disponible"
        click(1)
        assert picker.currentData() == previous
        QTest.keyClick(picker.entries, Qt.Key_Escape)
        app.processEvents()
        assert not picker.popup.isVisible()
        # Existing inactive types retain their UUID and label, without becoming choices.
        picker.addItem("Type inactif", "inactive")
        picker.setCurrentIndex(picker.findData("inactive"))
        picker.showPopup()
        app.processEvents()
        assert picker.currentData() == "inactive"
        picker.hidePopup()
        picker.close()
        print("Sélecteur : 4 catégories, 9 types, retour, sélection UUID, catégorie vide, fermeture et type inactif OK")
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
