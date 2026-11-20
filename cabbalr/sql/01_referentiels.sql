-- CABBALR : fragment du chargement initial, après 00_preparer.sql.
DO $cabbalr_guard$ BEGIN
 IF current_setting('sig_prestations.cabbalr_load',true) IS DISTINCT FROM E'f26384cb88fcf9141846eb7d08cad800ea38ed5b9e885412cd1a0bca7668291b' THEN
  RAISE EXCEPTION 'Exécuter 00_preparer.sql puis les fichiers suivants dans la même connexion';
 END IF;
END $cabbalr_guard$;
INSERT INTO milieux.prestataires (id,nom,actif,modifie_par,date_modification) VALUES (E'0b6985fb-89fa-574e-b40e-34a6468107a3'::uuid,E'Noeux Environnement',TRUE,NULL,NULL);
INSERT INTO milieux.prestataires (id,nom,actif,modifie_par,date_modification) VALUES (E'4aea38bb-5efa-554a-8788-622366e162aa'::uuid,E'Réagir',TRUE,NULL,NULL);
INSERT INTO milieux.prestataires (id,nom,actif,modifie_par,date_modification) VALUES (E'521e1a33-56ca-50cc-850e-56855e3c0b22'::uuid,E'AVIEE',TRUE,NULL,NULL);
INSERT INTO milieux.prestataires (id,nom,actif,modifie_par,date_modification) VALUES (E'697daa7f-3a79-5296-bce0-75c0c0a5618a'::uuid,E'Régie',TRUE,NULL,NULL);
INSERT INTO milieux.prestataires (id,nom,actif,modifie_par,date_modification) VALUES (E'97f52698-ee36-504d-8c0d-31937769128a'::uuid,E'Chemins vers l''Emploi',TRUE,NULL,NULL);
INSERT INTO milieux.prestataires (id,nom,actif,modifie_par,date_modification) VALUES (E'c3db9c46-44d0-5b05-bba3-7063d24a52a3'::uuid,E'Forêt et Paysages',TRUE,NULL,NULL);
INSERT INTO milieux.types_prestations (id,categorie_id,code,libelle,actif,modifie_par,date_modification) VALUES (E'272003ca-7006-5f4b-b5ac-f6d84281a3e2'::uuid,E'cf2572fb-9365-5ac5-bdf4-0d66581d9aaa'::uuid,E'CURAGE',E'Curage',TRUE,NULL,NULL);
INSERT INTO milieux.types_prestations (id,categorie_id,code,libelle,actif,modifie_par,date_modification) VALUES (E'6d6fa494-e36e-5ba5-bc50-dbf256d4fc7d'::uuid,E'4946680e-3547-5f25-8508-2929a7f7a79e'::uuid,E'ELAGAGE',E'Élagage',TRUE,NULL,NULL);
INSERT INTO milieux.types_prestations (id,categorie_id,code,libelle,actif,modifie_par,date_modification) VALUES (E'aae7d72e-377e-5cd8-a0fb-326d7bd03c5a'::uuid,E'60410105-fbdd-5890-9d20-a331b4e61e88'::uuid,E'SUIVI',E'Suivi de milieu',TRUE,NULL,NULL);
INSERT INTO milieux.types_prestations (id,categorie_id,code,libelle,actif,modifie_par,date_modification) VALUES (E'b6ea0cbd-54ef-5bb8-9cc4-42af05fe876e'::uuid,E'cf2572fb-9365-5ac5-bdf4-0d66581d9aaa'::uuid,E'FAUCHE',E'Fauche',TRUE,NULL,NULL);
INSERT INTO milieux.types_prestations (id,categorie_id,code,libelle,actif,modifie_par,date_modification) VALUES (E'cf98e704-4949-54b9-aa02-b65b55e8b83d'::uuid,E'4946680e-3547-5f25-8508-2929a7f7a79e'::uuid,E'EMBACLES',E'Retrait d’embâcles',TRUE,NULL,NULL);
INSERT INTO milieux.types_prestations (id,categorie_id,code,libelle,actif,modifie_par,date_modification) VALUES (E'd2fa2842-9125-5f4a-ad3f-0adffead207c'::uuid,E'60410105-fbdd-5890-9d20-a331b4e61e88'::uuid,E'ETUDE',E'Étude',TRUE,NULL,NULL);
INSERT INTO milieux.types_prestations (id,categorie_id,code,libelle,actif,modifie_par,date_modification) VALUES (E'd8737de6-7a5e-5892-afc4-b51f5e882e26'::uuid,E'cf2572fb-9365-5ac5-bdf4-0d66581d9aaa'::uuid,E'DEBROUSSAILLAGE',E'Débroussaillage',TRUE,NULL,NULL);
INSERT INTO milieux.types_prestations (id,categorie_id,code,libelle,actif,modifie_par,date_modification) VALUES (E'da65d85b-ecf1-5481-bd2a-a47cf9b14544'::uuid,E'60410105-fbdd-5890-9d20-a331b4e61e88'::uuid,E'RESTAURATION',E'Restauration écologique',TRUE,NULL,NULL);
INSERT INTO milieux.types_prestations (id,categorie_id,code,libelle,actif,modifie_par,date_modification) VALUES (E'e2659d31-52c3-5f87-884e-56eedd7e1ee9'::uuid,E'ae1b972a-e127-5216-9660-7c66583eb893'::uuid,E'PLANTATION',E'Plantation',TRUE,NULL,NULL);
