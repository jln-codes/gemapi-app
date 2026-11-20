DO $cabbalr_guard$ BEGIN
 IF current_setting('sig_prestations.cabbalr_load',true) IS DISTINCT FROM E'f26384cb88fcf9141846eb7d08cad800ea38ed5b9e885412cd1a0bca7668291b' THEN
  RAISE EXCEPTION 'Exécuter 00_preparer.sql puis les fichiers suivants dans la même connexion';
 END IF;
END $cabbalr_guard$;

-- Épuiser les événements différés avant les ALTER TABLE de réactivation.
SET CONSTRAINTS ALL IMMEDIATE;
ALTER TABLE milieux.prestataires ENABLE TRIGGER tr_stamp_prestataires;
ALTER TABLE milieux.types_prestations ENABLE TRIGGER tr_stamp_types_prestations;
ALTER TABLE milieux.techniciens ENABLE TRIGGER tr_stamp_techniciens;
ALTER TABLE milieux.communes ENABLE TRIGGER tr_stamp_communes;
ALTER TABLE milieux.cours_eau ENABLE TRIGGER tr_stamp_cours_eau;
ALTER TABLE milieux.ah ENABLE TRIGGER tr_stamp_ah;
ALTER TABLE milieux.ah_stockage ENABLE TRIGGER tr_stamp_ah_stockage;
ALTER TABLE milieux.ah_ouvrage ENABLE TRIGGER tr_stamp_ah_ouvrage;
ALTER TABLE milieux.sites_terrestres ENABLE TRIGGER tr_stamp_sites_terrestres;
ALTER TABLE milieux.sites_zones ENABLE TRIGGER tr_stamp_sites_zones;
ALTER TABLE milieux.digues ENABLE TRIGGER tr_stamp_digues;
ALTER TABLE milieux.digues_reperes ENABLE TRIGGER tr_stamp_digues_reperes;
ALTER TABLE milieux.ah_sections ENABLE TRIGGER tr_stamp_ah_sections;
DO $verify$ DECLARE r record; actual bigint; BEGIN
 FOR r IN SELECT * FROM (VALUES (E'ah',9),(E'ah_ouvrage',9),(E'ah_sections',8),(E'ah_stockage',8),(E'communes',100),(E'cours_eau',170),(E'digues',15),(E'digues_reperes',15),(E'prestataires',6),(E'prestations',0),(E'prestations_categorie',4),(E'sites_terrestres',16),(E'sites_zones',41),(E'statuts_prestations',4),(E'techniciens',10),(E'types_prestations',9)) AS expected(table_name,n) LOOP
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
