-- roles_milieux.sql — PostgreSQL 16+ / schémas milieux, public et referentiel
-- À exécuter par l'administrateur de la base, APRÈS model/schema.sql.
-- Ne crée aucun utilisateur individuel et ne modifie aucune fiche technicien.
BEGIN;
SELECT pg_catalog.set_config('search_path',pg_catalog.format('pg_catalog,%I,milieux',n.nspname),true)
FROM pg_catalog.pg_extension e JOIN pg_catalog.pg_namespace n ON n.oid=e.extnamespace
WHERE e.extname='postgis';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='milieux_consultation') THEN
    CREATE ROLE milieux_consultation NOLOGIN INHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='milieux_prestations') THEN
    CREATE ROLE milieux_prestations NOLOGIN INHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='milieux_patrimoine') THEN
    CREATE ROLE milieux_patrimoine NOLOGIN INHERIT;
  END IF;
END $$;

-- Hiérarchie ; les droits sont cumulés.
GRANT milieux_consultation TO milieux_prestations;
GRANT milieux_prestations TO milieux_patrimoine;

GRANT USAGE ON SCHEMA milieux, public, referentiel TO milieux_consultation;
-- PostGIS peut être installé dans public ou extensions : ne pas le supposer.
DO $$ DECLARE extension_schema text; BEGIN
  SELECT n.nspname INTO STRICT extension_schema FROM pg_extension e
  JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='postgis';
  EXECUTE format('GRANT USAGE ON SCHEMA %I TO milieux_consultation',extension_schema);
END $$;

-- Droit de lecture commun aux trois profils (par héritage).
GRANT SELECT ON TABLE
  public.troncons,
  public.mobilier,
  public.cheminements,
  public.vegetation,
  public.ouvrages_particuliers,
  public.equipements_mesure,
  public.ouvrages_hydrauliques,
  public.desordres,
  public.observations,
  public.photos,
  public.equipements_mesure__desordres,
  public.ouvrages_hydrauliques__desordres,
  public.ouvrages_particuliers__desordres,
  public.ouvrages_hydrauliques__objets_lies,
  milieux.prestations,
  milieux.ah, milieux.ah_stockage, milieux.ah_ouvrage,
  milieux.sites_terrestres, milieux.cours_eau,
  milieux.digues, milieux.digues_reperes, milieux.ah_sections,
  milieux.techniciens, milieux.prestataires, milieux.communes,
  milieux.prestations_categorie, milieux.types_prestations, milieux.statuts_prestations,
  milieux.prestations_fiches, milieux.prestations_carte, milieux.digues_carte,
  milieux.ah_sections_carte,
  milieux.prestations__ah, milieux.prestations__sites_terrestres
TO milieux_consultation;

GRANT SELECT ON ALL TABLES IN SCHEMA referentiel TO milieux_consultation;

GRANT EXECUTE ON FUNCTION
  milieux.cours_eau_reference_admissible(geometry,boolean,boolean),
  milieux.ah_sections_candidates(uuid)
TO milieux_consultation;

GRANT EXECUTE ON FUNCTION milieux.mesures07_resoudre(geometry,uuid,uuid,uuid,uuid,uuid) TO milieux_consultation;

-- Le gestionnaire de prestations modifie uniquement les prestations.
GRANT INSERT, UPDATE, DELETE ON TABLE
  milieux.prestations
TO milieux_prestations;

-- Le gestionnaire du patrimoine modifie en plus les objets patrimoniaux.
GRANT INSERT, UPDATE, DELETE ON TABLE
  public.troncons,
  public.mobilier,
  public.cheminements,
  public.vegetation,
  public.ouvrages_particuliers,
  public.equipements_mesure,
  public.ouvrages_hydrauliques,
  public.desordres,
  public.observations,
  public.photos,
  public.equipements_mesure__desordres,
  public.ouvrages_hydrauliques__desordres,
  public.ouvrages_particuliers__desordres,
  public.ouvrages_hydrauliques__objets_lies
TO milieux_patrimoine;
GRANT INSERT, UPDATE, DELETE ON TABLE
  milieux.ah, milieux.ah_stockage, milieux.ah_ouvrage,
  milieux.sites_terrestres, milieux.cours_eau,
  milieux.digues, milieux.digues_reperes, milieux.ah_sections
TO milieux_patrimoine;

GRANT EXECUTE ON FUNCTION
  milieux.digue_enregistrer(uuid,uuid,integer,timestamptz,text,text,text,uuid,text,double precision,double precision,text),
  milieux.digue_supprimer(uuid,integer,timestamptz)
TO milieux_patrimoine;

-- Supprime les privilèges TRUNCATE éventuellement accordés directement
-- à CES TROIS RÔLES (ne révoque pas les droits hérités d'autres rôles).
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA milieux
FROM milieux_consultation, milieux_prestations, milieux_patrimoine;

COMMIT;

-- NOTE : vérifier les privilèges déjà accordés à PUBLIC, anon, authenticated
-- ou aux comptes individuels ; les GRANT ci-dessus ne les annulent pas.
-- Pour les futures tables, mettre à jour ce script et les privilèges par défaut.
