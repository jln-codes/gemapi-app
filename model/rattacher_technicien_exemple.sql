-- rattacher_technicien.sql : modèle de travail pour UN agent.
-- Remplacer les valeurs entre chevrons, puis exécuter avec un rôle administrateur.
-- PRÉREQUIS : roles_milieux.sql appliqué.
-- L'identité QGIS/PostgreSQL est le LOGIN, pas l'UUID du technicien.
-- Ne placez PAS de mot de passe en clair dans ce fichier.

-- Créer le LOGIN séparément, par exemple :
-- CREATE ROLE <login_sql_sans_chevrons> LOGIN INHERIT;
-- Dans psql, définir son mot de passe avec : \password <login_sql_sans_chevrons>
-- (ou utiliser l'authentification institutionnelle configurée par l'admin).
-- Le compte doit ensuite se connecter à cette base avec ce même login.

BEGIN;
-- Remplacer agent.exemple par le vrai nom de compte, IDENTIQUE dans les 2 lignes.
-- IMPORTANT : ce script suppose que le compte LOGIN existe déjà.
REVOKE milieux_consultation, milieux_prestations, milieux_patrimoine
  FROM "agent.exemple";
GRANT milieux_prestations TO "agent.exemple";

-- Utiliser l'UUID exact de la fiche métier, obtenu avec
-- SELECT id, nom, prenom, login FROM gemapi.techniciens ORDER BY nom, prenom;
DO $$
DECLARE n integer;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='agent.exemple' AND rolcanlogin) THEN
    RAISE EXCEPTION 'Compte LOGIN agent.exemple absent';
  END IF;
  UPDATE gemapi.techniciens SET login='agent.exemple'
  WHERE id='00000000-0000-0000-0000-000000000000'::uuid;
  GET DIAGNOSTICS n = ROW_COUNT;
  IF n <> 1 THEN
    RAISE EXCEPTION 'Aucune fiche technicien correspondant à cet UUID';
  END IF;
END $$;
COMMIT;

-- Contrôle manuel :
-- SELECT id, prenom, nom, login FROM gemapi.techniciens WHERE login='agent.exemple';
-- SELECT r.rolname AS profil FROM pg_auth_members m
-- JOIN pg_roles r ON r.oid=m.roleid
-- JOIN pg_roles u ON u.oid=m.member
-- WHERE u.rolname='agent.exemple';
