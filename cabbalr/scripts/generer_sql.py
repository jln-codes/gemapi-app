#!/usr/bin/env python3
"""Generate initial-load SQL from the eight real CABBALR packages.

No connection to PostgreSQL or Supabase is made. Source packages are immutable
read-only inputs; SQL references are calculated later by the canonical server.
"""
import argparse
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from uuid import UUID

from osgeo import gdal, ogr


ROOT = Path(__file__).resolve().parents[2]
GPKG_DIR = ROOT / "cabbalr" / "gpkg"
SOURCES = {
    "referentiels.gpkg": ("prestations_categorie", "prestataires", "types_prestations"),
    "techniciens.gpkg": ("techniciens",),
    "communes.gpkg": ("communes",),
    "cours_eau.gpkg": ("cours_eau",),
    "ah.gpkg": ("ah", "ah_stockage", "ah_ouvrage", "ah_sections"),
    "sites_terrestres.gpkg": ("sites_terrestres",),
    "sites_zones.gpkg": ("sites_zones",),
    "digues.gpkg": ("digues",),
}
FIELDS = {
    "prestataires": ("id", "nom", "actif"),
    "types_prestations": ("id", "categorie_id", "code", "libelle", "actif"),
    "techniciens": ("id", "nom", "prenom", "login", "actif"),
    "communes": ("id", "insee", "nom", "geom"),
    "cours_eau": ("id", "nom", "type_ecoulement", "direction", "source", "geom"),
    "ah": ("id", "nom"),
    "ah_stockage": ("id", "ah_id", "nom", "categorie", "surface_ha", "geom"),
    "ah_ouvrage": ("id", "ah_id", "nom", "geom"),
    "sites_terrestres": ("id", "nom", "geom"),
    "sites_zones": ("id", "site_terrestre_id", "nom", "type_site", "surface_ha", "geom"),
    "digues": ("id", "nom", "identifiant_externe", "commentaire"),
    "digues_reperes": ("id", "digue_id", "riviere_id", "rive", "debut_fraction", "fin_fraction"),
    "ah_sections": ("id", "ah_id", "cours_eau_id", "debut_fraction", "fin_fraction", "commentaire"),
}
TRACE = ("modifie_par", "date_modification")
TABLES = tuple(sorted((*FIELDS, "prestations_categorie", "statuts_prestations", "prestations")))
STATUSES = {
    "PLANIFIE": ("58554fd0-fcc2-45b6-aa19-cc4a897af3fb", "Planifié"),
    "EN_COURS": ("9ee713ca-13a1-4358-b5d8-fa79627fc256", "En cours"),
    "TERMINE": ("421801d8-30be-4a5a-8e18-cb2b9ac0ea37", "Terminé"),
    "ANNULE": ("fdd48590-aace-4693-946e-80c1f4d8693f", "Annulé"),
}
GEOMETRIES = {"communes": {"MULTIPOLYGON"}, "cours_eau": {"MULTILINESTRING"},
              "ah_stockage": {"POLYGON"}, "ah_ouvrage": {"LINESTRING"},
              "sites_terrestres": {"MULTIPOLYGON"},
              "sites_zones": {"MULTIPOINT", "MULTILINESTRING", "MULTIPOLYGON"}}
EXTRAS = {"sites_terrestres": ("surface_m2", "surface_ha"),
          "sites_zones": ("niveau", "longueur", "entretien", "gestionnaire", "type")}
GROUPS = (
    ("01_referentiels.sql", ("prestataires", "types_prestations")),
    ("02_techniciens.sql", ("techniciens",)),
    ("03_communes.sql", ("communes",)),
    ("04_cours_eau.sql", ("cours_eau",)),
    ("05_ah.sql", ("ah", "ah_stockage", "ah_ouvrage")),
    ("06_sites.sql", ("sites_terrestres", "sites_zones")),
    ("07_digues.sql", ("digues", "digues_reperes")),
    ("08_ah_sections.sql", ("ah_sections",)),
)
SQL_FILES = ("00_preparer.sql", *(name for name, _ in GROUPS), "09_verifier.sql")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text(value):
    if "\x00" in str(value):
        raise ValueError("NUL interdit dans un texte PostgreSQL")
    value = str(value).replace("\\", "\\\\").replace("'", "''")
    value = value.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return "E'" + value + "'"


def canonical_uuid(value):
    return str(UUID(str(value)))


def timestamp(value):
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Date sans fuseau : " + str(value))
    return parsed.astimezone(dt.timezone.utc).isoformat(timespec="microseconds")


def literal(field, value):
    if value is None:
        return "NULL"
    if field == "id" or field.endswith("_id"):
        return text(canonical_uuid(value)) + "::uuid"
    if field in ("actif", "direction"):
        if type(value) not in (bool, int) or value not in (0, 1):
            raise ValueError("Booléen hors domaine : " + repr(value))
        return "TRUE" if value else "FALSE"
    if field == "date_modification":
        return text(timestamp(value)) + "::timestamptz"
    if field in ("debut_fraction", "fin_fraction"):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Fraction non finie")
        return repr(value) + "::double precision"
    if field == "surface_ha":
        try:
            number = Decimal(str(value))
        except InvalidOperation as error:
            raise ValueError("Décimal invalide") from error
        if not number.is_finite():
            raise ValueError("Décimal non fini")
        return text(format(number, "f")) + "::numeric"
    if field == "geom":
        return "ST_GeomFromWKB(decode('" + value.hex() + "','hex'),3950)"
    # INSEE remains text, including leading zeros when provided as text.
    return text(value)


def closed_source(path):
    for suffix in ("-wal", "-journal"):
        journal = Path(str(path) + suffix)
        if journal.exists() and journal.stat().st_size:
            raise ValueError(f"Enregistrer et fermer le fichier avant génération : {path.name}{suffix}")


def read_sources():
    ogr.UseExceptions()
    data, metadata = {}, {}
    for filename, layers in SOURCES.items():
        path = GPKG_DIR / filename
        closed_source(path)
        digest = sha(path)
        ds = gdal.OpenEx(str(path), gdal.OF_VECTOR | gdal.OF_READONLY,
                         open_options=["IMMUTABLE=YES"])
        if ds is None:
            raise ValueError("GeoPackage absent : " + filename)
        with sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
            db.row_factory = sqlite3.Row
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Intégrité SQLite : " + filename)
            declared = {r[0] for r in db.execute("SELECT table_name FROM gpkg_contents")}
            if declared != set(layers):
                raise ValueError(f"Couches inattendues dans {filename}: {declared}")
            for name in layers:
                layer = ds.GetLayerByName(name)
                records = [dict(row) for row in db.execute(f'SELECT * FROM "{name}"')]
                for row in records:
                    row["id"] = canonical_uuid(row["id"])
                    if name == "cours_eau" and (not row["nom"] or not row["nom"].strip()):
                        raise ValueError("Nom de cours d’eau obligatoire : " + row["id"])
                records.sort(key=lambda r: r["id"])
                if len({r["id"] for r in records}) != len(records):
                    raise ValueError("UUID dupliqué : " + name)
                columns = {row[1]: row[2] for row in db.execute(f'PRAGMA table_info("{name}")')}
                for row in records:
                    if name in GEOMETRIES:
                        feature = layer.GetFeature(row["fid"])
                        geometry = feature.GetGeometryRef()
                        if (layer.GetSpatialRef().GetAuthorityCode(None) != "3950"
                                or geometry is None or geometry.IsEmpty() or not geometry.IsValid()
                                or geometry.GetCoordinateDimension() != 2 or geometry.IsMeasured()
                                or geometry.GetGeometryName() not in GEOMETRIES[name]):
                            raise ValueError(f"Géométrie incompatible : {name}/{row['id']}")
                        row["geom"] = bytes(geometry.ExportToWkb(ogr.wkbNDR))
                        geometry = feature = None
                data[name] = records
                metadata[name] = {"file": filename, "columns": columns, "count": len(records)}
                layer = None
        ds = None
        closed_source(path)
        if digest != sha(path):
            raise ValueError("Source modifiée pendant la lecture : " + filename)
        metadata[filename] = {"sha256": digest}
    return data, metadata


def validate_relations(data):
    for child, field, parent in (
        ("types_prestations", "categorie_id", "prestations_categorie"),
        ("ah_stockage", "ah_id", "ah"), ("ah_ouvrage", "ah_id", "ah"),
        ("ah_sections", "ah_id", "ah"), ("ah_sections", "cours_eau_id", "cours_eau"),
        ("sites_zones", "site_terrestre_id", "sites_terrestres"),
        ("digues", "riviere_id", "cours_eau"),
    ):
        ids = {row["id"] for row in data[parent]}
        for row in data[child]:
            if row.get(field) is None or canonical_uuid(row[field]) not in ids:
                raise ValueError(f"Parent absent : {child}/{row['id']}/{field}")
    owners = [canonical_uuid(r["ah_id"]) for r in data["ah_stockage"]]
    if len(owners) != len(set(owners)):
        raise ValueError("Plusieurs stockages pour un AH")
    for table in ("digues", "ah_sections"):
        for row in data[table]:
            if not 0 <= row["debut_fraction"] < row["fin_fraction"] <= 1:
                raise ValueError(f"Fractions invalides : {table}/{row['id']}")
    for row in data["ah_sections"]:
        if row.get("revision_validation") not in (None, 1):
            raise ValueError("Une révision historique exige une procédure distincte, pas un import initial")


def prepare_data(data):
    """Flattened map export -> explicit parent and reference inputs only."""
    references = data["digues"]
    parents = {}
    for row in references:
        parent = canonical_uuid(row["digue_id"])
        candidate = {"id": parent, "nom": row["digue_nom"],
                     "modifie_par": row.get("modifie_par"), "date_modification": row.get("date_modification")}
        if parent in parents and candidate != parents[parent]:
            raise ValueError("Informations contradictoires pour la digue " + parent)
        parents[parent] = candidate
    data = dict(data)
    data["digues_reperes"] = references
    data["digues"] = sorted(parents.values(), key=lambda r: r["id"])
    return data


def guard(token):
    return ("DO $cabbalr_guard$ BEGIN\n"
            " IF current_setting('sig_prestations.cabbalr_load',true) IS DISTINCT FROM " + text(token) + " THEN\n"
            "  RAISE EXCEPTION 'Exécuter 00_preparer.sql puis les fichiers suivants dans la même connexion';\n"
            " END IF;\nEND $cabbalr_guard$;\n")


def row_values(table, row):
    fields = (*FIELDS[table], *TRACE)
    return fields, [literal(field, row.get(field)) for field in fields]


def category_check(data):
    values = ",\n".join("(" + ",".join((literal("id", r["id"]), text(r["libelle"]), str(int(r["ordre"])))) + ")"
                          for r in data["prestations_categorie"])
    return f""" IF EXISTS (
   WITH expected(id,libelle,ordre) AS (VALUES {values})
   (SELECT id,libelle,ordre FROM milieux.prestations_categorie EXCEPT SELECT * FROM expected)
   UNION ALL
   (SELECT * FROM expected EXCEPT SELECT id,libelle,ordre FROM milieux.prestations_categorie)
 ) THEN RAISE EXCEPTION 'Catégories initiales incompatibles : UUID, libellés ou ordre'; END IF;"""


def prelude(data, token):
    tables_sql = ",".join("milieux." + t for t in TABLES)
    allowed = ",".join(text(t) for t in TABLES)
    statuses = ",".join(f"({text(uid)}::uuid,{text(code)},{text(label)})"
                        for code, (uid, label) in sorted(STATUSES.items()))
    return f"""-- CABBALR : installation initiale canonique uniquement. Lire README.md.
BEGIN;
SET LOCAL standard_conforming_strings=on;
SET LOCAL client_encoding='UTF8';
SET LOCAL TimeZone='UTC';
SET LOCAL lock_timeout='10s';
SET LOCAL statement_timeout='120s';
DO $postgis$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_catalog.pg_extension WHERE extname='postgis') THEN
  RAISE EXCEPTION 'Installer PostGIS puis model/schema.sql avant ce chargement';
 END IF;
END $postgis$;
SELECT pg_catalog.set_config('search_path',pg_catalog.format('pg_catalog,%I,milieux',n.nspname),true)
 FROM pg_catalog.pg_extension e JOIN pg_catalog.pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='postgis';
LOCK TABLE {tables_sql} IN SHARE ROW EXCLUSIVE MODE;
DO $initial$ DECLARE t text; present boolean; BEGIN
 IF EXISTS(SELECT FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='milieux' AND c.relkind IN ('r','p') AND c.relname NOT IN ({allowed})) THEN
  RAISE EXCEPTION 'Tables métier inattendues : le schéma canonique courant est requis';
 END IF;
 FOREACH t IN ARRAY ARRAY[{allowed}] LOOP
  IF t NOT IN ('prestations_categorie','statuts_prestations') THEN
   EXECUTE format('SELECT EXISTS(SELECT FROM milieux.%I)',t) INTO present;
   IF present THEN RAISE EXCEPTION 'Chargement initial refusé : table milieux.% non vide',t; END IF;
  END IF;
 END LOOP;
{category_check(data)}
 IF EXISTS(WITH expected(id,code,libelle) AS (VALUES {statuses})
   (SELECT id,code,libelle FROM milieux.statuts_prestations EXCEPT SELECT * FROM expected)
   UNION ALL (SELECT * FROM expected EXCEPT SELECT id,code,libelle FROM milieux.statuts_prestations)) THEN
  RAISE EXCEPTION 'Statuts initiaux incompatibles';
 END IF;
 IF EXISTS(SELECT FROM pg_catalog.pg_trigger WHERE tgrelid IN
      (SELECT c.oid FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='milieux')
      AND tgenabled NOT IN ('O','A')) OR EXISTS(SELECT FROM pg_catalog.pg_constraint
      WHERE connamespace='milieux'::regnamespace AND NOT convalidated) THEN
  RAISE EXCEPTION 'Triggers ou contraintes désactivés avant import';
 END IF;
 IF EXISTS(SELECT FROM pg_catalog.pg_trigger WHERE tgname IN ('site_complete_parent','site_complete_zone')
      AND tgrelid IN ('milieux.sites_terrestres'::regclass,'milieux.sites_zones'::regclass)) OR
    (SELECT count(*) FROM pg_catalog.pg_attribute WHERE attrelid='milieux.cours_eau'::regclass
      AND attname IN ('section','valide') AND attgenerated='s')<>2 THEN
  RAISE EXCEPTION 'Schéma canonique courant requis : cardinalités et colonnes générées';
 END IF;
END $initial$;
-- Suspension ciblée de la traçabilité seulement ; les préparations et FK restent actives.
""" + "\n".join(f"ALTER TABLE milieux.{t} DISABLE TRIGGER tr_stamp_{t};" for t in FIELDS) + f"\nSELECT pg_catalog.set_config('sig_prestations.cabbalr_load',{text(token)},true);\n"


def postlude(data, token):
    counts = {table: len(data[table]) for table in FIELDS}
    counts.update(prestations_categorie=len(data["prestations_categorie"]), statuts_prestations=4, prestations=0)
    expected = ",".join(f"({text(t)},{n})" for t, n in sorted(counts.items()))
    return guard(token) + "\n-- Épuiser les événements différés avant les ALTER TABLE de réactivation.\nSET CONSTRAINTS ALL IMMEDIATE;\n" + "\n".join(f"ALTER TABLE milieux.{t} ENABLE TRIGGER tr_stamp_{t};" for t in FIELDS) + f"""
DO $verify$ DECLARE r record; actual bigint; BEGIN
 FOR r IN SELECT * FROM (VALUES {expected}) AS expected(table_name,n) LOOP
  EXECUTE format('SELECT count(*) FROM milieux.%I',r.table_name) INTO actual;
  IF actual<>r.n THEN RAISE EXCEPTION 'Effectif % : % au lieu de %',r.table_name,actual,r.n; END IF;
 END LOOP;
 IF EXISTS(SELECT FROM milieux.ah_sections_carte WHERE etat_reference<>'CONFORME') OR
    EXISTS(SELECT FROM milieux.digues_carte WHERE etat_referentiel<>'CONFORME') THEN
  RAISE EXCEPTION 'Référence hydrographique non conforme';
 END IF;
 IF EXISTS(SELECT FROM pg_catalog.pg_trigger WHERE tgrelid IN
      (SELECT c.oid FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='milieux')
      AND tgenabled NOT IN ('O','A')) THEN
  RAISE EXCEPTION 'Trigger non réactivé : transaction annulée';
 END IF;
END $verify$;
SELECT 'ah_sections' AS controle,count(*) AS conformes FROM milieux.ah_sections_carte WHERE etat_reference='CONFORME'
 UNION ALL SELECT 'digues_reperes',count(*) FROM milieux.digues_carte WHERE etat_referentiel='CONFORME';
COMMIT;
"""


def build():
    source, metadata = read_sources()
    validate_relations(source)
    data = prepare_data(source)
    model_sql = (ROOT / "model/schema.sql").read_text(encoding="utf-8").replace("\r\n", "\n")
    manifest = {"schema": "milieux", "model_sha256": hashlib.sha256(model_sql.encode("utf-8")).hexdigest(),
                "sources": {f: metadata[f] for f in sorted(SOURCES)},
                "counts": {t: len(rows) for t, rows in sorted(data.items())}}
    token = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()
    generated = {"00_preparer.sql": prelude(data, token)}
    for filename, tables in GROUPS:
        lines = ["-- CABBALR : fragment du chargement initial, après 00_preparer.sql.\n", guard(token)]
        for table in tables:
            for row in data[table]:
                fields, values = row_values(table, row)
                lines.append(f"INSERT INTO milieux.{table} ({','.join(fields)}) VALUES ({','.join(values)});\n")
        generated[filename] = "".join(lines)
    generated["09_verifier.sql"] = postlude(data, token)
    inventory = {"scope": "Attributs hors modèle canonique ; destination à valider, aucun SQL de conservation appliqué.", "layers": {}}
    for table, fields in EXTRAS.items():
        inventory["layers"][table] = {"columns": {f: metadata[table]["columns"][f] for f in fields},
            "rows": [{"id": row["id"], **{f: row[f] for f in fields}} for row in source[table]]}
    # Recheck the complete set, including files read at the start of generation.
    for filename in SOURCES:
        path = GPKG_DIR / filename
        closed_source(path)
        if sha(path) != metadata[filename]["sha256"]:
            raise ValueError("Source modifiée pendant la génération : " + filename)
    return generated, manifest, inventory


def generate(directory):
    generated, manifest, inventory = build()
    directory.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for name, content in generated.items():
        payload = content.encode("utf-8")
        (directory / name).write_bytes(payload)
        checksums[name] = hashlib.sha256(payload).hexdigest()
    (directory / "manifest.json").write_bytes((json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    inventory_path = directory.parent / "gpkg" / "attributs_complementaires.json"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_path.write_bytes((json.dumps(inventory, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    for filename, path in (("manifest.json", directory / "manifest.json"),
                           ("../gpkg/attributs_complementaires.json", inventory_path)):
        checksums[filename] = sha(path)
    (directory / "SHA256SUMS").write_bytes("".join(f"{checksums[n]}  {n}\n" for n in sorted(checksums)).encode("ascii"))
    return checksums


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "cabbalr/sql")
    args = parser.parse_args()
    checksums = generate(args.output_dir)
    print(f"{len(SQL_FILES)} SQL générés ; empreintes dans {args.output_dir / 'SHA256SUMS'}")


if __name__ == "__main__":
    main()
