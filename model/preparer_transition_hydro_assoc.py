"""Prepare the pending, one-off HYDRO-ASSOC-01 transition; never connect to a DB.

Definitions come exclusively from schema.sql. Remove this preparation tool once
both existing environments have been upgraded and verified (AGENTS.md).
Usage: python3 model/preparer_transition_hydro_assoc.py
"""

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def transition_sql():
    schema = (ROOT / "model/schema.sql").read_text(encoding="utf-8")

    def statement(pattern):
        match = re.search(pattern, schema, re.S | re.M)
        if match is None:
            raise ValueError(f"Définition canonique absente : {pattern}")
        return match.group(0)

    statements = [
        "BEGIN; SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='60s';",
        "SELECT pg_catalog.set_config('search_path',pg_catalog.format('pg_catalog,%I,milieux,pg_temp',"
        "n.nspname),true) FROM pg_catalog.pg_extension e JOIN pg_catalog.pg_namespace n "
        "ON n.oid=e.extnamespace WHERE e.extname='postgis';",
        "LOCK TABLE milieux.prestations IN ACCESS EXCLUSIVE MODE;",
        "DO $$ BEGIN IF EXISTS (SELECT FROM information_schema.columns WHERE table_schema='milieux' "
        "AND table_name='prestations' AND column_name='ah_section_id') THEN "
        "RAISE EXCEPTION 'Transition déjà appliquée ou état divergent : diagnostiquer avant toute action'; "
        "END IF; END $$;",
        "CREATE TEMP TABLE hydro_before ON COMMIT DROP AS SELECT "
        "(SELECT md5(coalesce(string_agg(to_jsonb(p)::text,'' ORDER BY id),'')) "
        "FROM milieux.prestations p) AS business_signature;",
        "CREATE TEMP TABLE hydro_views_before ON COMMIT DROP AS SELECT oid,relname,relowner,relacl,reloptions "
        "FROM pg_class WHERE oid IN ('milieux.prestations_carte'::regclass,"
        "'milieux.prestations_fiches'::regclass,'milieux.prestations__ah'::regclass);",
        statement(r"ALTER TABLE milieux.prestations ADD COLUMN ah_section_id uuid;"),
        statement(r"COMMENT ON COLUMN milieux.prestations.ah_section_id IS\n'.*?';"),
    ]
    for name in ("prestations_direct_modes", "prestations_direct_geometry"):
        statements.append(f"ALTER TABLE milieux.prestations DROP CONSTRAINT {name};")
        statements.append(statement(rf"ALTER TABLE milieux.prestations ADD CONSTRAINT {name}\n[^;]+;"))
    for name in ("prestations_ah_section_id_fkey",):
        statements.append(statement(rf"ALTER TABLE milieux.prestations ADD CONSTRAINT {name}\n[^;]+;"))
    statements.append(statement(r"CREATE INDEX prestations_ah_section_id_idx[^;]+;"))
    for name in ("assert_prestation_relations", "mesures07_preparer", "prestations_section_admissible"):
        function = statement(rf"CREATE FUNCTION milieux\.{name}\b.*? AS (\$[a-z_]+\$).*?\1;")
        statements.append(function.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
    statements.extend((
        "REVOKE ALL ON FUNCTION milieux.prestations_section_admissible() FROM PUBLIC;",
        statement(r"CREATE TRIGGER prestations_section_admissible_trg[^;]+;"),
    ))
    for name in ("prestations_carte", "prestations_fiches", "prestations__ah"):
        view = statement(rf"CREATE VIEW milieux\.{name}\b.*?;")
        statements.append(view.replace("CREATE VIEW", "CREATE OR REPLACE VIEW", 1))
    fields = ("nombre_points", "longueur_m", "surface_m2", "surface_ha", "type_geometrie",
              "type_geometrie_postgis", "possede_geometrie", "origine_mesures")
    for view in ("prestations_carte", "prestations_fiches"):
        difference = " OR ".join(f"p.{field} IS DISTINCT FROM v.{field}" for field in fields)
        statements.append(
            "DO $$ BEGIN IF EXISTS (SELECT FROM milieux.prestations p "
            f"JOIN milieux.{view} v USING(id) WHERE {difference}) OR "
            f"(SELECT count(*) FROM milieux.{view})<>(SELECT count(*) FROM milieux.prestations) OR "
            f"(SELECT count(*)-count(DISTINCT id) FROM milieux.{view})<>0 THEN "
            f"RAISE EXCEPTION 'Couverture, unicité ou mesures incohérentes dans {view}'; END IF; END $$;")
    statements.extend((
        "DO $$ BEGIN IF (SELECT md5(coalesce(string_agg((to_jsonb(p)-'ah_section_id')::text,'' "
        "ORDER BY id),'')) FROM milieux.prestations p) IS DISTINCT FROM "
        "(SELECT business_signature FROM hydro_before) THEN RAISE EXCEPTION "
        "'Modification inattendue des prestations : annulation'; END IF; "
        "IF EXISTS (SELECT FROM hydro_views_before b JOIN pg_class a ON a.oid=b.oid "
        "WHERE ROW(a.relowner,a.relacl,a.reloptions) IS DISTINCT FROM ROW(b.relowner,b.relacl,b.reloptions)) "
        "THEN RAISE EXCEPTION 'Propriétaire, privilèges ou options de vue modifiés'; END IF; END $$;",
        "COMMIT;",
    ))
    return "-- HYDRO-ASSOC-01 : transition préparée, application réelle soumise à autorisation.\n" + "\n\n".join(statements) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "audits/HYDRO-ASSOC-01/transition.sql")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(transition_sql(), encoding="utf-8")
    print(f"SQL préparé : {args.output}. Aucune connexion ni exécution SQL.")


if __name__ == "__main__":
    main()
