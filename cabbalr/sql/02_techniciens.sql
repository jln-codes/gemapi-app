-- CABBALR : fragment du chargement initial, après 00_preparer.sql.
DO $cabbalr_guard$ BEGIN
 IF current_setting('sig_prestations.cabbalr_load',true) IS DISTINCT FROM E'f26384cb88fcf9141846eb7d08cad800ea38ed5b9e885412cd1a0bca7668291b' THEN
  RAISE EXCEPTION 'Exécuter 00_preparer.sql puis les fichiers suivants dans la même connexion';
 END IF;
END $cabbalr_guard$;
INSERT INTO milieux.techniciens (id,nom,prenom,login,actif,modifie_par,date_modification) VALUES (E'0ce1ed4f-4c91-415a-bc2a-e4ca6e4b756b'::uuid,E'Quentin',E'Benoît',NULL,TRUE,NULL,NULL);
INSERT INTO milieux.techniciens (id,nom,prenom,login,actif,modifie_par,date_modification) VALUES (E'3f023dd1-036b-4bc9-a383-2fc0d9bede09'::uuid,E'Macquet',E'Mickael',NULL,TRUE,NULL,NULL);
INSERT INTO milieux.techniciens (id,nom,prenom,login,actif,modifie_par,date_modification) VALUES (E'711a7d5f-2b45-4a0e-9e59-93d4f0fe2631'::uuid,E'Lamiaux',E'Laeticia',NULL,TRUE,NULL,NULL);
INSERT INTO milieux.techniciens (id,nom,prenom,login,actif,modifie_par,date_modification) VALUES (E'b90a87be-1d4e-4ad9-943d-fbe19bd0f0b4'::uuid,E'Massart',E'Laurent',NULL,TRUE,NULL,NULL);
INSERT INTO milieux.techniciens (id,nom,prenom,login,actif,modifie_par,date_modification) VALUES (E'bb191894-7fd5-496b-80dc-bc24e0a6cb34'::uuid,E'Duval',E'Jérémie',NULL,TRUE,NULL,NULL);
INSERT INTO milieux.techniciens (id,nom,prenom,login,actif,modifie_par,date_modification) VALUES (E'cc47957f-86d9-441f-8fed-55e2591f1387'::uuid,E'Lorion',E'Julien',NULL,TRUE,NULL,NULL);
INSERT INTO milieux.techniciens (id,nom,prenom,login,actif,modifie_par,date_modification) VALUES (E'd9f877d1-7b2b-4c5e-b045-55c1c75ab9d1'::uuid,E'Canoen',E'Vincent',NULL,TRUE,NULL,NULL);
INSERT INTO milieux.techniciens (id,nom,prenom,login,actif,modifie_par,date_modification) VALUES (E'e45844ba-2f94-4b1a-9c53-dfad3c87fbff'::uuid,E'Pruvost',E'Aline',NULL,TRUE,NULL,NULL);
INSERT INTO milieux.techniciens (id,nom,prenom,login,actif,modifie_par,date_modification) VALUES (E'f50ee637-791f-4482-83a8-fa09f4f781d4'::uuid,E'Rolland',E'Tony',NULL,TRUE,NULL,NULL);
INSERT INTO milieux.techniciens (id,nom,prenom,login,actif,modifie_par,date_modification) VALUES (E'fdf7a81b-71c1-4761-880c-7acb9411b9cb'::uuid,E'Sauvage',E'Benoît',NULL,TRUE,NULL,NULL);
