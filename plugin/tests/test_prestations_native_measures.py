"""Native fiche/cartographic forms and persisted PostGIS measures, without remote access.

Project assertions run with unittest. Database checks run in test_demo_import,
against fresh databases with PostGIS in both public and extensions.
"""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import unittest

ROOT = Path(__file__).resolve().parents[2]
MEASURES = ('nombre_points', 'longueur_m', 'surface_m2', 'surface_ha',
            'type_geometrie', 'type_geometrie_postgis', 'possede_geometrie', 'origine_mesures')


class NativeMeasures(unittest.TestCase):
    def test_projects_keep_measure_views_without_physical_layer(self):
        for env in ('demo', 'cabbalr'):
            with self.subTest(env=env):
                path = ROOT/env/('prestations_demo.qgz' if env == 'demo' else 'prestations_cabbalr.qgz')
                with ZipFile(path) as archive:
                    root = ET.fromstring(archive.read(next(n for n in archive.namelist() if n.endswith('.qgs'))))
                nodes = root.findall('./projectlayers/maplayer')
                self.assertFalse(any(n.findtext('layername') == 'prestations' for n in nodes))
                self.assertEqual(sum(n.findtext('provider') == 'postgres' for n in nodes), 25)
                self.assertEqual(len(root.findall('./relations/relation')), 66)
                self.assertEqual(sum(n.findtext('layername') == 'prestations_fiches' for n in nodes), 1)
                self.assertEqual(sum(n.findtext('layername') in ('prestations-points',
                    'prestations-lignes', 'prestations-polygones') for n in nodes), 3)

    def test_cartographic_and_fiche_forms_expose_canonical_measures(self):
        for env in ('demo', 'cabbalr'):
            with ZipFile(ROOT/env/f'prestations_{env}.qgz') as archive:
                root = ET.fromstring(archive.read(next(n for n in archive.namelist() if n.endswith('.qgs'))))
            targets = [n for n in root.findall('./projectlayers/maplayer')
                       if n.findtext('layername') in ('prestations-points', 'prestations-lignes',
                                                     'prestations-polygones', 'prestations_fiches')]
            self.assertEqual(len(targets), 4)
            for layer in targets:
                with self.subTest(env=env, layer=layer.findtext('layername')):
                    if layer.findtext('layername') == 'prestations_fiches':
                        self.assertEqual(layer.get('readOnly'), '1')
                    fields = {n.get('name') for n in layer.findall('./fieldConfiguration/field')}
                    displayed = {n.get('name') for n in layer.findall('.//attributeEditorField')}
                    self.assertTrue(set(MEASURES) <= fields & displayed)
                    for field in ('nombre_points','origine_mesures') if layer.findtext('layername')=='prestations_fiches' else MEASURES:
                        self.assertEqual(layer.find(f"./editable/field[@name='{field}']").get('editable'), '0')
                        names = [n.get('name') for n in layer.findall('./fieldConfiguration/field')]
                        self.assertEqual(int(layer.find(f".//attributeEditorField[@name='{field}']").get('index')), names.index(field))


def check_database(query):
    """Use independent geometry constants, not the resolver as its own oracle."""
    assert query("SELECT count(*) FROM information_schema.columns WHERE table_schema='milieux' "
                 "AND table_name='prestations' AND column_name IN (" +
                 ','.join("'"+n+"'" for n in MEASURES) + ');') == '8'
    assert query("SELECT is_generated FROM information_schema.columns WHERE table_schema='milieux' "
                 "AND table_name='prestations' AND column_name='surface_ha'") == 'ALWAYS'
    assert query("SELECT count(*) FROM milieux.prestations WHERE "
                 "possede_geometrie IS DISTINCT FROM true OR "
                 "origine_mesures IS DISTINCT FROM CASE WHEN geom IS NULL THEN "
                 "'Patrimoine de rattachement' ELSE 'Prestation' END") == '0'
    query(r"""
BEGIN;
DO $test$
DECLARE p milieux.prestations%ROWTYPE; v record; zone uuid; old_trace timestamptz;
BEGIN
 FOR v IN SELECT * FROM (VALUES
   ('POINT(0 0)',1,NULL::float8,NULL::float8,'Point','ST_Point'),
   ('MULTIPOINT((0 0),(2 2))',2,NULL,NULL,'Point','ST_MultiPoint'),
   ('LINESTRING(0 0,3 4)',NULL,5,NULL,'Ligne','ST_LineString'),
   ('MULTILINESTRING((0 0,3 4),(20 20,20 30))',NULL,15,NULL,'Ligne','ST_MultiLineString'),
   ('POLYGON((0 0,2 0,2 3,0 3,0 0))',NULL,NULL,6,'Polygone','ST_Polygon'),
   ('MULTIPOLYGON(((0 0,2 0,2 3,0 3,0 0)),((10 0,12 0,12 3,10 3,10 0)))',NULL,NULL,12,'Polygone','ST_MultiPolygon')
 ) x(wkt,n,l,a,famille,genre)
 LOOP
   SELECT * INTO p FROM milieux.prestations WHERE ah_stockage_id IS NOT NULL LIMIT 1;
   UPDATE milieux.prestations SET geom=ST_GeomFromText(v.wkt,3950),quantite=123.45,unite='déclarée'
   WHERE id=p.id RETURNING * INTO p;
   IF ROW(p.nombre_points,p.longueur_m,p.surface_m2,p.type_geometrie,p.type_geometrie_postgis,p.origine_mesures)
      IS DISTINCT FROM ROW(v.n,v.l,v.a,v.famille,v.genre,'Prestation'::text)
      OR p.surface_ha IS DISTINCT FROM v.a/10000.0 OR p.quantite<>123.45 OR p.unite<>'déclarée'
   THEN RAISE EXCEPTION 'Mesure propre complète incorrecte pour %',v.wkt; END IF;
 END LOOP;
 SELECT * INTO p FROM milieux.prestations WHERE site_zone_id IS NOT NULL LIMIT 1;
 zone:=p.site_zone_id;old_trace:=p.date_modification;
 UPDATE milieux.sites_zones SET geom=ST_GeomFromText('MULTIPOINT((0 0),(100 100))',3950) WHERE id=zone;
 SELECT * INTO p FROM milieux.prestations WHERE id=p.id;
 IF p.nombre_points<>2 OR p.origine_mesures<>'Patrimoine de rattachement'
    OR p.date_modification IS DISTINCT FROM old_trace OR p.geom IS NOT NULL
 THEN RAISE EXCEPTION 'Actualisation parentale ou traçabilité incorrecte'; END IF;
 UPDATE milieux.prestations SET nombre_points=999,surface_m2=999,origine_mesures='Injection' WHERE id=p.id;
 SELECT * INTO p FROM milieux.prestations WHERE id=p.id;
 IF p.nombre_points<>2 OR p.surface_m2 IS NOT NULL OR p.origine_mesures<>'Patrimoine de rattachement'
    OR p.date_modification IS DISTINCT FROM old_trace
 THEN RAISE EXCEPTION 'Mesures modifiables manuellement'; END IF;
 UPDATE milieux.sites_zones SET geom=ST_GeomFromText('MULTILINESTRING((0 0,3 4),(20 20,20 30))',3950) WHERE id=zone;
 SELECT * INTO p FROM milieux.prestations WHERE id=p.id;
 IF p.longueur_m<>15 OR p.nombre_points IS NOT NULL THEN RAISE EXCEPTION 'Longueur parentale'; END IF;
 UPDATE milieux.sites_zones SET geom=ST_GeomFromText('MULTIPOLYGON(((0 0,2 0,2 3,0 3,0 0)),((10 0,12 0,12 3,10 3,10 0)))',3950) WHERE id=zone;
 SELECT * INTO p FROM milieux.prestations WHERE id=p.id;
 IF p.surface_m2<>12 OR p.surface_ha<>0.0012 OR p.longueur_m IS NOT NULL THEN RAISE EXCEPTION 'Surface parentale'; END IF;
END $test$;
ROLLBACK;
""")


if __name__ == '__main__':
    unittest.main()
