-- CABBALR : installation initiale canonique uniquement. Lire README.md.
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
LOCK TABLE milieux.ah,milieux.ah_ouvrage,milieux.ah_sections,milieux.ah_stockage,milieux.communes,milieux.cours_eau,milieux.digues,milieux.digues_reperes,milieux.prestataires,milieux.prestations,milieux.prestations_categorie,milieux.sites_terrestres,milieux.sites_zones,milieux.statuts_prestations,milieux.techniciens,milieux.types_prestations IN SHARE ROW EXCLUSIVE MODE;
DO $initial$ DECLARE t text; present boolean; BEGIN
 IF EXISTS(SELECT FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='milieux' AND c.relkind IN ('r','p') AND c.relname NOT IN (E'ah',E'ah_ouvrage',E'ah_sections',E'ah_stockage',E'communes',E'cours_eau',E'digues',E'digues_reperes',E'prestataires',E'prestations',E'prestations_categorie',E'sites_terrestres',E'sites_zones',E'statuts_prestations',E'techniciens',E'types_prestations')) THEN
  RAISE EXCEPTION 'Tables métier inattendues : le schéma canonique courant est requis';
 END IF;
 FOREACH t IN ARRAY ARRAY[E'ah',E'ah_ouvrage',E'ah_sections',E'ah_stockage',E'communes',E'cours_eau',E'digues',E'digues_reperes',E'prestataires',E'prestations',E'prestations_categorie',E'sites_terrestres',E'sites_zones',E'statuts_prestations',E'techniciens',E'types_prestations'] LOOP
  IF t NOT IN ('prestations_categorie','statuts_prestations') THEN
   EXECUTE format('SELECT EXISTS(SELECT FROM milieux.%I)',t) INTO present;
   IF present THEN RAISE EXCEPTION 'Chargement initial refusé : table milieux.% non vide',t; END IF;
  END IF;
 END LOOP;
 IF EXISTS (
   WITH expected(id,libelle,ordre) AS (VALUES (E'4946680e-3547-5f25-8508-2929a7f7a79e'::uuid,E'Entretien manuel',2),
(E'60410105-fbdd-5890-9d20-a331b4e61e88'::uuid,E'Génie écologique',3),
(E'ae1b972a-e127-5216-9660-7c66583eb893'::uuid,E'Plantations',4),
(E'cf2572fb-9365-5ac5-bdf4-0d66581d9aaa'::uuid,E'Entretien mécanique',1))
   (SELECT id,libelle,ordre FROM milieux.prestations_categorie EXCEPT SELECT * FROM expected)
   UNION ALL
   (SELECT * FROM expected EXCEPT SELECT id,libelle,ordre FROM milieux.prestations_categorie)
 ) THEN RAISE EXCEPTION 'Catégories initiales incompatibles : UUID, libellés ou ordre'; END IF;
 IF EXISTS(WITH expected(id,code,libelle) AS (VALUES (E'fdd48590-aace-4693-946e-80c1f4d8693f'::uuid,E'ANNULE',E'Annulé'),(E'9ee713ca-13a1-4358-b5d8-fa79627fc256'::uuid,E'EN_COURS',E'En cours'),(E'58554fd0-fcc2-45b6-aa19-cc4a897af3fb'::uuid,E'PLANIFIE',E'Planifié'),(E'421801d8-30be-4a5a-8e18-cb2b9ac0ea37'::uuid,E'TERMINE',E'Terminé'))
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
ALTER TABLE milieux.prestataires DISABLE TRIGGER tr_stamp_prestataires;
ALTER TABLE milieux.types_prestations DISABLE TRIGGER tr_stamp_types_prestations;
ALTER TABLE milieux.techniciens DISABLE TRIGGER tr_stamp_techniciens;
ALTER TABLE milieux.communes DISABLE TRIGGER tr_stamp_communes;
ALTER TABLE milieux.cours_eau DISABLE TRIGGER tr_stamp_cours_eau;
ALTER TABLE milieux.ah DISABLE TRIGGER tr_stamp_ah;
ALTER TABLE milieux.ah_stockage DISABLE TRIGGER tr_stamp_ah_stockage;
ALTER TABLE milieux.ah_ouvrage DISABLE TRIGGER tr_stamp_ah_ouvrage;
ALTER TABLE milieux.sites_terrestres DISABLE TRIGGER tr_stamp_sites_terrestres;
ALTER TABLE milieux.sites_zones DISABLE TRIGGER tr_stamp_sites_zones;
ALTER TABLE milieux.digues DISABLE TRIGGER tr_stamp_digues;
ALTER TABLE milieux.digues_reperes DISABLE TRIGGER tr_stamp_digues_reperes;
ALTER TABLE milieux.ah_sections DISABLE TRIGGER tr_stamp_ah_sections;
SELECT pg_catalog.set_config('sig_prestations.cabbalr_load',E'f26384cb88fcf9141846eb7d08cad800ea38ed5b9e885412cd1a0bca7668291b',true);
