"""Offscreen QGIS checks for map routing, role UI and deletion confirmation."""
import sys
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from qgis.PyQt.QtCore import Qt, QTimer, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog, QLabel, QMainWindow, QMessageBox, QPushButton
from qgis.core import QgsApplication

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'plugin'))
from gemapi_app import plugin as module
from gemapi_app.management import ManageDialog
from gemapi_app.permissions import prestation_permissions
from gemapi_app.record import build_delete


def sources(name):
    with ZipFile(ROOT / name) as archive:
        root = ET.fromstring(archive.read(next(x for x in archive.namelist() if x.endswith('.qgs'))))
    return [(layer.findtext('id'), layer.findtext('datasource'))
            for layer in root.findall('./projectlayers/maplayer')
            if 'table="milieux"."prestations_carte"' in (layer.findtext('datasource') or '')]


class Layer:
    def __init__(self, source):
        self._source = source
    def isValid(self):
        return True
    def providerType(self):
        return 'postgres'
    def source(self):
        return self._source


class Project:
    def __init__(self, layers):
        self.layers = layers
    def mapLayer(self, identifier):
        return self.layers.get(identifier)
    def mapLayers(self):
        return self.layers


def test_resolution():
    demo = sources('demo/prestations_demo.qgz')
    cabbalr = sources('cabbalr/prestations_cabbalr.qgz')
    assert len(demo) == len(cabbalr) == 3
    project = Project({identifier: Layer(source) for identifier, source in demo})
    uid = str(uuid4())
    for identifier, _ in demo:
        assert module.resolve_map_prestation(project, identifier, uid) == uid
    for bad in ('1', 'invalid', '', None):
        try:
            module.resolve_map_prestation(project, demo[0][0], bad)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError('UUID invalide accepté')
    project.layers['foreign'] = Layer(cabbalr[0][1])
    try:
        module.resolve_map_prestation(project, 'foreign', uid)
    except ValueError:
        pass
    else:
        raise AssertionError('Autre base acceptée')
    project.layers.pop('foreign')
    project.layers['foreign'] = Layer(demo[0][1].replace('prestations_carte', 'cours_eau'))
    try:
        module.resolve_map_prestation(project, 'foreign', uid)
    except ValueError:
        pass
    else:
        raise AssertionError('Autre table acceptée')


class Connection:
    def __init__(self, rights):
        self.rights = rights
        self.uid = str(uuid4())
        self.deleted = False
        self.error = None
        self.writes = []
    def executeSql(self, query):
        if query.startswith('SELECT has_table_privilege'):
            return [[self.rights[key] for key in ('select', 'insert', 'update', 'delete')]]
        if query.startswith('SELECT id,titre,version FROM'):
            return [] if self.deleted else [[self.uid, 'Prestation test', '123']]
        if query.startswith('DO $sig_prestations_delete$'):
            self.writes.append(query)
            if self.error:
                raise RuntimeError(self.error)
            self.deleted = True
            return []
        return []


class Session:
    def __init__(self, connection):
        self.conn = connection
        self.scope_generation = 0
        self.prestations_generation = 0
    def connection(self):
        return self.conn
    def get(self, key, loader, avoided_queries=1):
        return loader()
    def invalidate_prestations(self):
        self.prestations_generation += 1
    def clear(self, reason='manual'):
        self.scope_generation += 1
    def close(self):
        pass


class Interface:
    def __init__(self):
        self.window = QMainWindow()
    def mainWindow(self):
        return self.window


class Form(QDialog):
    saved = pyqtSignal(str)
    def __init__(self, iface, parent=None, mode='create', session=None):
        super().__init__(parent)
        self.mode = mode
        self.current_prestation_id = None
        self._edit_saved = False
        self._save_completed = False
        self._saved_scope_generation = None
        self.backButton = QPushButton(self)
        self.backButton.clicked.connect(self.reject)
    def load_existing(self, connection, uid):
        self.current_prestation_id = uid
    def shutdown(self):
        self.reject()


def test_routing():
    real_form = module.CreationDialog
    module.CreationDialog = Form
    try:
        iface = Interface()
        plugin = module.SigMilieuxUX(iface)
        plugin.session.close()
        rights = dict(select=True, insert=False, update=False, delete=False)
        connection = Connection(rights)
        plugin.session = Session(connection)
        class Manager(QDialog):
            def __init__(self):
                super().__init__()
                self.statusLabel = QLabel()
                self.connection = connection
                self.refreshed = 0
            def selected_id(self):
                return connection.uid
            def refresh(self):
                self.refreshed += 1
        plugin.manage = Manager()
        plugin.manage.show()
        plugin.show_existing()
        assert plugin.creation.mode == 'view'
        assert not plugin.manage.isVisible()
        plugin.creation.reject()
        assert plugin.manage.isVisible() and plugin.manage.refreshed == 1
        rights['update'] = True
        plugin.manage.hide()
        opened = plugin.open_prestation(connection.uid, origin='map')
        assert opened.mode == 'edit' and plugin.manage is not None
        assert not plugin.manage.isVisible()
        opened.reject()
        assert not plugin.manage.isVisible()
        rights['update'] = False
        try:
            plugin.open_prestation(connection.uid, origin='map')
        except ValueError:
            pass
        else:
            raise AssertionError('Lecture a obtenu une édition')
        plugin.manage.close()
        plugin.manage = None
        plugin.session.close()
    finally:
        module.CreationDialog = real_form


def click_confirmation(button):
    QTimer.singleShot(0, lambda: QgsApplication.instance().activeModalWidget().button(button).click())


def test_manager_delete():
    rights = dict(select=True, insert=False, update=False, delete=False)
    connection = Connection(rights)
    manager = ManageDialog(connection=connection)
    manager.show()
    QgsApplication.processEvents()
    assert manager.prestationList.count() == 1
    assert not manager.newButton.isVisible() and not manager.deleteButton.isVisible()
    assert manager.openButton.text() == 'Consulter la prestation'
    manager.prestationList.setCurrentRow(0)
    assert not manager.deleteButton.isEnabled()
    rights.update(insert=True, update=True, delete=True)
    manager.refresh(force=True)
    assert manager.deleteButton.isVisible()
    manager.prestationList.setCurrentRow(0)
    assert manager.deleteButton.isEnabled()
    manager._refresh_carto = lambda _: True
    click_confirmation(QMessageBox.No)
    manager.deleteButton.click()
    assert not connection.writes and manager.prestationList.count() == 1
    for error, expected in (('SIG_PRESTATIONS_CONFLICT', 'changé'),
                            ('SIG_PRESTATIONS_NOT_FOUND', 'déjà été supprimée'),
                            ('SIG_PRESTATIONS_FORBIDDEN', 'Droit DELETE')):
        connection.error = error
        click_confirmation(QMessageBox.Yes)
        manager.deleteButton.click()
        assert expected in manager.statusLabel.text()
        assert manager.prestationList.count() == 1
    connection.error = None
    photo = ROOT / 'audits/PERF-QGIS-09B/photo-ui-preservee.txt'
    photo.parent.mkdir(parents=True, exist_ok=True)
    photo.write_text('photo intacte', encoding='utf-8')
    click_confirmation(QMessageBox.Yes)
    manager.deleteButton.click()
    assert connection.deleted and manager.prestationList.count() == 0
    assert photo.read_text(encoding='utf-8') == 'photo intacte'
    photo.unlink()
    assert 'supprimée' in manager.statusLabel.text()
    manager.close()


def main():
    app = QgsApplication([], True)
    app.initQgis()
    for bad in ('bad', '', '123'):
        try:
            build_delete(bad, '1')
        except ValueError:
            pass
        else:
            raise AssertionError('UUID invalide accepté')
    try:
        build_delete(str(uuid4()), 'invalid')
    except ValueError:
        pass
    else:
        raise AssertionError('Version invalide acceptée')
    assert prestation_permissions(Connection(dict(select=True, insert=False,
        update=False, delete=False)))['delete'] is False
    test_resolution()
    test_routing()
    test_manager_delete()
    app.exitQgis()
    print('Actions, UUID, droits, navigation et suppression UI : OK')


if __name__ == '__main__':
    main()
