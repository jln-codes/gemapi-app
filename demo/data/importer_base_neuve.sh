#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 1 || ! $1 =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ || $1 =~ ^(postgres|template[01])$ ]]; then
    echo "Usage : importer_base_neuve.sh NOM_BASE_LOCALE_VIDE" >&2
    exit 2
fi
db=$1
here=$(cd "$(dirname "$0")" && pwd)
socket=${PGHOST:-/var/run/postgresql}
[[ $socket = /* && $socket != *,* && -d $socket ]] || { echo "Socket PostgreSQL local requis" >&2; exit 2; }
unset PGHOSTADDR PGSERVICE
# Assembler avant connexion. Une transaction couvre le schéma et toutes les données.
batch=$(mktemp)
trap 'rm -f "$batch"' EXIT
cat > "$batch" <<'SQL'
DO $guard$
BEGIN
    IF inet_server_addr() IS NOT NULL OR EXISTS (
        SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT LIKE 'pg\_%' AND n.nspname <> 'information_schema'
          AND c.relkind IN ('r','p','v','m','S','f')
          AND NOT EXISTS (SELECT FROM pg_depend d WHERE d.classid='pg_class'::regclass
                          AND d.objid=c.oid AND d.deptype='e')
    ) THEN RAISE EXCEPTION 'Base locale vide requise'; END IF;
END $guard$;
SQL
for file in ../../model/schema.sql 01_techniciens.sql 03_communes.sql 04_prestataires.sql \
    09_ah.sql 10_sites_terrestres.sql 11_cours_eau.sql 12_ah_sections.sql digues.sql \
    14_patrimoine.sql 15_prestations.sql 16_suivi.sql; do
    # Les exports restent exécutables isolément. psql -1 porte leur transaction commune.
    sed -e '/^BEGIN;$/d' -e '/^COMMIT;$/d' "$here/$file" >> "$batch"
    echo 'SET CONSTRAINTS ALL IMMEDIATE; SET CONSTRAINTS ALL DEFERRED;' >> "$batch"
done
psql -X -1 -v ON_ERROR_STOP=1 -h "$socket" -d "$db" -f "$batch"
