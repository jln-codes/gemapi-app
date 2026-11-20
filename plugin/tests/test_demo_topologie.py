"""Topology contracts of the current fictitious patrimony GeoPackages."""

from pathlib import Path
from hashlib import md5, sha256
import sys
import time
from uuid import uuid4
from osgeo import ogr

ROOT = Path(__file__).resolve().parents[2]
GPKG = ROOT / "demo/gpkg"
ORIGINAL_SITE_ZONE_IDS = {
    "0833c88a-7a46-56a5-9dbc-505695bc0c03", "0ffdbbf2-1dd5-567d-884b-65a24bd27d7d",
    "244d75e5-bc7d-5815-b650-58799120d1c2", "4abd7aa5-104f-56ff-873d-d8ac83f41990",
    "5244c330-5ed9-5cee-a36f-7ade8b8bca15", "5dc5dccc-73af-59d8-9b30-52b0a81186b3",
    "65f82de1-c9a0-504a-ab61-9ec7194ffacf", "780ed467-e05b-5fc9-8cc3-b5c27b29d40d",
    "8e82c4e2-7895-5adb-b9e6-31e36ffaa95f", "ae305883-cc61-5e1f-a201-246baddd0243",
    "fcb46f36-90df-550e-a01a-a0406b0d3638", "fd2951d8-4fea-58f7-9001-916bcd9e70ec",
}


def read(file, table, zone_null=False):
    source = ogr.Open(str(GPKG / file))
    layer = source.GetLayerByName(table)
    assert layer is not None
    assert layer.GetSpatialRef().GetAuthorityCode(None) == "3950"
    rows = {}
    for feature in layer:
        geometry = feature.GetGeometryRef()
        if zone_null and feature.GetField('site_zone_id'):
            assert geometry is None
        else:
            assert geometry is not None and not geometry.IsEmpty() and geometry.IsValid()
        rows[str(feature["id"])] = (geometry.Clone() if geometry is not None else None,
                                    {name: feature[name] for name in feature.keys()})
    return rows


def no_surface_overlap(left, right, same=False):
    for first, (a, _) in left.items():
        for second, (b, _) in right.items():
            if same and first >= second:
                continue
            assert a.Intersection(b).Area() <= 0.001, (first, second)


def main():
    storage = read("ah.gpkg", "ah_stockage")
    works = read("ah.gpkg", "ah_ouvrage")
    sites = read("sites_terrestres.gpkg", "sites_terrestres")
    zones = read("sites_terrestres.gpkg", "sites_zones")
    assert (len(storage), len(works), len(sites), len(zones)) == (10, 13, 12, 25)
    assert ORIGINAL_SITE_ZONE_IDS <= set(zones)
    assert all(geometry.GetGeometryName() == "MULTIPOLYGON" and geometry.GetGeometryCount() == 1
               for geometry, _ in sites.values())
    parent_digest = md5("|".join(sorted(uid + ":" + geometry.GetGeometryRef(0).ExportToWkb().hex()
                                     for uid, (geometry, _) in sites.items())).encode()).hexdigest()
    assert parent_digest == "f107cd9adc6494ba70061e221b994021"
    no_surface_overlap(storage, storage, True)
    no_surface_overlap(sites, sites, True)
    no_surface_overlap(storage, sites)
    assert all(geometry.GetGeometryName() == "POLYGON" for geometry, _ in storage.values())
    assert {kind: sum(geometry.GetGeometryName() == kind for geometry, _ in zones.values())
            for kind in ("MULTIPOINT", "MULTILINESTRING", "MULTIPOLYGON")} == {
                "MULTIPOINT": 4, "MULTILINESTRING": 4, "MULTIPOLYGON": 17}
    assert all(geometry.GetGeometryName() == "LINESTRING" for geometry, _ in works.values())
    polygon_sites = {}
    for geometry, attributes in zones.values():
        parent = sites[str(attributes["site_terrestre_id"])][0]
        assert geometry.Difference(parent).IsEmpty()
        if geometry.GetGeometryName() == "MULTIPOLYGON":
            assert not geometry.Equals(parent)
            assert geometry.Area() < parent.Area() * 0.5
            polygon_sites.setdefault(str(attributes["site_terrestre_id"]), []).append(geometry)
    assert sum(len(parts) >= 2 for parts in polygon_sites.values()) == 5
    for parts in polygon_sites.values():
        for index, first in enumerate(parts):
            for second in parts[index + 1:]:
                assert first.Intersection(second).Area() < 0.001
    for geometry, attributes in works.values():
        parent = next(g for g, a in storage.values()
                      if str(a["ah_id"]) == str(attributes["ah_id"]))
        assert geometry.Distance(parent.Boundary()) <= 0.001
        assert geometry.Difference(parent.Boundary()).Length() <= 0.001
    prestations = {}
    for table in ("prestations_points", "prestations_lignes", "prestations_polygones"):
        prestations.update(read("prestations.gpkg", table, zone_null=True))
    assert len(prestations) == 100
    digest = sha256("|".join(sorted(
        uid + ":" + (geometry.ExportToWkb().hex() if geometry is not None else 'NULL')
        for uid, (geometry, _) in prestations.items())).encode()).hexdigest()
    assert digest == "9e992f40a6028127d2ac37c8eb025ea3432690154942fed8da6013f10589baf5"
    assert sum(geometry is None for geometry,_ in prestations.values()) == 12
    assert {geometry.GetGeometryName() for geometry, _ in prestations.values() if geometry is not None} == {
        "POINT", "MULTIPOINT", "LINESTRING", "MULTILINESTRING", "POLYGON", "MULTIPOLYGON"}
    print("Topologie fictive : 10 stockages, 13 ouvrages, 12 sites, 25 zones, "
          "100 prestations ; aucun chevauchement surfacique")


def check_postgis():
    """Test the fresh SQL import, including geometry constraints and links."""
    from test_postgres_integration import command, sql
    zones=read('sites_terrestres.gpkg','sites_zones')
    expected_zone_digest=md5('|'.join(sorted(
        uid+':'+geometry.ExportToWkb().hex() for uid,(geometry,_) in zones.items()
    )).encode()).hexdigest()
    link_rows=[]
    for table in ('prestations_points','prestations_lignes','prestations_polygones'):
        for uid,(_,attributes) in read('prestations.gpkg',table,zone_null=True).items():
            links=[(family,uid,str(attributes[field])) for family,field in (
                ('cours_eau','cours_eau_id'),('digues','digue_id'),
                ('ah_stockage','ah_stockage_id'),('ah_ouvrage','ah_ouvrage_id'),
                ('sites_terrestres','site_terrestre_id'),('sites_zones','site_zone_id'))
                if attributes[field]]
            assert len(links)==1
            link_rows.extend(links)
    expected_links_digest=md5(','.join(':'.join(row) for row in sorted(link_rows)).encode()).hexdigest()
    container = "sig-demo-topo-" + uuid4().hex[:10]
    command("docker", "run", "--rm", "-d", "--name", container,
            "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgis/postgis:16-3.4")
    try:
        for _ in range(60):
            if command("docker", "exec", container, "pg_isready", "-U", "postgres",
                       check=False).returncode == 0:
                break
            time.sleep(0.5)
        sql(container, "CREATE EXTENSION IF NOT EXISTS postgis;")
        sql(container, (ROOT / "model/schema.sql").read_text(encoding="utf-8"))
        statements = []
        for path in sorted((ROOT / "demo/data").glob("[0-9][0-9]_*.sql")):
            statements.append(path.read_text(encoding="utf-8"))
            if path.name == "11_cours_eau.sql":
                statements.append((ROOT / "demo/data/digues.sql").read_text(encoding="utf-8"))
        sql(container, "\n".join(statements))
        counts = sql(container, "SELECT (SELECT count(*) FROM milieux.prestations),"
                     "(SELECT count(cours_eau_id) FROM milieux.prestations)+"
                     "(SELECT count(digue_id) FROM milieux.prestations)+"
                     "(SELECT count(ah_stockage_id) FROM milieux.prestations)+"
                     "(SELECT count(ah_ouvrage_id) FROM milieux.prestations)+"
                     "(SELECT count(site_terrestre_id) FROM milieux.prestations)+"
                     "(SELECT count(site_zone_id) FROM milieux.prestations);")
        assert counts.stdout.strip() == "100|100"
        zone_checks = sql(container, "SELECT count(*) FILTER (WHERE ST_GeometryType(geom)='ST_MultiPoint'),"
                          "count(*) FILTER (WHERE ST_GeometryType(geom)='ST_MultiLineString'),"
                          "count(*) FILTER (WHERE ST_GeometryType(geom)='ST_MultiPolygon') "
                          "FROM milieux.sites_zones;")
        assert zone_checks.stdout.strip() == "4|4|17"
        zone_digest = sql(container, "SELECT md5(string_agg(id::text||':'||"
                          "encode(ST_AsBinary(geom),'hex'),'|' ORDER BY id)) "
                          "FROM milieux.sites_zones;")
        assert zone_digest.stdout.strip() == expected_zone_digest
        links_digest = sql(container, "WITH links AS ("
                           "SELECT 'cours_eau' family,id prestation_id,cours_eau_id object_id FROM milieux.prestations WHERE cours_eau_id IS NOT NULL UNION ALL "
                           "SELECT 'digues',id,digue_id FROM milieux.prestations WHERE digue_id IS NOT NULL UNION ALL "
                           "SELECT 'ah_stockage',id,ah_stockage_id FROM milieux.prestations WHERE ah_stockage_id IS NOT NULL UNION ALL "
                           "SELECT 'ah_ouvrage',id,ah_ouvrage_id FROM milieux.prestations WHERE ah_ouvrage_id IS NOT NULL UNION ALL "
                           "SELECT 'sites_terrestres',id,site_terrestre_id FROM milieux.prestations WHERE site_terrestre_id IS NOT NULL UNION ALL "
                           "SELECT 'sites_zones',id,site_zone_id FROM milieux.prestations WHERE site_zone_id IS NOT NULL) "
                           "SELECT md5(string_agg(family||':'||prestation_id::text||':'||object_id::text,',' "
                           "ORDER BY family,prestation_id::text,object_id::text)) FROM links;")
        assert links_digest.stdout.strip() == expected_links_digest
        checks = (
            "SELECT count(*) FROM milieux.ah_stockage a JOIN milieux.ah_stockage b "
            "ON a.id<b.id AND ST_Intersects(a.geom,b.geom) "
            "WHERE ST_Area(ST_Intersection(a.geom,b.geom))>0.001",
            "SELECT count(*) FROM milieux.sites_terrestres a JOIN milieux.sites_terrestres b "
            "ON a.id<b.id AND ST_Intersects(a.geom,b.geom) "
            "WHERE ST_Area(ST_Intersection(a.geom,b.geom))>0.001",
            "SELECT count(*) FROM milieux.ah_stockage a JOIN milieux.sites_terrestres b "
            "ON ST_Intersects(a.geom,b.geom) "
            "WHERE ST_Area(ST_Intersection(a.geom,b.geom))>0.001",
            "SELECT count(*) FROM milieux.sites_zones z JOIN milieux.sites_terrestres s "
            "ON s.id=z.site_terrestre_id WHERE NOT ST_Covers(s.geom,z.geom)",
            "SELECT count(*) FROM milieux.ah_ouvrage o JOIN milieux.ah_stockage s "
            "ON s.ah_id=o.ah_id WHERE ST_Distance(o.geom,ST_Boundary(s.geom))>0.001",
        )
        combined = "SELECT " + ",".join("(" + query + ")" for query in checks) + ";"
        assert sql(container, combined).stdout.strip() == "0|0|0|0|0"
        print("Installation neuve PostGIS : 100 prestations, 100 liens, "
              "cinq contrôles topologiques à zéro")
    finally:
        command("docker", "stop", container, check=False)


if __name__ == "__main__":
    main()
    if "--postgis" in sys.argv:
        check_postgis()
