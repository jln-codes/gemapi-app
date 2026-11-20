"""Prepare pending HYDRO data transitions; never connect to PostgreSQL.

Delete this one-off preparation tool after both real transitions are verified.
The original CABBALR input is the pre-cleanup backup, not cours_eau_work/.
"""
import argparse
from pathlib import Path
import re
import sqlite3
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
RENAMES = {
    '33e78301-dc78-5a54-be41-a3ea7d6ff73d': 'Fossé démo A',
    '746637dd-3706-5b78-ae35-9b76fee85d51': 'Écoulement démo B',
    '97e74118-4e72-5d4c-b6fc-f27f5e211444': 'Fossé démo C',
}
PROTECTED = ('prestations', 'ah', 'ah_stockage', 'ah_ouvrage', 'ah_sections', 'digues', 'digues_reperes')
ANONYMOUS = "(nom IS NULL OR nom !~ '[^[:space:]]')"


def literal(value):
    return 'NULL' if value is None else "'" + str(value).replace("'", "''") + "'"


def read_courses(path):
    with sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1', uri=True) as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        rows = [(str(UUID(uid)), name) for uid, name in db.execute('SELECT id,nom FROM cours_eau ORDER BY id')]
    if len(rows) != len({uid for uid, _ in rows}):
        raise ValueError('UUID de cours d’eau dupliqué')
    return rows


def required_name_sql():
    source = (ROOT/'model/schema.sql').read_text(encoding='utf-8')
    match = re.search(r"CONSTRAINT cours_eau_nom_non_vide (CHECK \(nom ~ '[^']+'\))", source)
    if not match:
        raise ValueError('Contrainte canonique de nom absente')
    return ("DO $$ BEGIN IF EXISTS(SELECT FROM milieux.cours_eau WHERE " + ANONYMOUS + ") THEN "
            "RAISE EXCEPTION 'Cours d eau encore anonyme : contrainte refusée'; END IF; END $$;\n"
            "ALTER TABLE milieux.cours_eau ALTER COLUMN nom SET NOT NULL;\n"
            "ALTER TABLE milieux.cours_eau ADD CONSTRAINT cours_eau_nom_non_vide " + match[1] + ';\n')


def common_start():
    # Lock the children as well: a new dependency cannot appear between the
    # check and deletion. No permissions or permanent schema objects are added.
    lock = ','.join('milieux.'+t for t in (*PROTECTED, 'cours_eau'))
    pieces = ["BEGIN; SET LOCAL lock_timeout='5s'; SET LOCAL statement_timeout='120s';\n",
              "SET LOCAL standard_conforming_strings=on; SET LOCAL client_encoding='UTF8';\n",
              f'LOCK TABLE {lock} IN SHARE ROW EXCLUSIVE MODE;\n',
              "DO $$ BEGIN IF EXISTS(SELECT FROM pg_constraint WHERE conrelid='milieux.cours_eau'::regclass "
              "AND conname='cours_eau_nom_non_vide') THEN RAISE EXCEPTION 'Migration déjà appliquée ou état divergent'; END IF; "
              "IF NOT EXISTS(SELECT FROM pg_trigger WHERE tgrelid='milieux.cours_eau'::regclass "
              "AND tgname='tr_stamp_cours_eau' AND tgenabled='O') THEN RAISE EXCEPTION 'Traçabilité inattendue'; END IF; END $$;\n",
              'CREATE TEMP TABLE hydro_protected(table_name text PRIMARY KEY,signature text) ON COMMIT DROP;\n',
              "CREATE TEMP TABLE hydro_security ON COMMIT DROP AS SELECT oid,relowner,relacl,reloptions FROM pg_class "
              "WHERE relnamespace='milieux'::regnamespace AND relkind IN ('r','v');\n"]
    for table in PROTECTED:
        pieces.append("INSERT INTO hydro_protected SELECT " + literal(table) + ",md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY id),'')) FROM milieux."+table+' t;\n')
    return ''.join(pieces)


def common_end():
    return ("DO $$ DECLARE r record; actual text; BEGIN FOR r IN SELECT * FROM hydro_protected LOOP "
            "EXECUTE format('SELECT md5(coalesce(string_agg(to_jsonb(t)::text, %L ORDER BY id), %L)) FROM milieux.%I t','','',r.table_name) INTO actual; "
            "IF actual IS DISTINCT FROM r.signature THEN RAISE EXCEPTION 'Objet métier modifié : %',r.table_name; END IF; END LOOP; "
            "IF EXISTS(SELECT FROM hydro_security b FULL JOIN (SELECT oid,relowner,relacl,reloptions FROM pg_class "
            "WHERE relnamespace='milieux'::regnamespace AND relkind IN ('r','v')) a USING(oid) "
            "WHERE ROW(a.oid,a.relowner,a.relacl,a.reloptions) IS DISTINCT FROM ROW(b.oid,b.relowner,b.relacl,b.reloptions)) "
            "THEN RAISE EXCEPTION 'Privilèges, propriétaires ou vues modifiés'; END IF; END $$;\nCOMMIT;\n")


def demo_sql():
    source = dict(read_courses(ROOT/'demo/gpkg/cours_eau.gpkg'))
    if len(source) != 58 or any(source.get(uid) != name for uid,name in RENAMES.items()):
        raise ValueError('Source Démo non préparée ou effectif divergent')
    values = ',\n'.join(f'({literal(uid)}::uuid,{literal(name)})' for uid,name in RENAMES.items())
    return (common_start() + 'CREATE TEMP TABLE hydro_renames(id uuid PRIMARY KEY,nom text NOT NULL) ON COMMIT DROP;\n'
            'INSERT INTO hydro_renames VALUES '+values+';\n'
            "DO $$ BEGIN IF (SELECT count(*) FROM milieux.cours_eau)<>58 OR "
            "EXISTS((SELECT id FROM milieux.cours_eau WHERE " + ANONYMOUS + ") EXCEPT SELECT id FROM hydro_renames) OR "
            "EXISTS(SELECT id FROM hydro_renames EXCEPT (SELECT id FROM milieux.cours_eau WHERE " + ANONYMOUS + ")) "
            "THEN RAISE EXCEPTION 'UUID anonymes Démo ou effectif divergents'; END IF; END $$;\n"
            "CREATE TEMP TABLE hydro_demo_before ON COMMIT DROP AS SELECT id,to_jsonb(c) AS data FROM milieux.cours_eau c;\n"
            "ALTER TABLE milieux.cours_eau DISABLE TRIGGER tr_stamp_cours_eau;\n"
            "UPDATE milieux.cours_eau c SET nom=r.nom FROM hydro_renames r WHERE c.id=r.id;\n"
            "ALTER TABLE milieux.cours_eau ENABLE TRIGGER tr_stamp_cours_eau;\n" + required_name_sql() +
            "DO $$ BEGIN IF EXISTS(SELECT FROM hydro_demo_before b FULL JOIN milieux.cours_eau c USING(id) "
            "LEFT JOIN hydro_renames r USING(id) WHERE "
            "CASE WHEN r.id IS NULL THEN b.data ELSE jsonb_set(b.data,'{nom}',to_jsonb(r.nom)) END IS DISTINCT FROM to_jsonb(c)) OR "
            "EXISTS(SELECT FROM hydro_renames r LEFT JOIN milieux.cours_eau c USING(id) WHERE c.nom IS DISTINCT FROM r.nom) "
            "THEN RAISE EXCEPTION 'Renommage Démo non conforme'; END IF; END $$;\n" + common_end())


def cabbalr_sql(original):
    rows = read_courses(original)
    removed = {uid for uid,name in rows if name is None or not name.strip()}
    kept = {uid:name for uid,name in rows if uid not in removed}
    if len(rows)!=2299 or len(removed)!=2129 or len(kept)!=170:
        raise ValueError('Inventaire CABBALR attendu : 2299, dont 2129 anonymes et 170 nommés')
    if dict(read_courses(ROOT/'cabbalr/gpkg/cours_eau.gpkg')) != kept:
        raise ValueError('Les UUID ou noms conservés ne correspondent pas à la source nettoyée')
    values = ',\n'.join(f'({literal(uid)}::uuid,{literal(name)},{str(uid in kept).lower()})' for uid,name in rows)
    return (common_start()+
            'CREATE TEMP TABLE hydro_expected(id uuid PRIMARY KEY,nom text,keep boolean NOT NULL) ON COMMIT DROP;\n'
            'INSERT INTO hydro_expected VALUES '+values+';\n'
            "DO $$ BEGIN IF EXISTS(SELECT FROM hydro_expected e FULL JOIN milieux.cours_eau c USING(id) "
            "WHERE e.id IS NULL OR c.id IS NULL OR e.nom IS DISTINCT FROM c.nom) OR "
            "EXISTS(SELECT FROM milieux.cours_eau c JOIN hydro_expected e USING(id) WHERE NOT e.keep AND NOT " + ANONYMOUS.replace('nom','c.nom') + ") "
            "THEN RAISE EXCEPTION 'Inventaire UUID ou noms CABBALR divergent'; END IF; END $$;\n"
            # Discover every FK, including unanticipated consumers, and refuse
            # composite references instead of assuming a harmless dependency.
            "DO $$ DECLARE r record; n bigint; BEGIN FOR r IN SELECT c.conrelid::regclass AS child, "
            "c.conname,c.confdeltype,a.attname,array_length(c.conkey,1) AS arity FROM pg_constraint c "
            "JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=c.conkey[1] "
            "WHERE c.contype='f' AND c.confrelid='milieux.cours_eau'::regclass LOOP "
            "IF r.arity<>1 OR r.confdeltype NOT IN ('a','r') THEN RAISE EXCEPTION 'FK composite ou suppression automatique à diagnostiquer : %',r.conname; END IF; "
            "EXECUTE format('SELECT count(*) FROM %s c JOIN hydro_expected e ON c.%I=e.id WHERE NOT e.keep',r.child,r.attname) INTO n; "
            "IF n<>0 THEN RAISE EXCEPTION 'Cours d eau à supprimer encore référencé par % : %',r.child,n; END IF; END LOOP; END $$;\n"
            "CREATE TEMP TABLE hydro_kept_before ON COMMIT DROP AS SELECT id,to_jsonb(c) AS data FROM milieux.cours_eau c "
            "JOIN hydro_expected e USING(id) WHERE e.keep;\n"
            "DELETE FROM milieux.cours_eau c USING hydro_expected e WHERE c.id=e.id AND NOT e.keep AND " + ANONYMOUS.replace('nom','c.nom') + ';\n' + required_name_sql() +
            "DO $$ BEGIN IF (SELECT count(*) FROM milieux.cours_eau)<>170 OR "
            "EXISTS(SELECT FROM hydro_kept_before b FULL JOIN milieux.cours_eau c USING(id) WHERE b.data IS DISTINCT FROM to_jsonb(c)) "
            "THEN RAISE EXCEPTION 'Effectifs, UUID ou attributs conservés divergents'; END IF; END $$;\n" + common_end())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-cabbalr',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'audits/HYDRO-DEPLOIEMENT-01/migrations')
    args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    for name,sql in (('demo-renommage-noms.sql',demo_sql()),('cabbalr-nettoyage-noms.sql',cabbalr_sql(args.original_cabbalr))):
        (args.output_dir/name).write_text(sql,encoding='utf-8')
        print('Préparé, sans connexion :',name)

if __name__=='__main__':main()
