"""Execute versioned DELETE through the real QGIS PostgreSQL provider on PostGIS."""
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from qgis.core import (QgsApplication, QgsDataSourceUri, QgsProject,
                       QgsProviderRegistry, QgsVectorLayer, QgsWkbTypes)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.record import build_delete, build_insert, build_update
from gemapi_app.creation import CreationDialog
from gemapi_app.management import ManageDialog
from test_postgres_integration import command, sql
from test_prestation_delete_postgis import fixture, insert, values, version


def main():
    container = 'sig-qgis-delete-' + uuid4().hex[:10]
    command('docker', 'run', '--rm', '-d', '--name', container,
            '-p', '127.0.0.1::5432', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
            'postgis/postgis:16-3.4')
    try:
        for _ in range(60):
            if command('docker', 'exec', container, 'pg_isready', '-h', '127.0.0.1',
                       '-U', 'postgres', check=False).returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError('PostGIS jetable non prêt')
        port = command('docker', 'port', container, '5432').stdout.strip().rsplit(':', 1)[1]
        fixture(container)
        data, (storage, _) = values(container, 'audits/PERF-QGIS-09B/photo-preservee.txt')
        app = QgsApplication([], False)
        app.initQgis()
        metadata = QgsProviderRegistry.instance().providerMetadata('postgres')
        assert metadata is not None
        connection = metadata.createConnection(
            f"dbname='postgres' host='127.0.0.1' port={port} user='postgres'", {})
        project = QgsProject.instance()
        layers = {}
        for kind in (QgsWkbTypes.MultiPoint, QgsWkbTypes.MultiLineString,
                     QgsWkbTypes.MultiPolygon):
            uri = QgsDataSourceUri()
            uri.setConnection('127.0.0.1', port, 'postgres', 'postgres', '')
            uri.setDataSource('gemapi', 'prestations_carte', 'geom', '', 'id')
            uri.setWkbType(kind)
            uri.setSrid('3950')
            layer = QgsVectorLayer(uri.uri(False), 'carte temporaire', 'postgres')
            assert layer.isValid(), kind
            project.addMapLayer(layer)
            layers[kind] = layer
        first = insert(container, data, 'ah_stockage', storage)
        connection.executeSql(build_delete(first, version(container, first)))
        assert not version(container, first)
        assert ManageDialog._refresh_carto(SimpleNamespace(connection=connection), connection)
        moved = connection.executeSql(build_insert(data, [('ah_stockage', storage)],
                                                   'POINT(2 2)'))[0][0]
        moved = str(moved)
        assert any(str(feature['id']) == moved for feature in
                   layers[QgsWkbTypes.MultiPoint].getFeatures())
        edit_sql = build_update(moved, version(container, moved), data, data,
                                [('ah_stockage', storage)], [('ah_stockage', storage)],
                                'POINT(2 2)', 'LINESTRING(2 2,3 3)')
        connection.executeSql(edit_sql)
        form = SimpleNamespace(
            _canonical_layer=lambda table: layers[QgsWkbTypes.MultiPoint]
            if table == 'prestations_carte' else None,
            _associations=lambda: [('ah_stockage', storage)])
        assert CreationDialog._refresh_layers(form)
        assert not any(str(feature['id']) == moved for feature in
                       layers[QgsWkbTypes.MultiPoint].getFeatures())
        assert any(str(feature['id']) == moved for feature in
                   layers[QgsWkbTypes.MultiLineString].getFeatures())
        second = insert(container, data, 'ah_stockage', storage)
        old = version(container, second)
        sql(container, f"UPDATE gemapi.prestations SET description='Autre version' WHERE id='{second}'")
        try:
            connection.executeSql(build_delete(second, old))
        except Exception as error:
            assert 'SIG_PRESTATIONS_CONFLICT' in str(error), str(error)
        else:
            raise AssertionError('Le fournisseur QGIS a accepté une version périmée')
        assert version(container, second) != old
        print('Fournisseur PostgreSQL QGIS : suppression et conflit xmin vérifiés')
        project.clear()
        app.exitQgis()
    finally:
        command('docker', 'stop', container, check=False)


if __name__ == '__main__':
    main()
