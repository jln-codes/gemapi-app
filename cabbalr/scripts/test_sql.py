#!/usr/bin/env python3
"""Reproducible local tests. Only SQL and schema.sql enter disposable PostGIS."""
import datetime as dt
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from uuid import uuid4

import generer_sql as generator


ROOT = generator.ROOT
EXPECTED = {"prestataires": 6, "techniciens": 10, "communes": 100, "cours_eau": 170,
            "ah": 9, "ah_stockage": 8, "ah_ouvrage": 9, "ah_sections": 8,
            "digues": 15, "digues_reperes": 15, "sites_terrestres": 16, "sites_zones": 41,
            "types_prestations": 9, "prestations_categorie": 4, "statuts_prestations": 4,
            "prestations": 0}


def command(*args, input_text=None, check=True):
    result = subprocess.run(args, input=input_text, text=True, encoding="utf-8", capture_output=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr[-6000:])
    return result


class InitialSql(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.container = "cabbalr-sql-01-" + uuid4().hex[:10]
        command("docker", "run", "--rm", "-d", "--name", cls.container,
                "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgis/postgis:16-3.4")
        cls.addClassCleanup(command, "docker", "stop", cls.container, check=False)
        for _ in range(60):
            if command("docker", "exec", cls.container, "pg_isready", "-h", "127.0.0.1",
                       "-U", "postgres", check=False).returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError("PostGIS jetable non disponible")
        # No GeoPackage is copied or mounted into the server container.
        command("docker", "cp", str(ROOT / "model/schema.sql"), cls.container + ":/tmp/schema.sql")
        command("docker", "cp", str(ROOT / "cabbalr/sql"), cls.container + ":/tmp/cabbalr_sql")
        cls.raw, cls.source_metadata = generator.read_sources()
        cls.data = generator.prepare_data(cls.raw)
        cls.initial_hashes = {name: generator.sha(generator.GPKG_DIR / name) for name in generator.SOURCES}
        cls.database_index = 0

    @classmethod
    def tearDownClass(cls):
        for name, digest in cls.initial_hashes.items():
            if generator.sha(generator.GPKG_DIR / name) != digest:
                raise AssertionError("Source modifiée : " + name)

    @classmethod
    def sql(cls, database, query, check=True):
        return command("docker", "exec", "-i", cls.container, "psql", "-X", "-qAt",
                       "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", database,
                       input_text=query, check=check)

    @classmethod
    def json(cls, database, query):
        return json.loads(cls.sql(database, "SET search_path=pg_catalog,public,extensions,milieux;" + query).stdout,
                          parse_float=Decimal)

    @classmethod
    def fresh(cls, extension_schema):
        cls.database_index += 1
        database = "cabbalr_" + str(cls.database_index)
        cls.sql("postgres", "CREATE DATABASE " + database)
        cls.sql(database, f"CREATE SCHEMA IF NOT EXISTS {extension_schema}; CREATE EXTENSION postgis WITH SCHEMA {extension_schema}")
        command("docker", "exec", cls.container, "psql", "-Xq", "-v", "ON_ERROR_STOP=1",
                "-U", "postgres", "-d", database, "-f", "/tmp/schema.sql")
        return database

    @classmethod
    def load(cls, database):
        args = ["docker", "exec", cls.container, "psql", "-Xq", "-v", "ON_ERROR_STOP=1",
                "-U", "postgres", "-d", database]
        for name in generator.SQL_FILES:
            args.extend(["-f", "/tmp/cabbalr_sql/" + name])
        return command(*args, check=False)

    @classmethod
    def snapshot(cls, database):
        tables = " UNION ALL ".join(
            f"SELECT '{t}' AS name,md5(coalesce(string_agg(to_jsonb(t)::text,'|' ORDER BY id),'')) AS digest FROM milieux.{t} t"
            for t in generator.TABLES)
        return cls.json(database, f"SELECT jsonb_object_agg(name,digest) FROM ({tables}) x")

    def assert_active(self, database):
        inactive = self.sql(database, "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                           "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='milieux' "
                           "AND t.tgenabled NOT IN ('O','A')").stdout.strip()
        self.assertEqual(inactive, "0")

    def assert_contents(self, database):
        for table, n in EXPECTED.items():
            self.assertEqual(self.sql(database, f"SELECT count(*) FROM milieux.{table}").stdout.strip(), str(n), table)
        for table, fields in generator.FIELDS.items():
            if table in generator.GEOMETRIES:
                projection = "to_jsonb(t)-'geom'||jsonb_build_object('_wkb',encode(ST_AsBinary(geom),'hex'))"
            else:
                projection = "to_jsonb(t)"
            saved = self.json(database, f"SELECT jsonb_agg({projection} ORDER BY id) FROM milieux.{table} t")
            by_id = {r["id"]: r for r in saved}
            self.assertEqual(set(by_id), {r["id"] for r in self.data[table]}, table)
            for source in self.data[table]:
                actual = by_id[source["id"]]
                for key in (*fields, *generator.TRACE):
                    expected = source.get(key)
                    if key == "geom":
                        self.assertEqual(actual["_wkb"], expected.hex(), (table, source["id"]))
                    elif expected is None:
                        self.assertIsNone(actual[key], (table, key, source["id"]))
                    elif key == "date_modification":
                        self.assertEqual(dt.datetime.fromisoformat(actual[key]),
                                         dt.datetime.fromisoformat(expected.replace("Z", "+00:00")))
                    elif key == "insee":
                        self.assertEqual(actual[key], str(expected))
                    elif key in ("debut_fraction", "fin_fraction"):
                        self.assertEqual(float(actual[key]), float(expected))
                    elif key == "surface_ha":
                        self.assertEqual(Decimal(str(actual[key])), Decimal(str(expected)))
                    elif key.endswith("_id") or key == "id":
                        self.assertEqual(actual[key], generator.canonical_uuid(expected))
                    else:
                        self.assertEqual(actual[key], expected, (table, key, source["id"]))
        qualified = sum(r.get("direction") == 1 for r in self.raw["cours_eau"])
        self.assertEqual(self.sql(database, "SELECT count(*) FROM milieux.cours_eau WHERE direction IS TRUE").stdout.strip(), str(qualified))
        self.assertEqual(self.sql(database, "SET search_path=pg_catalog,public,extensions,milieux; "
                                  "SELECT count(*) FROM milieux.cours_eau WHERE section IS DISTINCT FROM ST_NumGeometries(geom) "
                                  "OR valide IS DISTINCT FROM (direction IS TRUE AND section=1)").stdout.strip(), "0")
        self.assertEqual(self.sql(database, "SELECT count(*) FROM milieux.sites_terrestres s WHERE NOT EXISTS(SELECT FROM milieux.sites_zones z WHERE z.site_terrestre_id=s.id)").stdout.strip(), "15")
        for table, river, signature in (("ah_sections", "cours_eau_id", "geom_cours_eau_signature"),
                                        ("digues_reperes", "riviere_id", "geom_riviere_signature")):
            bad = self.sql(database, f"SET search_path=pg_catalog,public,extensions,milieux; SELECT count(*) FROM milieux.{table} s "
                           f"JOIN milieux.cours_eau r ON r.id=s.{river} WHERE "
                           "NOT cours_eau_reference_admissible(r.geom,r.direction,r.valide) OR "
                           "ST_AsEWKB(s.geom_reference) IS DISTINCT FROM ST_AsEWKB(ST_LineSubstring(ST_GeometryN(r.geom,1),s.debut_fraction,s.fin_fraction)) OR "
                           f"s.{signature} IS DISTINCT FROM md5(encode(ST_AsEWKB(r.geom),'hex'))").stdout.strip()
            self.assertEqual(bad, "0", table)
        self.assertEqual(self.sql(database, "SELECT count(*) FROM milieux.ah_sections_carte WHERE etat_reference='CONFORME'").stdout.strip(), "8")
        self.assertEqual(self.sql(database, "SELECT count(*) FROM milieux.digues_carte WHERE etat_referentiel='CONFORME'").stdout.strip(), "15")
        self.assert_active(database)

    def test_01_generation_reproductible(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "audits") as folder:
            one, two = Path(folder) / "one/sql", Path(folder) / "two/sql"
            first = generator.generate(one)
            self.assertEqual(first, generator.generate(two))
            for name in (*generator.SQL_FILES, "manifest.json", "SHA256SUMS"):
                self.assertEqual((one / name).read_bytes(), (two / name).read_bytes())
                self.assertEqual((one / name).read_text(encoding="utf-8").replace("\r\n", "\n"),
                                 (ROOT / "cabbalr/sql" / name).read_text(encoding="utf-8").replace("\r\n", "\n"))
            self.assertEqual((one.parent / "gpkg/attributs_complementaires.json")
                             .read_text(encoding="utf-8").replace("\r\n", "\n"),
                             (generator.GPKG_DIR / "attributs_complementaires.json")
                             .read_text(encoding="utf-8").replace("\r\n", "\n"))
            inventory = json.loads((one.parent / "gpkg/attributs_complementaires.json").read_text())
            for table, fields in generator.EXTRAS.items():
                indexed = {r["id"]: r for r in inventory["layers"][table]["rows"]}
                for row in self.raw[table]:
                    self.assertEqual({f: indexed[row["id"]][f] for f in fields}, {f: row[f] for f in fields})

    def test_02_installations_et_refus_reexecution(self):
        for extension_schema in ("public", "extensions"):
            with self.subTest(postgis=extension_schema):
                database = self.fresh(extension_schema)
                loaded = self.load(database)
                self.assertEqual(loaded.returncode, 0, loaded.stderr[-6000:])
                self.assert_contents(database)
                columns = self.sql(database, "SELECT column_name||':'||data_type||':'||is_nullable "
                                   "FROM information_schema.columns WHERE table_schema='milieux' "
                                   "AND table_name='prestations' AND column_name IN ('photo_1','photo_2') "
                                   "ORDER BY column_name").stdout.strip().splitlines()
                self.assertEqual(columns, ["photo_1:text:YES", "photo_2:text:YES"])
                photo = self.sql(database, "SET search_path=pg_catalog,public,extensions,milieux; "
                                 "BEGIN; INSERT INTO milieux.prestations "
                                 "(intitule,type_prestation_id,prestataire_id,statut_id,technicien_id,"
                                 "date_debut,date_fin,cours_eau_id,geom,photo_1,photo_2) "
                                 "SELECT 'Contrôle fictif',t.id,p.id,s.id,u.id,'2026-01-01','2026-01-02',"
                                 "c.id,ST_PointOnSurface(c.geom),'photos/2026/chantier/vue.jpg',NULL "
                                 "FROM milieux.types_prestations t CROSS JOIN milieux.prestataires p "
                                 "CROSS JOIN milieux.statuts_prestations s CROSS JOIN milieux.techniciens u "
                                 "CROSS JOIN milieux.cours_eau c LIMIT 1; "
                                 "SET CONSTRAINTS ALL IMMEDIATE; "
                                 "SELECT photo_1||'|'||coalesce(photo_2,'<NULL>') "
                                 "FROM milieux.prestations; ROLLBACK;").stdout.strip()
                self.assertEqual(photo, "photos/2026/chantier/vue.jpg|<NULL>")
                self.assertEqual(self.sql(database, "SELECT count(*) FROM milieux.prestations").stdout.strip(), "0")
                snapshot = self.snapshot(database)
                replay = self.load(database)
                self.assertNotEqual(replay.returncode, 0)
                self.assertIn("non vide", replay.stderr)
                self.assertEqual(snapshot, self.snapshot(database))
                self.assert_active(database)

    def test_03_preconditions_protegent_donnees_et_categories(self):
        for case in ("existing", "category", "disabled"):
            with self.subTest(case=case):
                database = self.fresh("public")
                if case == "existing":
                    self.sql(database, "INSERT INTO milieux.ah(nom) VALUES ('Objet à préserver')")
                elif case == "category":
                    self.sql(database, "UPDATE milieux.prestations_categorie SET libelle='Autre nomenclature' WHERE ordre=1")
                else:
                    self.sql(database, "ALTER TABLE milieux.ah_sections DISABLE TRIGGER ah_sections_prepare_trg")
                snapshot = self.snapshot(database)
                result = self.load(database)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(snapshot, self.snapshot(database))
                self.assertEqual(self.sql(database, "SELECT count(*) FROM milieux.cours_eau").stdout.strip(), "0")

    def test_04_refus_reference_annule_tout_et_restaure_triggers(self):
        database = self.fresh("extensions")
        before = self.snapshot(database)
        statements = "\n".join((ROOT / "cabbalr/sql" / name).read_text() for name in generator.SQL_FILES[:-1])
        statements += "\nUPDATE milieux.ah_sections SET revision_validation=revision_validation+1,fin_fraction=debut_fraction;\n"
        statements += (ROOT / "cabbalr/sql/09_verifier.sql").read_text()
        refused = self.sql(database, statements, check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Fractions attendues", refused.stderr)
        self.assertEqual(before, self.snapshot(database))
        self.assert_active(database)
        recovered = self.load(database)
        self.assertEqual(recovered.returncode, 0, recovered.stderr[-6000:])
        self.assert_contents(database)

    def test_06_nom_metier_obligatoire(self):
        database = self.fresh("public")
        for value in ("NULL", "''", "'   '", "E'\\t\\n'"):
            result = self.sql(database, "INSERT INTO milieux.cours_eau(nom,source,geom) VALUES (" +
                              value + ",'TEST',ST_GeomFromText('MULTILINESTRING((0 0,1 1))',3950))",
                              check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue("cours_eau_nom_non_vide" in result.stderr or "not-null constraint" in result.stderr,
                            result.stderr)
        self.assertEqual(self.sql(database, "SELECT count(*) FROM milieux.cours_eau").stdout.strip(), "0")
        self.sql(database, "INSERT INTO milieux.cours_eau(nom,source,geom) VALUES "
                 "('Écoulement fictif','TEST',ST_GeomFromText('MULTILINESTRING((0 0,1 1))',3950))")

    def test_05_litteraux_unicode_precision_fuseau_et_null(self):
        source = "Été d'O\"Brien ; \\ chemin\nligne\r\t$texte$"
        database = self.fresh("public")
        query = "SELECT jsonb_build_object('text'," + generator.text(source) + ", 'decimal'," + generator.literal("surface_ha", "0.1000000000000000001") + ", 'date'," + generator.literal("date_modification", "2026-10-25T02:30:00.123456+02:00") + ", 'null'," + generator.literal("direction", None) + ", 'insee'," + generator.literal("insee", "01234") + ")"
        actual = self.json(database, query)
        self.assertEqual(actual["text"], source)
        self.assertEqual(actual["decimal"], Decimal("0.1000000000000000001"))
        self.assertEqual(dt.datetime.fromisoformat(actual["date"]), dt.datetime(2026, 10, 25, 0, 30, 0, 123456, tzinfo=dt.timezone.utc))
        self.assertIsNone(actual["null"])
        self.assertEqual(actual["insee"], "01234")
        for field, value in (("direction", 2), ("date_modification", "2026-10-25T02:30:00"), ("surface_ha", "NaN")):
            with self.assertRaises(ValueError):
                generator.literal(field, value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
