"""Bidirectional QGIS project synchronisation, without database access."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from qgis.core import QgsDataSourceUri

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('project_sync', ROOT/'cabbalr/scripts/synchroniser_projet_qgis.py')
sync = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sync
spec.loader.exec_module(sync)


def edit_project(path, edit):
    project = sync.archive(path)
    edit(project['root'])
    xml = project['xml'].split(b'<qgis',1)[0]+ET.tostring(project['root'],encoding='utf-8')
    with ZipFile(path,'w') as output:
        output.comment = project['comment']
        for entry,data in project['members']:
            output.writestr(entry,xml if entry.filename==project['name'] else data)


class ProjectSyncTest(unittest.TestCase):
    def setUp(self):
        (ROOT/'audits').mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='project-sync-',dir=ROOT/'audits')
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.paths = {}
        for env in ('demo','cabbalr'):
            self.paths[env] = self.folder/(env+'.qgz')
            self.paths[env].write_bytes(sync.PROJECTS[env].read_bytes())
        self.backups = self.folder/'sauvegardes'

    def root(self,env):
        return sync.archive(self.paths[env])['root']

    def configuration_edit(self,env,name='Configuration source'):
        def change(root):
            next(iter(sync.layers(root).values())).find('layername').text=name
        edit_project(self.paths[env],change)

    def assert_environment_kept(self,before,after):
        self.assertEqual(sync.environment(before),sync.environment(after))
        self.assertEqual(sync.relation_ids(before),sync.relation_ids(after))
        self.assertEqual(sync.layers(before).keys(),sync.layers(after).keys())

    def test_embedded_python_actions_target_current_plugin(self):
        for env in ('demo', 'cabbalr'):
            with self.subTest(env=env):
                xml = ET.tostring(self.root(env), encoding='unicode')
                self.assertIn('gemapi_app', xml)
                self.assertNotIn('sig_prestations', xml)

    def test_projects_use_one_direct_postgres_connection(self):
        for env in ('demo', 'cabbalr'):
            with self.subTest(env=env):
                root = self.root(env)
                postgres = [QgsDataSourceUri(layer.findtext('datasource'))
                            for layer in sync.layers(root).values()
                            if layer.findtext('provider') == 'postgres']
                # The hidden SQL zone reference remains after PERF-QGIS-09A.
                self.assertEqual(len(postgres), 25)
                technical_id = 'Zones_terrestres_libelles_sql_PERF_QGIS_03B'
                technical = sync.layers(root)[technical_id]
                self.assertEqual(technical.findtext('provider'), 'postgres')
                self.assertEqual(QgsDataSourceUri(technical.findtext('datasource')).keyColumn(), 'id')
                self.assertIsNone(root.find(f'./layer-tree-group//layer-tree-layer[@id="{technical_id}"]'))
                self.assertFalse(any(uri.schema() == 'milieux' and uri.table() == 'prestations'
                                     for uri in postgres))
                self.assertEqual(sum(uri.table() == 'prestations_carte' for uri in postgres), 3)
                self.assertEqual(sum(uri.table() == 'prestations_fiches' for uri in postgres), 1)
                self.assertEqual(len(sync.relation_ids(root)), 66)
                connections = {uri.connectionInfo(False) for uri in postgres}
                self.assertEqual(len(connections), 1)
                for element in root.iter():
                    for value in element.attrib.values():
                        if value.startswith('dbname='):
                            self.assertIn(QgsDataSourceUri(value).connectionInfo(False), connections)
                for uri in postgres:
                    if env == 'cabbalr':
                        self.assertFalse(uri.username())
                    self.assertTrue(uri.host())
                    self.assertEqual(uri.port(), '5432')
                    self.assertEqual(uri.database(), 'postgres')
                    self.assertEqual(uri.sslMode(), QgsDataSourceUri.SslRequire)
                    self.assertFalse(uri.password() or uri.service() or uri.authConfigId())
                    for field in ('sslrootcert', 'sslcert', 'sslkey'):
                        self.assertFalse(uri.hasParam(field))

    def test_prestation_status_categories_are_canonical_in_both_projects(self):
        expected = {
            '58554fd0-fcc2-45b6-aa19-cc4a897af3fb': 'Planifié',
            '9ee713ca-13a1-4358-b5d8-fa79627fc256': 'En cours',
            '421801d8-30be-4a5a-8e18-cb2b9ac0ea37': 'Terminé',
            'fdd48590-aace-4693-946e-80c1f4d8693f': 'Annulé',
        }
        signatures = []
        for env in ('demo', 'cabbalr'):
            root = self.root(env)
            for name in ('prestations-points', 'prestations-lignes', 'prestations-polygones'):
                layer, = [item for item in sync.layers(root).values()
                          if item.findtext('layername') == name]
                renderer = layer.find('./renderer-v2')
                self.assertEqual(renderer.get('type'), 'categorizedSymbol')
                self.assertEqual(renderer.get('attr'), 'statut_id')
                categories = renderer.findall('./categories/category')
                self.assertEqual({c.get('value'): c.get('label') for c in categories}, expected)
                self.assertEqual(len(categories), 4)
                self.assertTrue(all(c.get('render') == 'true' for c in categories))
                signatures.append([(c.get('value'), c.get('label'), c.get('symbol'))
                                   for c in categories])
        self.assertTrue(all(signature == signatures[0] for signature in signatures))

    def test_removed_native_prestation_layer_is_not_reintroduced(self):
        for env in ('demo', 'cabbalr'):
            with self.subTest(env=env):
                root = self.root(env)
                self.assertFalse(any(layer.findtext('layername') == 'prestations'
                                     for layer in sync.layers(root).values()))
                self.assertEqual(len(sync.relation_ids(root)), 66)

    def test_sync_rejects_project_with_reintroduced_layer(self):
        def add_obsolete_layer(root):
            layers = root.find('./projectlayers')
            layer = deepcopy(next(iter(layers)))
            layer.find('id').text = 'obsolete_prestations_layer'
            layer.find('layername').text = 'prestations'
            layers.append(layer)
        edit_project(self.paths['cabbalr'], add_obsolete_layer)
        with self.assertRaisesRegex(ValueError, 'identifiants de couches'):
            sync.compare(self.paths['cabbalr'], self.paths['demo'])

    def test_only_known_hydro_filter_difference_is_local(self):
        plan = sync.compare(self.paths['cabbalr'], self.paths['demo'])
        identifier = next(identifier for identifier, layer in sync.layers(plan.root).items()
                          if layer.findtext('layername') == "Cours d'eau")
        self.assertEqual(QgsDataSourceUri(sync.layers(plan.root)[identifier].findtext('datasource')).sql(), '')
        def unexpected_filter(root):
            course = sync.layers(root)[identifier]
            uri = QgsDataSourceUri(course.findtext('datasource'))
            uri.setSql('"nom" IS NULL')
            course.find('datasource').text = uri.uri(False)
        edit_project(self.paths['cabbalr'], unexpected_filter)
        with self.assertRaisesRegex(ValueError, 'filtre SQL'):
            sync.compare(self.paths['cabbalr'], self.paths['demo'])

    def test_reverse_preserves_destination_and_source_with_verified_backup(self):
        self.configuration_edit('cabbalr')
        source_hash=sync.digest(self.paths['cabbalr'])
        before=self.paths['demo'].read_bytes()
        old=self.root('demo')
        plan=sync.compare(self.paths['cabbalr'],self.paths['demo'])
        self.assertTrue(plan.pending)
        backup=plan.apply(self.backups)
        self.assertEqual(backup.read_bytes(),before)
        self.assertEqual(sync.digest(self.paths['cabbalr']),source_hash)
        new=self.root('demo')
        self.assert_environment_kept(old,new)
        self.assertEqual(next(iter(sync.layers(new).values())).findtext('layername'),'Configuration source')
        self.assertFalse(sync.compare(self.paths['cabbalr'],self.paths['demo']).pending)
        with ZipFile(self.paths['demo']) as output:
            self.assertIn('prestations_demo.qgs',output.namelist())
            self.assertNotIn('prestations_cabbalr.qgs',output.namelist())
            self.assertFalse(any(b'fmgeqjspogvyhprvinnw' in output.read(n) for n in output.namelist()))

    def test_forward_preserves_destination_account_and_extents(self):
        self.configuration_edit('demo')
        old=self.root('cabbalr')
        plan=sync.compare(self.paths['demo'],self.paths['cabbalr'])
        plan.apply(self.backups)
        self.assert_environment_kept(old,self.root('cabbalr'))
        reverse = sync.compare(self.paths['demo'],self.paths['cabbalr'])
        self.assertFalse(reverse.pending, reverse.report['modifications_a_reporter'])

    def test_reverse_then_forward_does_not_propose_formatting_only_changes(self):
        self.configuration_edit('cabbalr')
        source_hash=sync.digest(self.paths['cabbalr'])
        sync.compare(self.paths['cabbalr'],self.paths['demo']).apply(self.backups)
        reverse = sync.compare(self.paths['demo'],self.paths['cabbalr'])
        self.assertFalse(reverse.pending, reverse.report['modifications_a_reporter'])
        self.assertEqual(sync.digest(self.paths['cabbalr']),source_hash)

    def test_simulation_default_does_not_write_or_back_up(self):
        self.configuration_edit('cabbalr')
        before={env:p.read_bytes() for env,p in self.paths.items()}
        with patch.dict(sync.PROJECTS,self.paths),patch.object(sys,'argv',['sync','--sens','cabbalr-vers-demo']),redirect_stdout(StringIO()) as text:
            sync.main()
        self.assertIn('Simulation uniquement',text.getvalue())
        for env,path in self.paths.items():self.assertEqual(path.read_bytes(),before[env])
        self.assertFalse(self.backups.exists())

    def test_direction_is_mandatory(self):
        before={env:p.read_bytes() for env,p in self.paths.items()}
        with patch.object(sys,'argv',['sync']),self.assertRaises(SystemExit) as error:
            sync.main()
        self.assertEqual(error.exception.code,2)
        for env,path in self.paths.items():self.assertEqual(path.read_bytes(),before[env])

    def test_authentication_and_distinct_ssl_modes_are_preserved(self):
        def auth(root):
            for layer in sync.layers(root).values():
                if layer.findtext('provider')=='postgres':
                    uri=QgsDataSourceUri(layer.findtext('datasource'))
                    uri.setConnection(uri.host(),uri.port(),uri.database(),uri.username(),'',QgsDataSourceUri.SslVerifyFull,'abc1234')
                    layer.find('datasource').text=uri.uri(False)
                    break
        edit_project(self.paths['demo'],auth)
        before=self.root('demo')
        plan=sync.compare(self.paths['cabbalr'],self.paths['demo'])
        self.assert_environment_kept(before,plan.root)
        self.assertIn('authcfg=abc1234',ET.tostring(plan.root,encoding='unicode'))
        for layer in sync.layers(plan.root).values():
            for field in layer.findall('./fieldConfiguration/field'):
                for option in field.findall(".//Option[@name='ReferencedLayerDataSource']"):
                    parent = next(node for node in field.iter() if option in node)
                    referenced_id = parent.find("Option[@name='ReferencedLayerId']").get('value')
                    referenced = sync.layers(plan.root)[referenced_id]
                    self.assertEqual(QgsDataSourceUri(option.get('value')).uri(False),
                                     QgsDataSourceUri(referenced.findtext('datasource')).uri(False))

    def test_widget_reference_to_another_table_is_rejected(self):
        def wrong_table(root):
            field = next(layer.find("./fieldConfiguration/field[@name='ah_section_id']")
                         for layer in sync.layers(root).values()
                         if layer.find("./fieldConfiguration/field[@name='ah_section_id']") is not None)
            option = field.find(".//Option[@name='ReferencedLayerDataSource']")
            uri = QgsDataSourceUri(option.get('value'))
            uri.setDataSource('milieux', 'cours_eau', 'geom', '', 'id')
            option.set('value', uri.uri(False))
        edit_project(self.paths['demo'], wrong_table)
        with self.assertRaisesRegex(ValueError, 'Source de widget incompatible'):
            sync.compare(self.paths['cabbalr'], self.paths['demo'])

    def test_lookup_filter_is_preserved_when_authentication_changes(self):
        def auth(root):
            for layer in sync.layers(root).values():
                uri = QgsDataSourceUri(layer.findtext('datasource'))
                if layer.findtext('provider') == 'postgres' and uri.table() == 'cours_eau':
                    uri.setConnection(uri.host(), uri.port(), uri.database(), uri.username(), '',
                                      QgsDataSourceUri.SslVerifyFull, 'abc1234')
                    layer.find('datasource').text = uri.uri(False)
        edit_project(self.paths['cabbalr'], auth)
        before = self.root('cabbalr')
        plan = sync.compare(self.paths['demo'], self.paths['cabbalr'])
        self.assert_environment_kept(before, plan.root)
        for layer in sync.layers(plan.root).values():
            field = layer.find("./fieldConfiguration/field[@name='cours_eau_id']")
            if field is None:
                continue
            old = sync.layers(before)[layer.findtext('id')].find("./fieldConfiguration/field[@name='cours_eau_id']")
            for option, original in zip(field.findall(".//Option[@name='ReferencedLayerDataSource']"),
                                        old.findall(".//Option[@name='ReferencedLayerDataSource']")):
                uri = QgsDataSourceUri(option.get('value'))
                self.assertEqual(uri.sql(), QgsDataSourceUri(original.get('value')).sql())
                self.assertEqual(uri.authConfigId(), 'abc1234')
                self.assertEqual(uri.sslMode(), QgsDataSourceUri.SslVerifyFull)

    def test_all_cached_connections_match_destination_layers(self):
        plan=sync.compare(self.paths['cabbalr'],self.paths['demo'])
        allowed={QgsDataSourceUri(l.findtext('datasource')).uri(False)
                 for l in sync.layers(self.root('demo')).values() if l.findtext('provider')=='postgres'}
        count=0
        for element in plan.root.iter():
            for value in element.attrib.values():
                if value.startswith('dbname='):
                    count+=1
                    self.assertIn(QgsDataSourceUri(value).uri(False),allowed)
        self.assertGreater(count,150)

    def test_layout_geometry_is_local_but_layout_appearance_is_shared(self):
        def change(root):
            item=next(iter(sync.map_items(root).values()))
            item.find('Extent').set('xmin','987654')
            item.set('background','false')
            root.find('mapcanvas/extent/xmin').text='876543'
        edit_project(self.paths['cabbalr'],change)
        before=self.root('demo')
        plan=sync.compare(self.paths['cabbalr'],self.paths['demo'])
        self.assert_environment_kept(before,plan.root)
        self.assertEqual(next(iter(sync.map_items(plan.root).values())).get('background'),'false')

    def test_modified_destination_after_comparison_is_not_overwritten(self):
        self.configuration_edit('cabbalr')
        plan=sync.compare(self.paths['cabbalr'],self.paths['demo'])
        self.configuration_edit('demo','Changement concurrent')
        before=self.paths['demo'].read_bytes()
        with self.assertRaisesRegex(ValueError,'changé depuis'):
            plan.apply(self.backups)
        self.assertEqual(self.paths['demo'].read_bytes(),before)
        self.assertFalse(self.backups.exists())

    def test_modified_source_after_comparison_is_not_applied(self):
        self.configuration_edit('cabbalr')
        plan=sync.compare(self.paths['cabbalr'],self.paths['demo'])
        self.configuration_edit('cabbalr','Nouvelle modification')
        before=self.paths['demo'].read_bytes()
        with self.assertRaisesRegex(ValueError,'changé depuis'):
            plan.apply(self.backups)
        self.assertEqual(self.paths['demo'].read_bytes(),before)

    def test_conflicting_layer_or_relation_ids_are_refused(self):
        for path in ('./projectlayers/maplayer/id','./relations/relation'):
            with self.subTest(path=path):
                original=self.paths['cabbalr'].read_bytes()
                def change(root):
                    node=root.find(path)
                    if node.tag=='id':node.text='id_modifie'
                    else:node.set('id','relation_modifiee')
                edit_project(self.paths['cabbalr'],change)
                with self.assertRaisesRegex(ValueError,'identifiants'):
                    sync.compare(self.paths['cabbalr'],self.paths['demo'])
                self.paths['cabbalr'].write_bytes(original)

    def test_unknown_cached_connection_is_refused(self):
        def change(root):
            root.set('unknownConnection',"dbname='postgres' host=other.invalid table=\"milieux\".\"unknown\"")
        edit_project(self.paths['cabbalr'],change)
        with self.assertRaisesRegex(ValueError,'non appariée'):
            sync.compare(self.paths['cabbalr'],self.paths['demo'])

    def test_no_op_does_not_create_another_backup(self):
        self.configuration_edit('cabbalr')
        sync.compare(self.paths['cabbalr'],self.paths['demo']).apply(self.backups)
        existing=set(self.backups.iterdir())
        self.assertIsNone(sync.compare(self.paths['cabbalr'],self.paths['demo']).apply(self.backups))
        self.assertEqual(set(self.backups.iterdir()),existing)

    def test_refuses_source_as_destination(self):
        with self.assertRaisesRegex(ValueError,'distincts'):
            sync.compare(self.paths['demo'],self.paths['demo'])

    def test_report_cannot_overwrite_a_project(self):
        before=self.paths['demo'].read_bytes()
        with patch.dict(sync.PROJECTS,self.paths),patch.object(sys,'argv',[
                'sync','--sens','cabbalr-vers-demo','--rapport',str(self.paths['demo'])]),redirect_stdout(StringIO()),self.assertRaises(SystemExit):
            sync.main()
        self.assertEqual(self.paths['demo'].read_bytes(),before)


if __name__=='__main__':
    unittest.main()
