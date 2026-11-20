"""Management patrimony picker, using QGIS offscreen and a read-only fake SQL connection.

Run with QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_management_patrimony_ui.py
"""

import sys
from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.core import QgsApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.management import ManageDialog  # noqa: E402


STORAGE = "11111111-1111-1111-1111-111111111111"
WORKS = "22222222-2222-2222-2222-222222222222"
ZONE = "33333333-3333-3333-3333-333333333333"
RIVER = "44444444-4444-4444-4444-444444444444"
DIKE = "55555555-5555-5555-5555-555555555555"


class FakeConnection:
    def executeSql(self, query):
        if query.startswith("SELECT has_table_privilege"):
            return ((True, True, True, True),)
        if "FROM milieux.ah_sections" in query:
            return ()
        if query.startswith("SELECT DISTINCT annee"):
            return ((2026,), (2027,))
        if query.startswith("SELECT id::text,libelle FROM milieux.statuts_prestations"):
            return ((STORAGE, "Terminé"),)
        if query.startswith("SELECT id::text,nom FROM milieux.prestataires"):
            return ((STORAGE, "Prestataire"),)
        if query.startswith("SELECT id::text,concat_ws(' ',prenom,nom)"):
            return ((STORAGE, "Julien Dubois"),)
        if query.startswith("SELECT id::text,nom FROM milieux.communes"):
            return ((STORAGE, "Commune"),)
        if "FROM milieux.ah_stockage o" in query:
            return ((STORAGE, "ZEC du Bois — Stockage principal"),)
        if "FROM milieux.ah_ouvrage o" in query:
            return ((WORKS, "ZEC du Bois — Ouvrage de régulation"),)
        if "FROM milieux.sites_zones o" in query:
            return ((ZONE, "Marais des Saules — Mare nord"),)
        if "FROM milieux.cours_eau" in query:
            return ((RIVER, "La Clarence"),)
        if "FROM milieux.digues" in query:
            return ((DIKE, "Digue des Prés"),)
        if "SELECT id,titre FROM" in query:
            return ((STORAGE, "Prestation de contrôle"),)
        raise AssertionError(query)


def main():
    app = QgsApplication([], True)
    app.initQgis()
    dialog = ManageDialog(connection=FakeConnection())
    dialog.show()
    app.processEvents()
    assert [dialog.familyCombo.itemData(i) for i in range(dialog.familyCombo.count())] == [
        "", "cours_eau", "digues", "ah", "site_terrestre"]
    assert dialog.objectPicker.title == "Patrimoine"
    assert dialog.familyCombo.parent() is dialog.objectPicker
    for family, count in (("cours_eau", 1), ("digues", 1), ("ah", 2),
                          ("site_terrestre", 1)):
        dialog.familyCombo.setCurrentIndex(dialog.familyCombo.findData(family))
        assert dialog.objectPicker.list.count() == count, family
        assert not any(dialog.filters().get(key) for key in
                       ("cours_eau", "digues", "ah_stockage", "ah_ouvrage", "sites_zones"))
    dialog.familyCombo.setCurrentIndex(dialog.familyCombo.findData("ah"))
    items = [dialog.objectPicker.list.item(i) for i in range(2)]
    assert {item.data(Qt.UserRole) for item in items} == {
        ("ah_stockage", STORAGE), ("ah_ouvrage", WORKS)}
    assert all(item.text().startswith("ZEC du Bois — ") and item.toolTip() == item.text()
               for item in items)
    for item in items:
        item.setCheckState(Qt.Checked)
    assert dialog.filters()["ah_stockage"] == (STORAGE,)
    assert dialog.filters()["ah_ouvrage"] == (WORKS,)
    dialog.objectPicker.search.setText("Ouvrage")
    assert set(dialog.objectPicker.values()) == {("ah_stockage", STORAGE), ("ah_ouvrage", WORKS)}
    dialog.objectPicker.search.setText("Bois")
    assert all(not item.isHidden() for item in items)
    dialog.objectPicker.search.clear()
    dialog.pickers["years"].list.item(0).setCheckState(Qt.Checked)
    dialog.pickers["providers"].list.item(0).setCheckState(Qt.Checked)
    assert dialog.filters()["years"] == (2026,)
    assert dialog.filters()["providers"] == (STORAGE,)
    dialog.resize(1000, 800)
    app.processEvents()
    first = [dialog.pickers[key].geometry() for key in
             ("years", "statuses", "technicians", "providers")]
    assert len({item.y() for item in first}) == 1
    assert all(first[i].x() < first[i + 1].x() for i in range(3))
    assert dialog.objectPicker.geometry().y() > first[0].y()
    assert dialog.objectPicker.geometry().x() > dialog.pickers["communes"].geometry().x()
    dialog.familyCombo.setCurrentIndex(dialog.familyCombo.findData("site_terrestre"))
    assert "ah_stockage" not in dialog.filters() and "ah_ouvrage" not in dialog.filters()
    assert dialog.objectPicker.list.item(0).text() == "Marais des Saules — Mare nord"
    dialog.objectPicker.list.item(0).setCheckState(Qt.Checked)
    assert dialog.filters()["sites_zones"] == (ZONE,)
    dialog.clear_filters()
    assert dialog.familyCombo.currentData() == "" and not dialog.objectPicker.values()
    assert not dialog.filters()["years"] and not dialog.filters()["providers"]
    dialog.familyCombo.setCurrentIndex(dialog.familyCombo.findData("ah"))
    dialog.resize(1000, 800)
    app.processEvents()
    image = Path(__file__).resolve().parents[2] / "audits/ux_gestion_patrimoine_01_formulaire.png"
    image.parent.mkdir(exist_ok=True)
    assert dialog.grab().save(str(image))
    for width in (780, 560):
        dialog.resize(width, 700)
        app.processEvents()
        assert dialog.objectPicker.geometry().width() > 0
    dialog.close()
    print("Gestion patrimoniale Qt : cinq choix, listes, recherche, filtres et grille OK")


if __name__ == "__main__":
    main()
