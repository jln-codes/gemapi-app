-- SIG Prestations / PostgreSQL 16+ et PostGIS 3.3+ / installation NEUVE
-- Requiert l'extension postgis, quel que soit son schema d'installation.
-- Ne pas executer sur une base existante avec ces objets.
BEGIN;
CREATE SCHEMA IF NOT EXISTS milieux;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_extension WHERE extname = 'postgis') THEN
    RAISE EXCEPTION 'Extension PostGIS absente : installer postgis avant schema.sql';
  END IF;
END $$;
SELECT pg_catalog.set_config(
  'search_path',
  pg_catalog.format('pg_catalog,%I,%I', n.nspname, 'milieux'),
  true
)
FROM pg_catalog.pg_extension AS e
JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace
WHERE e.extname = 'postgis';
CREATE TABLE milieux.techniciens (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), nom text NOT NULL, prenom text, login text UNIQUE, actif boolean NOT NULL DEFAULT true, modifie_par text, date_modification timestamptz);
CREATE TABLE milieux.communes (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), insee text NOT NULL UNIQUE, nom text NOT NULL, geom geometry(MultiPolygon,3950) NOT NULL, modifie_par text, date_modification timestamptz, CHECK(ST_IsValid(geom) AND NOT ST_IsEmpty(geom) AND ST_NDims(geom)=2));
CREATE TABLE milieux.prestataires (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), nom text NOT NULL, actif boolean NOT NULL DEFAULT true, modifie_par text, date_modification timestamptz);
CREATE TABLE milieux.prestations_categorie (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), libelle text NOT NULL UNIQUE, ordre integer NOT NULL);
INSERT INTO milieux.prestations_categorie (id, libelle, ordre) VALUES
('cf2572fb-9365-5ac5-bdf4-0d66581d9aaa', 'Entretien mécanique', 1),
('4946680e-3547-5f25-8508-2929a7f7a79e', 'Entretien manuel', 2),
('60410105-fbdd-5890-9d20-a331b4e61e88', 'Génie écologique', 3),
('ae1b972a-e127-5216-9660-7c66583eb893', 'Plantations', 4);
CREATE TABLE milieux.types_prestations (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), categorie_id uuid NOT NULL REFERENCES milieux.prestations_categorie(id) ON DELETE RESTRICT, code text NOT NULL UNIQUE, libelle text NOT NULL, actif boolean NOT NULL DEFAULT true, modifie_par text, date_modification timestamptz);
CREATE TABLE milieux.statuts_prestations (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), code text NOT NULL UNIQUE CHECK (code IN ('PLANIFIE','EN_COURS','TERMINE','ANNULE')), libelle text NOT NULL UNIQUE, modifie_par text, date_modification timestamptz);
INSERT INTO milieux.statuts_prestations (id, code, libelle) VALUES
 ('58554fd0-fcc2-45b6-aa19-cc4a897af3fb','PLANIFIE','Planifié'),
 ('9ee713ca-13a1-4358-b5d8-fa79627fc256','EN_COURS','En cours'),
 ('421801d8-30be-4a5a-8e18-cb2b9ac0ea37','TERMINE','Terminé'),
 ('fdd48590-aace-4693-946e-80c1f4d8693f','ANNULE','Annulé');
CREATE TABLE milieux.ah (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), nom text NOT NULL, modifie_par text, date_modification timestamptz);
CREATE TABLE milieux.ah_stockage (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), ah_id uuid NOT NULL UNIQUE REFERENCES milieux.ah(id) ON DELETE RESTRICT, nom text NOT NULL, categorie text, surface_ha numeric, geom geometry(Polygon,3950) NOT NULL, modifie_par text, date_modification timestamptz, CONSTRAINT ah_stockage_geom_contract CHECK (NOT ST_IsEmpty(geom) AND ST_IsValid(geom) AND ST_NDims(geom)=2));
CREATE TABLE milieux.ah_ouvrage (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), ah_id uuid NOT NULL REFERENCES milieux.ah(id) ON DELETE RESTRICT, nom text, geom geometry(LineString,3950) NOT NULL, modifie_par text, date_modification timestamptz, CONSTRAINT ah_ouvrage_geom_contract CHECK (NOT ST_IsEmpty(geom) AND ST_IsValid(geom) AND ST_NDims(geom)=2));
-- Contrôle de type explicite : le typmod MultiPolygon convertirait un Polygon à l'écriture.
CREATE TABLE milieux.sites_terrestres (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), nom text NOT NULL, geom geometry(Geometry,3950) NOT NULL, modifie_par text, date_modification timestamptz, CONSTRAINT sites_terrestres_geom_contract CHECK (NOT ST_IsEmpty(geom) AND ST_IsValid(geom) AND ST_NDims(geom)=2 AND ST_GeometryType(geom)='ST_MultiPolygon'));
CREATE TABLE milieux.sites_zones (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), site_terrestre_id uuid NOT NULL REFERENCES milieux.sites_terrestres(id) ON DELETE RESTRICT, nom text NOT NULL, type_site text, surface_ha numeric, geom geometry(Geometry,3950) NOT NULL, modifie_par text, date_modification timestamptz, CONSTRAINT sites_zones_geom_contract CHECK (NOT ST_IsEmpty(geom) AND ST_IsValid(geom) AND ST_NDims(geom)=2 AND ST_GeometryType(geom) IN ('ST_MultiPoint','ST_MultiLineString','ST_MultiPolygon')));
CREATE TABLE milieux.cours_eau (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), nom text NOT NULL CONSTRAINT cours_eau_nom_non_vide CHECK (nom ~ '[^[:space:]]'), type_ecoulement text, direction boolean, section integer GENERATED ALWAYS AS (ST_NumGeometries(geom)) STORED, valide boolean GENERATED ALWAYS AS (direction IS TRUE AND ST_NumGeometries(geom)=1) STORED NOT NULL, source text NOT NULL, geom geometry(MultiLineString,3950) NOT NULL, modifie_par text, date_modification timestamptz, CHECK(ST_IsValid(geom) AND NOT ST_IsEmpty(geom) AND ST_NDims(geom)=2));
CREATE FUNCTION milieux.cours_eau_qualification() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
    IF ST_AsEWKB(NEW.geom) IS DISTINCT FROM ST_AsEWKB(OLD.geom) THEN
        NEW.direction := NULL;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER hydro_qual_direction BEFORE UPDATE OF geom ON milieux.cours_eau
FOR EACH ROW EXECUTE FUNCTION milieux.cours_eau_qualification();
CREATE TABLE milieux.prestations (cours_eau_id uuid REFERENCES milieux.cours_eau(id) ON DELETE RESTRICT, digue_id uuid, ah_stockage_id uuid REFERENCES milieux.ah_stockage(id) ON DELETE RESTRICT, ah_ouvrage_id uuid REFERENCES milieux.ah_ouvrage(id) ON DELETE RESTRICT, site_terrestre_id uuid REFERENCES milieux.sites_terrestres(id) ON DELETE RESTRICT, site_zone_id uuid REFERENCES milieux.sites_zones(id) ON DELETE RESTRICT, id uuid PRIMARY KEY DEFAULT gen_random_uuid(), intitule text, type_prestation_id uuid NOT NULL REFERENCES milieux.types_prestations(id) ON DELETE RESTRICT, prestataire_id uuid NOT NULL REFERENCES milieux.prestataires(id) ON DELETE RESTRICT, statut_id uuid NOT NULL REFERENCES milieux.statuts_prestations(id) ON DELETE RESTRICT, date_debut date NOT NULL, date_fin date NOT NULL, quantite numeric, unite text, description text, position text NOT NULL DEFAULT 'Indéfini' CONSTRAINT prestations_position_values CHECK (position IN ('Berge','Talus côté rivière / stockage','Crête','Talus côté terre','Indéfini')), rive text NOT NULL DEFAULT 'Indéfinie' CONSTRAINT prestations_rive_values CHECK (rive IN ('Gauche','Droite','Les deux','Indéfinie')), photo_1 text, photo_1_commentaire text, photo_2 text, photo_2_commentaire text, geom geometry(Geometry,3950), technicien_id uuid NOT NULL REFERENCES milieux.techniciens(id) ON DELETE RESTRICT, modifie_par text, date_modification timestamptz, CHECK(date_fin >= date_debut), CONSTRAINT prestations_geom_contract CHECK(geom IS NULL OR (NOT ST_IsEmpty(geom) AND ST_IsValid(geom) AND ST_SRID(geom)=3950 AND ST_NDims(geom)=2 AND ST_GeometryType(geom) IN ('ST_Point','ST_LineString','ST_Polygon','ST_MultiPoint','ST_MultiLineString','ST_MultiPolygon'))));
-- L'ensemble des rattachements et la position sont contrôlés sur l'état final
-- de la transaction, sans ordre de saisie imposé au formulaire QGIS.
ALTER TABLE milieux.prestations ADD COLUMN nombre_points integer,
ADD COLUMN longueur_m double precision,
ADD COLUMN surface_m2 double precision,
ADD COLUMN surface_ha double precision GENERATED ALWAYS AS(surface_m2/10000.0) STORED,
ADD COLUMN type_geometrie text,
ADD COLUMN type_geometrie_postgis text,
ADD COLUMN possede_geometrie boolean NOT NULL DEFAULT false,
ADD COLUMN origine_mesures text NOT NULL DEFAULT 'Aucune géométrie';
-- Sept modes directs ; la FK section AH est ajoutée après sa table cible.
ALTER TABLE milieux.prestations ADD COLUMN ah_section_id uuid;
COMMENT ON COLUMN milieux.prestations.ah_section_id IS
'Section AH directement rattachée ; géométrie propre de la prestation obligatoire, aucun héritage de geom_reference.';

ALTER TABLE milieux.prestations ADD CONSTRAINT prestations_direct_modes
CHECK (num_nonnulls(cours_eau_id,digue_id,ah_stockage_id,ah_ouvrage_id,site_terrestre_id,site_zone_id,ah_section_id)<=1);
ALTER TABLE milieux.prestations ADD CONSTRAINT prestations_direct_geometry
CHECK ((cours_eau_id IS NULL AND digue_id IS NULL AND site_terrestre_id IS NULL AND ah_section_id IS NULL) OR geom IS NOT NULL);
ALTER TABLE milieux.prestations ADD CONSTRAINT prestations_zone_geometry
CHECK (site_zone_id IS NULL OR geom IS NULL);
ALTER TABLE milieux.prestations ADD CONSTRAINT prestations_site_multi_geometry
CHECK (site_terrestre_id IS NULL OR ST_GeometryType(geom) IN
       ('ST_MultiPoint','ST_MultiLineString','ST_MultiPolygon'));
CREATE FUNCTION milieux.assert_prestation_relations(prestation_uuid uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path FROM CURRENT AS $relations_assert$
DECLARE p milieux.prestations%ROWTYPE;
BEGIN
    SELECT * INTO p FROM milieux.prestations WHERE id=prestation_uuid FOR UPDATE;
    IF NOT FOUND THEN RETURN; END IF;
    IF num_nonnulls(p.cours_eau_id,p.digue_id,p.ah_stockage_id,p.ah_ouvrage_id,p.site_terrestre_id,p.site_zone_id,p.ah_section_id)<>1 THEN
        RAISE EXCEPTION 'Exactement un mode de rattachement patrimonial est obligatoire pour %',p.id USING ERRCODE='23514';
    END IF;
    IF (p.position<>'Indéfini' OR p.rive<>'Indéfinie') AND p.cours_eau_id IS NULL AND p.digue_id IS NULL AND p.ah_ouvrage_id IS NULL AND p.ah_section_id IS NULL THEN
        RAISE EXCEPTION 'Position ou rive incompatible avec le rattachement patrimonial' USING ERRCODE='23514';
    END IF;
END $relations_assert$;
CREATE FUNCTION milieux.prestation_relations_complete() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, milieux AS $relations_trigger$
BEGIN
    IF TG_OP <> 'DELETE' THEN PERFORM milieux.assert_prestation_relations(NEW.id); END IF;
    RETURN NULL;
END $relations_trigger$;
CREATE CONSTRAINT TRIGGER prestation_relations_parent AFTER INSERT OR UPDATE ON milieux.prestations
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION milieux.prestation_relations_complete();
-- Un site peut n'avoir aucune zone ; chaque zone conserve son parent obligatoire
-- et la FK ON DELETE RESTRICT protège un site encore référencé.
-- session_user conserve le role de connexion individuel meme apres SET ROLE.
CREATE OR REPLACE FUNCTION milieux.stamp_modification() RETURNS trigger LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
 NEW.modifie_par := session_user;
 NEW.date_modification := clock_timestamp();
 RETURN NEW;
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['techniciens','communes','prestataires','types_prestations','statuts_prestations','ah','ah_stockage','ah_ouvrage','sites_terrestres','sites_zones','cours_eau','prestations'] LOOP
   EXECUTE format('CREATE TRIGGER tr_stamp_%I BEFORE INSERT OR UPDATE ON milieux.%I FOR EACH ROW EXECUTE FUNCTION milieux.stamp_modification()',t,t);
 END LOOP;
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['communes','ah_stockage','ah_ouvrage','sites_terrestres','sites_zones','cours_eau','prestations'] LOOP
   EXECUTE format('CREATE INDEX %I ON milieux.%I USING gist(geom)',t||'_geom_idx',t);
 END LOOP;
END $$;
CREATE INDEX prestations_ah_section_id_idx ON milieux.prestations(ah_section_id);
CREATE INDEX prestations_cours_eau_id_idx ON milieux.prestations(cours_eau_id);
CREATE INDEX prestations_digue_id_idx ON milieux.prestations(digue_id);
CREATE INDEX prestations_ah_stockage_id_idx ON milieux.prestations(ah_stockage_id);
CREATE INDEX prestations_ah_ouvrage_id_idx ON milieux.prestations(ah_ouvrage_id);
CREATE INDEX prestations_site_terrestre_id_idx ON milieux.prestations(site_terrestre_id);
CREATE INDEX prestations_site_zone_id_idx ON milieux.prestations(site_zone_id);
CREATE INDEX prestations_prestataire_idx ON milieux.prestations(prestataire_id);
CREATE INDEX prestations_type_idx ON milieux.prestations(type_prestation_id);
CREATE INDEX prestations_statut_idx ON milieux.prestations(statut_id);
CREATE INDEX prestations_technicien_idx ON milieux.prestations(technicien_id);
-- MESURES-07 : colonnes canoniques déclarées avant les vues qui les exposent.
-- Le calcul et les triggers sont définis plus bas, après leurs dépendances.
-- Géométrie cartographique : zone imposée, géométrie propre prioritaire pour
-- les AH, sinon géométrie du stockage/ouvrage. Aucun héritage n'est recopié
-- dans prestations.geom et la quantité déclarée reste indépendante.
CREATE VIEW milieux.prestations_carte
WITH (security_invoker = true) AS
SELECT
    p.id,
    p.intitule,
    p.type_prestation_id,
    p.prestataire_id,
    p.statut_id,
    p.date_debut,
    p.date_fin,
    p.quantite,
    p.unite,
    p.description,
    p.photo_1,
    p.photo_1_commentaire,
    p.photo_2,
    p.photo_2_commentaire,
    CASE
        WHEN p.site_zone_id IS NOT NULL THEN z.geom
        WHEN p.ah_stockage_id IS NOT NULL THEN COALESCE(p.geom, s.geom)
        WHEN p.ah_ouvrage_id IS NOT NULL THEN COALESCE(p.geom, o.geom)
        ELSE p.geom
    END::geometry(Geometry,3950) AS geom,
    p.date_modification,
    p.modifie_par,
    p.technicien_id,
    p.position,
    p.rive,
    p.cours_eau_id,
    p.digue_id,
    p.ah_stockage_id,
    p.ah_ouvrage_id,
    p.site_terrestre_id,
    p.site_zone_id,
    p.nombre_points,
    p.longueur_m,
    p.surface_m2,
    p.surface_ha,
    p.type_geometrie,
    p.type_geometrie_postgis,
    p.possede_geometrie,
    p.origine_mesures,
    p.ah_section_id
FROM milieux.prestations p
LEFT JOIN milieux.sites_zones z ON z.id=p.site_zone_id
LEFT JOIN milieux.ah_stockage s ON s.id=p.ah_stockage_id
LEFT JOIN milieux.ah_ouvrage o ON o.id=p.ah_ouvrage_id;
-- Vue tabulaire QGIS : une fiche par prestation, sans jointure N:N.
-- Les huit mesures sont celles enregistrées dans prestations, sans recalcul.
-- Les deux nouveaux champs sont ajoutés en fin pour préserver les positions.
CREATE VIEW milieux.prestations_fiches
WITH (security_invoker = true) AS
SELECT
    p.id,
    p.intitule,
    tp.libelle AS type_prestation,
    pr.nom AS prestataire,
    s.libelle AS statut,
    NULLIF(concat_ws(' ', NULLIF(btrim(t.prenom), ''), NULLIF(btrim(t.nom), '')), '') AS technicien,
    p.date_debut,
    p.date_fin,
    p.quantite,
    p.unite,
    p.description,
    p.photo_1,
    p.photo_1_commentaire,
    p.photo_2,
    p.photo_2_commentaire,
    p.type_prestation_id,
    p.prestataire_id,
    p.statut_id,
    p.technicien_id,
    p.date_modification,
    p.type_geometrie,
    p.type_geometrie_postgis,
    p.possede_geometrie,
    p.longueur_m,
    p.surface_m2,
    p.surface_ha,
    p.modifie_par,
    p.position,
    p.rive,
    p.cours_eau_id, p.digue_id, p.ah_stockage_id, p.ah_ouvrage_id, p.site_terrestre_id, p.site_zone_id,
    p.nombre_points,
    p.origine_mesures,
    p.ah_section_id
FROM milieux.prestations AS p
JOIN milieux.types_prestations AS tp ON tp.id = p.type_prestation_id
JOIN milieux.prestataires AS pr ON pr.id = p.prestataire_id
JOIN milieux.statuts_prestations AS s ON s.id = p.statut_id
JOIN milieux.techniciens AS t ON t.id = p.technicien_id;

-- Digues et repères du modèle courant.
CREATE TABLE milieux.digues (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nom text NOT NULL CHECK (btrim(nom) <> ''),
    identifiant_externe text,
    commentaire text,
    modifie_par text,
    date_modification timestamptz
);

-- Les fractions portent sur l'orientation actuelle de la rivière. La
-- géométrie copiée demeure inchangée si le référentiel est redessiné.
CREATE TABLE milieux.digues_reperes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    digue_id uuid NOT NULL REFERENCES milieux.digues(id) ON DELETE RESTRICT,
    riviere_id uuid NOT NULL REFERENCES milieux.cours_eau(id) ON DELETE RESTRICT,
    rive text NOT NULL CHECK (rive IN ('G', 'D')),
    debut_fraction double precision NOT NULL CHECK (debut_fraction BETWEEN 0 AND 1),
    fin_fraction double precision NOT NULL CHECK (fin_fraction BETWEEN 0 AND 1),
    geom_reference geometry(LineString, 3950) NOT NULL,
    geom_riviere_signature text NOT NULL,
    revision_validation integer NOT NULL DEFAULT 1 CHECK (revision_validation > 0),
    modifie_par text,
    date_modification timestamptz,
    CONSTRAINT digues_reperes_digue_unique UNIQUE (digue_id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT digues_reperes_ordre CHECK (debut_fraction < fin_fraction),
    CONSTRAINT digues_reperes_geom_valide CHECK (
        ST_IsValid(geom_reference) AND NOT ST_IsEmpty(geom_reference)
        AND ST_Length(geom_reference) > 0
    )
);
CREATE INDEX digues_reperes_digue_idx ON milieux.digues_reperes(digue_id);
CREATE INDEX digues_reperes_riviere_rive_idx
    ON milieux.digues_reperes(riviere_id, rive);
CREATE INDEX digues_reperes_geom_gix
    ON milieux.digues_reperes USING gist(geom_reference);

CREATE FUNCTION milieux.assert_digue_repere(digue_uuid uuid) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, milieux AS $$
BEGIN
    -- Le verrou du parent sérialise les changements de repère concurrents.
    PERFORM 1 FROM milieux.digues WHERE id = digue_uuid FOR UPDATE;
    IF FOUND AND NOT EXISTS (
        SELECT 1 FROM milieux.digues_reperes WHERE digue_id = digue_uuid
    ) THEN
        RAISE EXCEPTION 'Digue % sans repère', digue_uuid USING ERRCODE = '23514';
    END IF;
END $$;
CREATE FUNCTION milieux.digue_repere_complete() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, milieux AS $$
BEGIN
    IF TG_TABLE_NAME = 'digues' THEN
        IF TG_OP <> 'DELETE' THEN PERFORM milieux.assert_digue_repere(NEW.id); END IF;
    ELSE
        IF TG_OP <> 'INSERT' THEN PERFORM milieux.assert_digue_repere(OLD.digue_id); END IF;
        IF TG_OP <> 'DELETE' THEN PERFORM milieux.assert_digue_repere(NEW.digue_id); END IF;
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER digue_repere_parent AFTER INSERT OR UPDATE ON milieux.digues
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION milieux.digue_repere_complete();
CREATE CONSTRAINT TRIGGER digue_repere_child AFTER INSERT OR UPDATE OR DELETE ON milieux.digues_reperes
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION milieux.digue_repere_complete();

ALTER TABLE milieux.prestations ADD CONSTRAINT prestations_digue_id_fkey FOREIGN KEY (digue_id) REFERENCES milieux.digues(id) ON DELETE RESTRICT;
-- Fonction pure : aucune lecture de table, aucune qualification implicite.
CREATE FUNCTION milieux.cours_eau_reference_admissible(p_geom geometry, p_direction boolean, p_valide boolean)
RETURNS boolean LANGUAGE sql IMMUTABLE PARALLEL SAFE
SET search_path FROM CURRENT AS $admissible$
    SELECT CASE WHEN p_direction IS TRUE AND p_valide IS TRUE AND p_geom IS NOT NULL
                     AND ST_GeometryType(p_geom)='ST_MultiLineString'
                     AND ST_NumGeometries(p_geom)=1 THEN
        ST_SRID(p_geom)=3950 AND ST_NDims(p_geom)=2 AND NOT ST_IsEmpty(p_geom)
        AND ST_IsValid(p_geom) AND ST_IsSimple(ST_GeometryN(p_geom,1))
        AND NOT ST_IsClosed(ST_GeometryN(p_geom,1)) AND ST_Length(p_geom)>0
    ELSE false END
$admissible$;

CREATE FUNCTION milieux.digues_reperes_prepare() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
DECLARE
    r_geom geometry;
    r_line geometry;
    r_direction boolean;
    r_valide boolean;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF (NEW.id,NEW.digue_id) IS DISTINCT FROM (OLD.id,OLD.digue_id) THEN
            RAISE EXCEPTION 'UUID du repère et identité de la digue immuables' USING ERRCODE='23514';
        END IF;
        IF NEW.revision_validation IS NOT DISTINCT FROM OLD.revision_validation THEN
            IF (NEW.riviere_id,NEW.rive,NEW.debut_fraction,NEW.fin_fraction,NEW.geom_riviere_signature)
                IS DISTINCT FROM
               (OLD.riviere_id,OLD.rive,OLD.debut_fraction,OLD.fin_fraction,OLD.geom_riviere_signature)
               OR ST_AsEWKB(NEW.geom_reference) IS DISTINCT FROM ST_AsEWKB(OLD.geom_reference) THEN
                RAISE EXCEPTION 'Référence figée : augmenter revision_validation de 1 pour revalider'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END IF;
        IF NEW.revision_validation IS DISTINCT FROM OLD.revision_validation+1 THEN
            RAISE EXCEPTION 'Revalidation : la révision doit augmenter exactement de 1' USING ERRCODE='23514';
        END IF;
    ELSIF NEW.revision_validation IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION 'Première validation : révision 1 obligatoire' USING ERRCODE='23514';
    END IF;
    IF NEW.debut_fraction IS NULL OR NEW.fin_fraction IS NULL
       OR NOT (NEW.debut_fraction>=0 AND NEW.debut_fraction<NEW.fin_fraction AND NEW.fin_fraction<=1) THEN
        RAISE EXCEPTION 'Fractions attendues : 0 <= début < fin <= 1' USING ERRCODE='23514';
    END IF;

    -- FOR SHARE empêche une correction concurrente du tracé entre la lecture
    -- et l'enregistrement de l'instantané dans cette transaction.
    SELECT geom,direction,valide INTO r_geom,r_direction,r_valide FROM milieux.cours_eau
      WHERE id = NEW.riviere_id FOR SHARE;
    IF r_geom IS NULL THEN
        RAISE EXCEPTION 'Rivière de référence introuvable';
    END IF;
    IF NOT milieux.cours_eau_reference_admissible(r_geom,r_direction,r_valide) THEN
        RAISE EXCEPTION 'Cours d eau non admissible : direction et valide TRUE, ligne unique simple ouverte et positive requises'
            USING ERRCODE='23514';
    END IF;
    r_line := ST_GeometryN(r_geom,1);

    NEW.geom_reference := ST_LineSubstring(
        r_line, NEW.debut_fraction, NEW.fin_fraction);
    NEW.geom_riviere_signature := md5(encode(ST_AsEWKB(r_geom), 'hex'));
    RETURN NEW;
END $$;
CREATE TRIGGER digues_reperes_prepare_trg
BEFORE INSERT OR UPDATE ON milieux.digues_reperes
FOR EACH ROW EXECUTE FUNCTION milieux.digues_reperes_prepare();
CREATE TRIGGER tr_stamp_digues
BEFORE INSERT OR UPDATE ON milieux.digues
FOR EACH ROW EXECUTE FUNCTION milieux.stamp_modification();
CREATE TRIGGER tr_stamp_digues_reperes
BEFORE INSERT OR UPDATE ON milieux.digues_reperes
FOR EACH ROW EXECUTE FUNCTION milieux.stamp_modification();

-- Parcours explicites : droits du compte connecté, aucune élévation.
-- Le jeton parent évite aussi d'écraser une modification native de ses attributs.
CREATE FUNCTION milieux.digue_enregistrer(
    p_digue uuid, p_repere uuid, p_revision integer, p_parent_modification timestamptz,
    p_nom text, p_identifiant text, p_commentaire text,
    p_riviere uuid, p_rive text, p_debut double precision, p_fin double precision,
    p_signature text
) RETURNS uuid LANGUAGE plpgsql SECURITY INVOKER SET search_path FROM CURRENT AS $save$
DECLARE
    d milieux.digues%ROWTYPE;
    s milieux.digues_reperes%ROWTYPE;
    r milieux.cours_eau%ROWTYPE;
BEGIN
    SELECT * INTO r FROM milieux.cours_eau WHERE id=p_riviere FOR SHARE;
    IF NOT FOUND OR NOT milieux.cours_eau_reference_admissible(r.geom,r.direction,r.valide) THEN
        RAISE EXCEPTION 'Cours d eau non admissible : prévisualisez un support qualifié' USING ERRCODE='23514';
    END IF;
    IF p_signature IS NULL OR p_signature IS DISTINCT FROM md5(encode(ST_AsEWKB(r.geom),'hex')) THEN
        RAISE EXCEPTION 'Le cours d eau a changé : prévisualisez à nouveau avant de confirmer' USING ERRCODE='40001';
    END IF;
    IF p_digue IS NULL THEN
        IF p_repere IS NOT NULL OR p_revision IS DISTINCT FROM 0 THEN
            RAISE EXCEPTION 'Nouvelle digue : identité ou révision incorrecte' USING ERRCODE='23514';
        END IF;
        INSERT INTO milieux.digues(nom,identifiant_externe,commentaire)
        VALUES (p_nom,p_identifiant,p_commentaire) RETURNING * INTO d;
        INSERT INTO milieux.digues_reperes(digue_id,riviere_id,rive,debut_fraction,fin_fraction)
        VALUES (d.id,p_riviere,p_rive,p_debut,p_fin) RETURNING id INTO p_repere;
    ELSE
        SELECT * INTO d FROM milieux.digues WHERE id=p_digue FOR UPDATE;
        IF NOT FOUND OR d.date_modification IS DISTINCT FROM p_parent_modification THEN
            RAISE EXCEPTION 'La digue a changé : rechargez la fiche' USING ERRCODE='40001';
        END IF;
        SELECT * INTO s FROM milieux.digues_reperes WHERE digue_id=p_digue FOR UPDATE;
        IF NOT FOUND OR s.id IS DISTINCT FROM p_repere OR s.revision_validation IS DISTINCT FROM p_revision THEN
            RAISE EXCEPTION 'Le repère a changé : rechargez la fiche' USING ERRCODE='40001';
        END IF;
        UPDATE milieux.digues SET nom=p_nom,identifiant_externe=p_identifiant,commentaire=p_commentaire
        WHERE id=p_digue AND (nom,identifiant_externe,commentaire)
            IS DISTINCT FROM (p_nom,p_identifiant,p_commentaire);
        UPDATE milieux.digues_reperes SET riviere_id=p_riviere,rive=p_rive,
            debut_fraction=p_debut,fin_fraction=p_fin,revision_validation=revision_validation+1 WHERE id=p_repere;
    END IF;
    RETURN p_repere;
END $save$;

CREATE FUNCTION milieux.digue_supprimer(p_repere uuid,p_revision integer,p_parent_modification timestamptz)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path FROM CURRENT AS $delete$
DECLARE
    d milieux.digues%ROWTYPE;
    s milieux.digues_reperes%ROWTYPE;
    nombre bigint;
BEGIN
    -- Verrou du parent avant le repère, comme à l'enregistrement. Le verrou
    -- empêche aussi un rattachement FK concurrent pendant le contrôle.
    SELECT d0.* INTO d FROM milieux.digues d0 JOIN milieux.digues_reperes s0
        ON s0.digue_id=d0.id WHERE s0.id=p_repere FOR UPDATE OF d0;
    IF NOT FOUND OR d.date_modification IS DISTINCT FROM p_parent_modification THEN
        RAISE EXCEPTION 'La digue a changé : rechargez la fiche' USING ERRCODE='40001';
    END IF;
    SELECT * INTO s FROM milieux.digues_reperes WHERE id=p_repere AND digue_id=d.id FOR UPDATE;
    IF NOT FOUND OR s.revision_validation IS DISTINCT FROM p_revision THEN
        RAISE EXCEPTION 'Le repère a changé : rechargez la fiche' USING ERRCODE='40001';
    END IF;
    SELECT count(*) INTO nombre FROM milieux.prestations WHERE digue_id=d.id;
    IF nombre>0 THEN
        RAISE EXCEPTION 'Suppression impossible : % prestation(s) rattachée(s) à cette digue. Aucun objet supprimé.',nombre
            USING ERRCODE='23503';
    END IF;
    DELETE FROM milieux.digues_reperes WHERE id=p_repere;
    DELETE FROM milieux.digues WHERE id=d.id;
END $delete$;
REVOKE ALL ON FUNCTION milieux.digue_enregistrer(uuid,uuid,integer,timestamptz,text,text,text,uuid,text,double precision,double precision,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION milieux.digue_supprimer(uuid,integer,timestamptz) FROM PUBLIC;
COMMENT ON COLUMN milieux.digues_reperes.revision_validation IS
'Validation explicite : 1 à la création, puis +1, y compris à fractions identiques. UUID et parent immuables.';

-- Couche géographique de consultation ; la géométrie affichée est l'instantané.
CREATE VIEW milieux.digues_carte
WITH (security_invoker = true) AS
SELECT s.id, s.digue_id, d.nom AS digue_nom, s.riviere_id, r.nom AS riviere_nom,
       s.rive, s.debut_fraction, s.fin_fraction,
       s.geom_reference AS geom,
       CASE
           WHEN md5(encode(ST_AsEWKB(r.geom), 'hex'))
                IS DISTINCT FROM s.geom_riviere_signature
           THEN 'REFERENTIEL_MODIFIE'
           WHEN NOT milieux.cours_eau_reference_admissible(r.geom,r.direction,r.valide)
           THEN 'COURS_EAU_NON_QUALIFIE'
           ELSE 'CONFORME'
       END AS etat_referentiel
FROM milieux.digues_reperes AS s
JOIN milieux.digues AS d ON d.id = s.digue_id
JOIN milieux.cours_eau AS r ON r.id = s.riviere_id;
-- DIG-01 END

-- Référencement hydrographique AH : décisions explicites, instantanés figés.
CREATE TABLE milieux.ah_sections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ah_id uuid NOT NULL REFERENCES milieux.ah(id) ON DELETE RESTRICT,
    cours_eau_id uuid NOT NULL REFERENCES milieux.cours_eau(id) ON DELETE RESTRICT,
    debut_fraction double precision NOT NULL,
    fin_fraction double precision NOT NULL,
    geom_reference geometry(LineString,3950) NOT NULL,
    geom_cours_eau_signature text NOT NULL,
    revision_validation integer NOT NULL DEFAULT 1 CHECK (revision_validation > 0),
    valide_par text NOT NULL,
    date_validation timestamptz NOT NULL,
    commentaire text,
    modifie_par text,
    date_modification timestamptz,
    CONSTRAINT ah_sections_intervalle CHECK (
        debut_fraction >= 0 AND debut_fraction < fin_fraction AND fin_fraction <= 1),
    CONSTRAINT ah_sections_intervalle_unique UNIQUE (ah_id,cours_eau_id,debut_fraction,fin_fraction),
    CONSTRAINT ah_sections_geom_contract CHECK (
        NOT ST_IsEmpty(geom_reference) AND ST_IsValid(geom_reference)
        AND ST_NDims(geom_reference)=2 AND ST_Length(geom_reference)>0)
);
ALTER TABLE milieux.prestations ADD CONSTRAINT prestations_ah_section_id_fkey
FOREIGN KEY (ah_section_id) REFERENCES milieux.ah_sections(id) ON DELETE RESTRICT;

CREATE INDEX ah_sections_cours_eau_idx ON milieux.ah_sections(cours_eau_id);
CREATE INDEX ah_sections_geom_idx ON milieux.ah_sections USING gist(geom_reference);

CREATE FUNCTION milieux.ah_sections_prepare() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $prepare$
DECLARE
    r_geom geometry;
    r_direction boolean;
    r_valide boolean;
BEGIN
    IF TG_OP='UPDATE' THEN
        IF NEW.id IS DISTINCT FROM OLD.id THEN
            RAISE EXCEPTION 'UUID de section immuable' USING ERRCODE='23514';
        END IF;
        IF NEW.revision_validation IS NOT DISTINCT FROM OLD.revision_validation THEN
            IF (NEW.ah_id,NEW.cours_eau_id,NEW.debut_fraction,NEW.fin_fraction,
                NEW.geom_cours_eau_signature,NEW.valide_par,NEW.date_validation)
                 IS DISTINCT FROM
               (OLD.ah_id,OLD.cours_eau_id,OLD.debut_fraction,OLD.fin_fraction,
                OLD.geom_cours_eau_signature,OLD.valide_par,OLD.date_validation)
               OR ST_AsEWKB(NEW.geom_reference) IS DISTINCT FROM ST_AsEWKB(OLD.geom_reference) THEN
                RAISE EXCEPTION 'Référence figée : augmenter revision_validation de 1 pour revalider'
                    USING ERRCODE='23514';
            END IF;
            RETURN NEW;
        END IF;
        IF NEW.revision_validation IS DISTINCT FROM OLD.revision_validation+1 THEN
            RAISE EXCEPTION 'Revalidation : la révision doit augmenter exactement de 1' USING ERRCODE='23514';
        END IF;
    ELSIF NEW.revision_validation IS DISTINCT FROM 1 THEN
        RAISE EXCEPTION 'Première validation : révision 1 obligatoire' USING ERRCODE='23514';
    END IF;
    IF NEW.debut_fraction IS NULL OR NEW.fin_fraction IS NULL
       OR NOT (NEW.debut_fraction>=0 AND NEW.debut_fraction<NEW.fin_fraction AND NEW.fin_fraction<=1) THEN
        RAISE EXCEPTION 'Fractions attendues : 0 <= début < fin <= 1' USING ERRCODE='23514';
    END IF;
    IF NOT EXISTS(SELECT FROM milieux.ah WHERE id=NEW.ah_id) THEN
        RAISE EXCEPTION 'Parent AH introuvable' USING ERRCODE='23503';
    END IF;
    -- Verrou partagé jusqu'à la fin de transaction : empêche un tracé ou une
    -- qualification concurrents entre lecture et enregistrement de l'instantané.
    SELECT geom,direction,valide INTO r_geom,r_direction,r_valide FROM milieux.cours_eau
        WHERE id=NEW.cours_eau_id FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cours d eau de référence introuvable' USING ERRCODE='23503';
    END IF;
    IF NOT milieux.cours_eau_reference_admissible(r_geom,r_direction,r_valide) THEN
        RAISE EXCEPTION 'Cours d eau non admissible : direction et valide TRUE, ligne unique simple ouverte et positive requises'
            USING ERRCODE='23514';
    END IF;
    NEW.geom_reference := ST_LineSubstring(ST_GeometryN(r_geom,1),NEW.debut_fraction,NEW.fin_fraction);
    NEW.geom_cours_eau_signature := md5(encode(ST_AsEWKB(r_geom),'hex'));
    NEW.valide_par := session_user;
    NEW.date_validation := clock_timestamp();
    RETURN NEW;
END $prepare$;
CREATE TRIGGER ah_sections_prepare_trg BEFORE INSERT OR UPDATE ON milieux.ah_sections
FOR EACH ROW EXECUTE FUNCTION milieux.ah_sections_prepare();
CREATE TRIGGER tr_stamp_ah_sections BEFORE INSERT OR UPDATE ON milieux.ah_sections
FOR EACH ROW EXECUTE FUNCTION milieux.stamp_modification();

CREATE VIEW milieux.ah_sections_carte WITH (security_invoker=true) AS
SELECT s.id,s.ah_id,s.cours_eau_id,s.debut_fraction,s.fin_fraction,s.geom_reference,
       s.geom_cours_eau_signature,s.revision_validation,s.valide_par,s.date_validation,
       s.commentaire,s.modifie_par,s.date_modification, s.geom_reference AS geom,
       md5(encode(ST_AsEWKB(r.geom),'hex'))=s.geom_cours_eau_signature AS signature_conforme,
       milieux.cours_eau_reference_admissible(r.geom,r.direction,r.valide) AS cours_eau_qualifie,
       CASE WHEN md5(encode(ST_AsEWKB(r.geom),'hex')) IS DISTINCT FROM s.geom_cours_eau_signature
                THEN 'REFERENTIEL_MODIFIE'
            WHEN NOT milieux.cours_eau_reference_admissible(r.geom,r.direction,r.valide)
                THEN 'COURS_EAU_NON_QUALIFIE'
            ELSE 'CONFORME' END AS etat_reference
FROM milieux.ah_sections s JOIN milieux.cours_eau r ON r.id=s.cours_eau_id;

-- L'admissibilité est vérifiée à l'écriture, sous verrous partagés.
-- Une ancienne association obsolète reste consultable et éditable sans réaffectation.
CREATE FUNCTION milieux.prestations_section_admissible() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path FROM CURRENT AS $section_check$
DECLARE section_row milieux.ah_sections%ROWTYPE; reference_row milieux.cours_eau%ROWTYPE;
BEGIN
    IF NEW.ah_section_id IS NULL THEN RETURN NEW; END IF;
    IF TG_OP='UPDATE' THEN
        IF NEW.ah_section_id IS NOT DISTINCT FROM OLD.ah_section_id
           AND ST_AsEWKB(NEW.geom) IS NOT DISTINCT FROM ST_AsEWKB(OLD.geom) THEN RETURN NEW; END IF;
    END IF;
    SELECT * INTO section_row FROM milieux.ah_sections WHERE id=NEW.ah_section_id FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Section AH introuvable' USING ERRCODE='23503';
    END IF;
    SELECT * INTO reference_row FROM milieux.cours_eau WHERE id=section_row.cours_eau_id FOR SHARE;
    IF NOT milieux.cours_eau_reference_admissible(reference_row.geom,reference_row.direction,reference_row.valide)
       OR md5(encode(ST_AsEWKB(reference_row.geom),'hex')) IS DISTINCT FROM section_row.geom_cours_eau_signature
       OR NOT ST_Equals(section_row.geom_reference,ST_LineSubstring(ST_GeometryN(reference_row.geom,1),
                                              section_row.debut_fraction,section_row.fin_fraction)) THEN
        RAISE EXCEPTION 'Section AH non conforme ou cours d eau non qualifié : revalidation nécessaire'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $section_check$;
REVOKE ALL ON FUNCTION milieux.prestations_section_admissible() FROM PUBLIC;
CREATE TRIGGER prestations_section_admissible_trg BEFORE INSERT OR UPDATE ON milieux.prestations
FOR EACH ROW EXECUTE FUNCTION milieux.prestations_section_admissible();

-- Propositions en lecture seule depuis l'unique stockage facultatif du parent.
-- Aucun INSERT ni validation métier : accepter exige une écriture explicite.
CREATE FUNCTION milieux.ah_sections_candidates(p_ah_id uuid)
RETURNS TABLE (cours_eau_id uuid, debut_fraction double precision, fin_fraction double precision,
               geom_reference geometry, geom_cours_eau_signature text)
LANGUAGE sql STABLE SET search_path FROM CURRENT AS $candidates$
    WITH supports AS MATERIALIZED (
        SELECT r.id,r.geom,ST_GeometryN(r.geom,1) AS ligne,s.geom AS stockage_geom
        FROM milieux.ah_stockage s JOIN milieux.cours_eau r ON ST_Intersects(s.geom,r.geom)
        WHERE s.ah_id=p_ah_id AND milieux.cours_eau_reference_admissible(r.geom,r.direction,r.valide)
    ), parties AS (
        SELECT r.id,r.geom,r.ligne,p.geom AS partie
        FROM supports r CROSS JOIN LATERAL ST_Dump(ST_LineMerge(ST_UnaryUnion(
            ST_CollectionExtract(ST_Intersection(r.stockage_geom,r.ligne),2)))) p
        WHERE NOT ST_IsEmpty(p.geom) AND ST_Length(p.geom)>0
    ), fractions AS (
        SELECT id,geom,ligne,partie,
               LEAST(ST_LineLocatePoint(ligne,ST_StartPoint(partie)),
                     ST_LineLocatePoint(ligne,ST_EndPoint(partie))) AS debut,
               GREATEST(ST_LineLocatePoint(ligne,ST_StartPoint(partie)),
                        ST_LineLocatePoint(ligne,ST_EndPoint(partie))) AS fin
        FROM parties
    )
    SELECT id,debut,fin,ST_LineSubstring(ligne,debut,fin),md5(encode(ST_AsEWKB(geom),'hex'))
    FROM fractions WHERE debut<fin AND ST_Equals(ST_LineSubstring(ligne,debut,fin),partie)
    ORDER BY id,debut,fin
$candidates$;
COMMENT ON TABLE milieux.ah_sections IS
'Sections du parent AH définies par fractions manuelles sur un cours d eau qualifié. Géométrie calculée et figée, revalidation explicite ; aucune dépendance au stockage.';
COMMENT ON COLUMN milieux.ah_sections.revision_validation IS
'1 à la création ; augmenter exactement de 1 pour accepter une nouvelle référence, même avec les mêmes fractions. Aucun recalcul sur modification du cours d eau.';
COMMENT ON FUNCTION milieux.ah_sections_candidates(uuid) IS
'Propositions spatiales en lecture seule sur cours d eau qualifiés ; aucune décision métier enregistrée.';
-- Fin du référencement hydrographique AH.

-- Liaisons de consultation consolidées pour les formulaires QGIS des parents.
-- L'identifiant technique stable permet de charger chaque vue sans géométrie
-- avec une clé simple ; les couples métier restent les deux UUID exposés.
CREATE VIEW milieux.prestations__ah
WITH (security_invoker = true) AS
SELECT md5('prestations__ah:' || links.prestation_id::text || ':' || links.ah_id::text)::uuid AS id,
       links.prestation_id, links.ah_id
FROM (
    SELECT l.id AS prestation_id, s.ah_id
    FROM milieux.prestations AS l
    JOIN milieux.ah_stockage AS s ON s.id = l.ah_stockage_id
    UNION
    SELECT l.id AS prestation_id, o.ah_id
    FROM milieux.prestations AS l
    JOIN milieux.ah_ouvrage AS o ON o.id = l.ah_ouvrage_id
    UNION
    SELECT l.id AS prestation_id, s.ah_id
    FROM milieux.prestations AS l
    JOIN milieux.ah_sections AS s ON s.id = l.ah_section_id
) AS links;

CREATE VIEW milieux.prestations__sites_terrestres
WITH (security_invoker = true) AS
SELECT md5('prestations__sites_terrestres:' || links.prestation_id::text || ':' || links.site_terrestre_id::text)::uuid AS id,
       links.prestation_id, links.site_terrestre_id
FROM (
    SELECT id AS prestation_id, site_terrestre_id FROM milieux.prestations WHERE site_terrestre_id IS NOT NULL
    UNION
    SELECT p.id AS prestation_id, z.site_terrestre_id
    FROM milieux.prestations AS p
    JOIN milieux.sites_zones AS z ON z.id = p.site_zone_id
) AS links;

-- Mesures enregistrées : géométrie propre prioritaire, sinon patrimoine.
-- La quantité déclarée reste indépendante. Actualiser la fiche après sauvegarde.
SELECT pg_catalog.set_config('search_path',pg_catalog.format('pg_catalog,%I,milieux,pg_temp',n.nspname),true)
FROM pg_catalog.pg_extension e JOIN pg_catalog.pg_namespace n ON n.oid=e.extnamespace
WHERE e.extname='postgis';
CREATE FUNCTION milieux.mesures07_resoudre(
    propre geometry,cours uuid,digue uuid,stockage uuid,ouvrage uuid,site uuid,zone uuid,
    OUT nombre_points integer,OUT longueur_m double precision,
    OUT surface_m2 double precision,OUT surface_ha double precision,
    OUT type_geometrie text,OUT type_geometrie_postgis text,
    OUT possede_geometrie boolean,OUT origine_mesures text
) RETURNS record LANGUAGE plpgsql VOLATILE SECURITY INVOKER
SET search_path FROM CURRENT AS $resolve$
DECLARE g geometry;
BEGIN
    IF propre IS NOT NULL THEN g:=propre;
    ELSIF cours IS NOT NULL THEN SELECT geom INTO g FROM milieux.cours_eau WHERE id=cours;
    ELSIF digue IS NOT NULL THEN SELECT geom_reference INTO g FROM milieux.digues_reperes WHERE digue_id=digue;
    ELSIF stockage IS NOT NULL THEN SELECT geom INTO g FROM milieux.ah_stockage WHERE id=stockage;
    ELSIF ouvrage IS NOT NULL THEN SELECT geom INTO g FROM milieux.ah_ouvrage WHERE id=ouvrage;
    ELSIF site IS NOT NULL THEN SELECT geom INTO g FROM milieux.sites_terrestres WHERE id=site;
    ELSIF zone IS NOT NULL THEN SELECT geom INTO g FROM milieux.sites_zones WHERE id=zone;
    END IF;
    possede_geometrie:=g IS NOT NULL AND NOT ST_IsEmpty(g);
    origine_mesures:=CASE WHEN NOT possede_geometrie THEN 'Aucune géométrie'
        WHEN propre IS NOT NULL THEN 'Prestation' ELSE 'Patrimoine de rattachement' END;
    IF NOT possede_geometrie THEN RETURN; END IF;
    type_geometrie_postgis:=ST_GeometryType(g);
    CASE type_geometrie_postgis
        WHEN 'ST_Point','ST_MultiPoint' THEN type_geometrie:='Point';nombre_points:=ST_NPoints(g);
        WHEN 'ST_LineString','ST_MultiLineString' THEN type_geometrie:='Ligne';longueur_m:=ST_Length(g);
        WHEN 'ST_Polygon','ST_MultiPolygon' THEN type_geometrie:='Polygone';surface_m2:=ST_Area(g);surface_ha:=surface_m2/10000.0;
        ELSE NULL;
    END CASE;
END $resolve$;
REVOKE ALL ON FUNCTION milieux.mesures07_resoudre(geometry,uuid,uuid,uuid,uuid,uuid,uuid) FROM PUBLIC;

CREATE FUNCTION milieux.mesures07_preparer() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path FROM CURRENT AS $prepare$
DECLARE m record;
BEGIN
    IF TG_OP='UPDATE' THEN
        -- Ce trigger est appelé après tr_stamp_prestations (ordre alphabétique).
        -- Les mises à jour de seules mesures ne modifient pas la traçabilité métier.
        IF (to_jsonb(NEW)-ARRAY['nombre_points','longueur_m','surface_m2','surface_ha','type_geometrie','type_geometrie_postgis','possede_geometrie','origine_mesures','modifie_par','date_modification']) IS NOT DISTINCT FROM (to_jsonb(OLD)-ARRAY['nombre_points','longueur_m','surface_m2','surface_ha','type_geometrie','type_geometrie_postgis','possede_geometrie','origine_mesures','modifie_par','date_modification']) AND NOT (ROW(NEW.nombre_points,NEW.longueur_m,NEW.surface_m2,NEW.type_geometrie,NEW.type_geometrie_postgis,NEW.possede_geometrie,NEW.origine_mesures) IS NOT DISTINCT FROM ROW(OLD.nombre_points,OLD.longueur_m,OLD.surface_m2,OLD.type_geometrie,OLD.type_geometrie_postgis,OLD.possede_geometrie,OLD.origine_mesures)) THEN
            NEW.modifie_par:=OLD.modifie_par;
            NEW.date_modification:=OLD.date_modification;
        END IF;
        IF ST_AsEWKB(NEW.geom) IS NOT DISTINCT FROM ST_AsEWKB(OLD.geom)
           AND ROW(NEW.cours_eau_id,NEW.digue_id,NEW.ah_stockage_id,NEW.ah_ouvrage_id,NEW.site_terrestre_id,NEW.site_zone_id,NEW.ah_section_id) IS NOT DISTINCT FROM ROW(OLD.cours_eau_id,OLD.digue_id,OLD.ah_stockage_id,OLD.ah_ouvrage_id,OLD.site_terrestre_id,OLD.site_zone_id,OLD.ah_section_id) AND ROW(NEW.nombre_points,NEW.longueur_m,NEW.surface_m2,NEW.type_geometrie,NEW.type_geometrie_postgis,NEW.possede_geometrie,NEW.origine_mesures) IS NOT DISTINCT FROM ROW(OLD.nombre_points,OLD.longueur_m,OLD.surface_m2,OLD.type_geometrie,OLD.type_geometrie_postgis,OLD.possede_geometrie,OLD.origine_mesures) THEN RETURN NEW; END IF;
    END IF;
    -- FOR SHARE requiert UPDATE sur le parent : le trigger seul, non appelable
    -- directement, porte cette capacité. Aucun GRANT d'édition de parent au rôle Prestations.
    IF NEW.geom IS NULL THEN
        IF NEW.ah_stockage_id IS NOT NULL THEN PERFORM 1 FROM milieux.ah_stockage WHERE id=NEW.ah_stockage_id FOR SHARE;
        ELSIF NEW.ah_ouvrage_id IS NOT NULL THEN PERFORM 1 FROM milieux.ah_ouvrage WHERE id=NEW.ah_ouvrage_id FOR SHARE;
        ELSIF NEW.site_zone_id IS NOT NULL THEN PERFORM 1 FROM milieux.sites_zones WHERE id=NEW.site_zone_id FOR SHARE;
        END IF;
    END IF;
    SELECT * INTO m FROM milieux.mesures07_resoudre(NEW.geom,NEW.cours_eau_id,NEW.digue_id,
        NEW.ah_stockage_id,NEW.ah_ouvrage_id,NEW.site_terrestre_id,NEW.site_zone_id);
    NEW.nombre_points:=m.nombre_points;
    NEW.longueur_m:=m.longueur_m;
    NEW.surface_m2:=m.surface_m2;
    NEW.type_geometrie:=m.type_geometrie;
    NEW.type_geometrie_postgis:=m.type_geometrie_postgis;
    NEW.possede_geometrie:=m.possede_geometrie;
    NEW.origine_mesures:=m.origine_mesures;
    RETURN NEW;
END $prepare$;
REVOKE ALL ON FUNCTION milieux.mesures07_preparer() FROM PUBLIC;
CREATE TRIGGER zz_mesures07_preparer BEFORE INSERT OR UPDATE ON milieux.prestations
FOR EACH ROW EXECUTE FUNCTION milieux.mesures07_preparer();



-- Seules ces trois familles autorisent une prestation sans géométrie propre.
CREATE FUNCTION milieux.mesures07_parent() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path FROM CURRENT AS $parent$
BEGIN
    IF TG_TABLE_NAME='ah_stockage' THEN
        UPDATE milieux.prestations SET origine_mesures=NULL WHERE geom IS NULL AND ah_stockage_id=NEW.id;
    ELSIF TG_TABLE_NAME='ah_ouvrage' THEN
        UPDATE milieux.prestations SET origine_mesures=NULL WHERE geom IS NULL AND ah_ouvrage_id=NEW.id;
    ELSIF TG_TABLE_NAME='sites_zones' THEN
        UPDATE milieux.prestations SET origine_mesures=NULL WHERE geom IS NULL AND site_zone_id=NEW.id;
    END IF;
    RETURN NULL;
END $parent$;
REVOKE ALL ON FUNCTION milieux.mesures07_parent() FROM PUBLIC;
CREATE TRIGGER mesures07_dependants AFTER UPDATE OF geom ON milieux.ah_stockage FOR EACH ROW
WHEN(ST_AsEWKB(OLD.geom) IS DISTINCT FROM ST_AsEWKB(NEW.geom)) EXECUTE FUNCTION milieux.mesures07_parent();
CREATE TRIGGER mesures07_dependants AFTER UPDATE OF geom ON milieux.ah_ouvrage FOR EACH ROW
WHEN(ST_AsEWKB(OLD.geom) IS DISTINCT FROM ST_AsEWKB(NEW.geom)) EXECUTE FUNCTION milieux.mesures07_parent();
CREATE TRIGGER mesures07_dependants AFTER UPDATE OF geom ON milieux.sites_zones FOR EACH ROW
WHEN(ST_AsEWKB(OLD.geom) IS DISTINCT FROM ST_AsEWKB(NEW.geom)) EXECUTE FUNCTION milieux.mesures07_parent();

COMMIT;
