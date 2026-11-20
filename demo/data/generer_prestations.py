#!/usr/bin/env python3
"""Exporte les prestations actuelles sans recalculer leurs géométries."""

from pathlib import Path

from osgeo import ogr

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "gpkg" / "prestations.gpkg"
SQL = ROOT / "data" / "15_prestations.sql"
PHOTO_FIELDS = ("photo_1", "photo_1_commentaire", "photo_2", "photo_2_commentaire")


def quoted(value):
    return "'" + str(value).replace("'", "''") + "'"


def main():
    """Export the current demo exactly, preserving manually edited geometries.

    No seed geometry, translation or historic topological transform is replayed.
    """
    ogr.UseExceptions()
    source = ogr.Open(str(PACKAGE), 0)
    if source is None:
        raise FileNotFoundError(PACKAGE)
    rows = []
    fields = ("id", "intitule", "type_prestation_id", "prestataire_id",
              "technicien_id", "date_debut", "date_fin", "quantite", "unite",
              "description", "position", "rive", *PHOTO_FIELDS,
              "cours_eau_id", "digue_id", "ah_stockage_id", "ah_ouvrage_id", "site_terrestre_id", "site_zone_id", "ah_section_id")
    for layer in source:
        for feature in layer:
            values = [feature.GetField(name) for name in fields]
            code = feature.GetField("statut")
            geometry = feature.GetGeometryRef()
            if feature.GetField("ah_section_id") and geometry is None:
                raise ValueError(f"La prestation {feature.GetField('id')} sur section AH doit avoir sa géométrie propre")
            if feature.GetField("site_zone_id") and geometry is not None:
                raise ValueError(f"La prestation {feature.GetField('id')} sur zone doit avoir une géométrie NULL")
            if feature.GetField("site_terrestre_id") and (
                    geometry is None or geometry.GetGeometryName() not in
                    ("MULTIPOINT", "MULTILINESTRING", "MULTIPOLYGON")):
                raise ValueError(f"La prestation {feature.GetField('id')} sur site doit être multipartie")
            geom = (f"ST_GeomFromWKB(decode('{geometry.ExportToWkb().hex()}','hex'),3950)"
                    if geometry is not None else "NULL")
            literals = [quoted(value) if value is not None else "NULL" for value in values]
            literals += [f"(SELECT id FROM milieux.statuts_prestations WHERE code={quoted(code)})", geom]
            rows.append((feature.GetField("id"), f"INSERT INTO milieux.prestations ({','.join((*fields, 'statut_id', 'geom'))}) VALUES ({','.join(literals)});"))
    if len(rows) != 100 or len({uid for uid, _ in rows}) != 100:
        raise ValueError("100 UUID de démonstration distincts requis")
    header = ["-- Prestations courantes, coordonnées exactes conservées depuis le GeoPackage.", "BEGIN;",
              "SELECT pg_catalog.set_config('search_path', pg_catalog.format('pg_catalog,%I,%I', n.nspname, 'milieux'), true) FROM pg_catalog.pg_extension e JOIN pg_catalog.pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='postgis';"]
    SQL.write_text("\n".join([*header, *(statement for _, statement in sorted(rows)), "COMMIT;", ""]), encoding="utf-8")
    print("100 prestations exportées sans recalcul des géométries ni attributs")

if __name__ == "__main__":
    main()
