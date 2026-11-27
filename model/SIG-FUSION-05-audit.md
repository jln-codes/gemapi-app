# SIG-FUSION-05 — Audit des supports et des FK externes

Projection documentaire v0.5. Base : `1246f650ace55cc171ea0941ce07f915932b013a`. Sources digues-app **development** : `e6c5b8e56887dfc7534d76d659dc18ed0e6edbae`. Aucun accès PostgreSQL, aucune modification de données ou de code opérationnel.

## Résultat

49 tables : 23 métier, 4 associatives, 22 référentiels ; 110 relations internes. Les **51 FK externes v0.4** sont toutes inventoriées ci-dessous. **3 restent externes** ; le modèle n’est pas entièrement autonome. Les deux références de personnes sont remplacées par des attributions documentaires textuelles, sans nouveau registre de personnes.

## Méthode et preuves

- `model/schema_development_v0.4.mmd` et son PDF ; `model/schema.sql` en lecture seule.
- digues-app : `docs/architecture/schema-global.mmd`, `digues_app/target/schema_current.sql`, `digues_app/migration/{canonical_troncons,canonical_validation,structures_digue,troncon_franc_bord,troncon_positions,validation,fidelity_contracts}.py`.
- Usages applicatifs : `webapp/backend/digues_webapp/{data_views,models,queries,resource_mutations,troncons,reperage}.py`.
- Jeux CABBALR et démo : lecture SQLite `mode=ro`, géométries décodées avec Shapely ; générateurs et SQL lus, jamais exécutés.

## Inventaire exhaustif des 51 FK externes v0.4

### 1. `public.ouvrages_hydrauliques__objets_lies.ouvrage_voirie_id`

- Ancienne cible : `public.ouvrages_voirie(id)`.
- Usage métier : Lien technique vers famille non projetée.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Adapter ck_cible_ouvrage_hydraulique_liee aux six cibles restantes. Diagnostiquer les lignes devenues sans cible ; aucun objet fictif, aucun N:N de remplacement.

### 2. `public.ouvrages_hydrauliques__objets_lies.reseau_hydraulique_id`

- Ancienne cible : `public.reseaux_hydrauliques(id)`.
- Usage métier : Lien technique vers famille non projetée.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Adapter ck_cible_ouvrage_hydraulique_liee aux six cibles restantes. Diagnostiquer les lignes devenues sans cible ; aucun objet fictif, aucun N:N de remplacement.

### 3. `public.ouvrages_hydrauliques__objets_lies.ouvrage_telecom_energie_id`

- Ancienne cible : `public.ouvrages_telecom_energie(id)`.
- Usage métier : Lien technique vers famille non projetée.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Adapter ck_cible_ouvrage_hydraulique_liee aux six cibles restantes. Diagnostiquer les lignes devenues sans cible ; aucun objet fictif, aucun N:N de remplacement.

### 4. `public.ouvrages_hydrauliques__objets_lies.reseau_technique_id`

- Ancienne cible : `public.reseaux_techniques(id)`.
- Usage métier : Lien technique vers famille non projetée.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Adapter ck_cible_ouvrage_hydraulique_liee aux six cibles restantes. Diagnostiquer les lignes devenues sans cible ; aucun objet fictif, aucun N:N de remplacement.

### 5. `public.ouvrages_hydrauliques__objets_lies.digue_id`

- Ancienne cible : `public.digues(id)`.
- Usage métier : Objet technique lié de famille digue.
- Cible interne possible : milieux.digues(id).
- Suppression possible : Oui.
- Décision : **Internalisée**.
- Conséquence et conditions : Remplacer la FK historique, garder la cible exclusive. UUID identique seulement si identité démontrée ; sinon table de correspondance d’import approuvée, pas de nom/proximité.

### 6. `public.amenagements_hydrauliques__structures.amenagement_hydraulique_id`

- Ancienne cible : `public.amenagements_hydrauliques(id)`.
- Usage métier : Parent de structure AH individualisée.
- Cible interne possible : milieux.ah_ouvrage.
- Suppression possible : Non avant correspondance validée.
- Décision : **À arbitrer ; FK externe conservée**.
- Conséquence et conditions : Proposition de FK interne non appliquée. Préserver UUID de structure, couches, géométrie et ck_structure_parent_zone_unique ; diagnostic des correspondances absentes ou multiples.

### 7. `public.observations.amenagement_hydraulique_id`

- Ancienne cible : `public.amenagements_hydrauliques(id)`.
- Usage métier : Cible historique du constat.
- Cible interne possible : milieux.ah_ouvrage.
- Suppression possible : Oui.
- Décision : **Transformée en ah_ouvrage_id**.
- Conséquence et conditions : Correspondance métier et UUID explicite obligatoire. Un ancien AH global ne désigne pas automatiquement un ouvrage constitutif ; refus si ambigu. Cible unique contrôlée après conversion.

### 8. `public.observations.element_morphologique_id`

- Ancienne cible : `public.elements_morphologiques_lit(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 9. `public.observations.objet_mesure_hydraulique_id`

- Ancienne cible : `public.objets_mesures_hydrauliques(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 10. `public.observations.observateur_id`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Attribution métier du constat ou du cliché.
- Cible interne possible : Mention documentaire facultative, sans FK.
- Suppression possible : Oui.
- Décision : **Transformée en texte observateur**.
- Conséquence et conditions : Pas de référentiel personnes importé. Résoudre le libellé explicite du contact ; sans résolution, conserver le diagnostic avec UUID source et bloquer la perte silencieuse. Ne pas déduire un technicien ; homonymes non fusionnés.

### 11. `public.observations.organe_protection_collective_id`

- Ancienne cible : `public.organes_protection_collective(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 12. `public.observations.ouvrage_telecom_energie_id`

- Ancienne cible : `public.ouvrages_telecom_energie(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 13. `public.observations.ouvrage_voirie_id`

- Ancienne cible : `public.ouvrages_voirie(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 14. `public.photos.photographe_id`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Attribution métier du constat ou du cliché.
- Cible interne possible : Mention documentaire facultative, sans FK.
- Suppression possible : Oui.
- Décision : **Transformée en texte photographe**.
- Conséquence et conditions : Pas de référentiel personnes importé. Résoudre le libellé explicite du contact ; sans résolution, conserver le diagnostic avec UUID source et bloquer la perte silencieuse. Ne pas déduire un technicien ; homonymes non fusionnés.

### 15. `public.observations.prestation_id`

- Ancienne cible : `public.prestations(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 16. `public.observations.profil_travers_id`

- Ancienne cible : `public.profils_travers(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 17. `public.observations.reseau_hydraulique_id`

- Ancienne cible : `public.reseaux_hydrauliques(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 18. `public.observations.reseau_technique_id`

- Ancienne cible : `public.reseaux_techniques(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 19. `public.observations.segment_hydrographique_id`

- Ancienne cible : `public.segments_hydrographiques(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 20. `public.observations.structure_protection_id`

- Ancienne cible : `public.structures_protection(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 21. `public.troncons.systeme_reperage_defaut_id`

- Ancienne cible : `public.systemes_reperage(id)`.
- Usage métier : Repérage SIRS abandonné.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer FK et dépendances vers systèmes/bornes ; exploiter XY ou axe qualifié avant conversion. Positions relatives non résolues signalées ; aucune géométrie inventée.

### 22. `public.observations.composant_berge_id`

- Ancienne cible : `public.composants_berges(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 23. `public.photos.systeme_reperage_id`

- Ancienne cible : `public.systemes_reperage(id)`.
- Usage métier : Repérage SIRS abandonné.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer FK et dépendances vers systèmes/bornes ; exploiter XY ou axe qualifié avant conversion. Positions relatives non résolues signalées ; aucune géométrie inventée.

### 24. `public.photos.borne_debut_id`

- Ancienne cible : `public.bornes_reperage(id)`.
- Usage métier : Repérage SIRS abandonné.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer FK et dépendances vers systèmes/bornes ; exploiter XY ou axe qualifié avant conversion. Positions relatives non résolues signalées ; aucune géométrie inventée.

### 25. `public.photos.borne_fin_id`

- Ancienne cible : `public.bornes_reperage(id)`.
- Usage métier : Repérage SIRS abandonné.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer FK et dépendances vers systèmes/bornes ; exploiter XY ou axe qualifié avant conversion. Positions relatives non résolues signalées ; aucune géométrie inventée.

### 26. `public.amenagements_hydrauliques__structures.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 27. `public.amenagements_hydrauliques__structures.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 28. `public.desordres.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 29. `public.desordres.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 30. `public.equipements_mesure.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 31. `public.equipements_mesure.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 32. `public.observations.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 33. `public.observations.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 34. `public.ouvrages_hydrauliques.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 35. `public.ouvrages_hydrauliques.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 36. `public.ouvrages_particuliers.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 37. `public.ouvrages_particuliers.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 38. `public.photos.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 39. `public.photos.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 40. `public.troncons.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 41. `public.troncons.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 42. `public.observations.trace_position_troncon_id`

- Ancienne cible : `public.traces_positions_troncons(id)`.
- Usage métier : Ancienne cible hors des 13 familles autorisées.
- Cible interne possible : Aucune.
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Retirer le terme de ck_cible_unique. Une observation dont c’était la seule cible est non convertible sans décision métier, avec ses photos ; ne pas l’insérer sans cible ni la rattacher arbitrairement à un tronçon.

### 43. `public.amenagements_hydrauliques__structures.zone_stockage_id`

- Ancienne cible : `public.zones_stockage(id)`.
- Usage métier : Parent de structure AH individualisée.
- Cible interne possible : milieux.ah_stockage.
- Suppression possible : Non avant correspondance validée.
- Décision : **À arbitrer ; FK externe conservée**.
- Conséquence et conditions : Proposition de FK interne non appliquée. Préserver UUID de structure, couches, géométrie et ck_structure_parent_zone_unique ; diagnostic des correspondances absentes ou multiples.

### 44. `public.observations.zone_stockage_id`

- Ancienne cible : `public.zones_stockage(id)`.
- Usage métier : Cible historique du constat.
- Cible interne possible : milieux.ah_stockage.
- Suppression possible : Oui.
- Décision : **Transformée en ah_stockage_id**.
- Conséquence et conditions : Correspondance métier et UUID explicite obligatoire. Un ancien AH global ne désigne pas automatiquement un ouvrage constitutif ; refus si ambigu. Cible unique contrôlée après conversion.

### 45. `public.troncons.segment_hydrographique_support_id`

- Ancienne cible : `public.segments_hydrographiques(id)`.
- Usage métier : Support physique SIRS.
- Cible interne possible : Aucune équivalence directe à milieux.cours_eau démontrée.
- Suppression possible : Non avant choix A/B.
- Décision : **À arbitrer ; FK externe conservée**.
- Conséquence et conditions : Conserver ck_troncons_support et ck_troncons_crete_fields. Tronçon de lit SIRS et cours d’eau interne ne sont pas identiques ; examiner unités, rôle et correspondances géométriques sans appariement automatique.

### 46. `public.mobilier.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 47. `public.mobilier.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 48. `public.cheminements.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 49. `public.cheminements.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 50. `public.vegetation.created_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

### 51. `public.vegetation.edited_by`

- Ancienne cible : `public.contacts(id)`.
- Usage métier : Auteur informatique SIRS.
- Cible interne possible : modifie_par / date_modification (nouvelle écriture seulement).
- Suppression possible : Oui.
- Décision : **Supprimée**.
- Conséquence et conditions : Identité informatique historique hors cible, retrait explicitement décidé ; jamais convertir le contact en compte PostgreSQL. Diagnostiquer la métadonnée source à l’import.

## Supports de tronçons : état actuel et protections

| Élément | Usage observé et conséquences |
|---|---|
| `troncon_support_id`, `troncon_support_qualifie` | FK composite différée vers `(id,est_support_classique)`. Le discriminant généré vaut `true`. La démo digues-app crée une crête `crete-carbonade` sur `carbonade-t02` ; `structures_digue.py` et `troncon_franc_bord.py` alimentent ce support. |
| `berge_support_id`, `berge_support_id_type` | FK composite différée vers `(id,type_troncon_id)` dans la projection ; discriminant `BERGE`. La source utilise `type_physique_id`, renommé dès v0.2. Supprimer ce rôle sans conversion ferait perdre la qualification du support. |
| `segment_hydrographique_support_id` | FK externe vers un tronçon de lit SIRS. `milieux.cours_eau` représente le réseau de référence et n'est pas une équivalence démontrée de ce support physique. Conservée en attente d'arbitrage, sans nouvelle table. |
| `est_structure` | Généré pour CRETE, TALUS, TALUS_RISBERME, RISBERME, FRANC_BORD. La FK d'observation est retirée mais `localisations_objets` externe et ses localisations de structure utilisent encore `(id,est_structure)`. |
| `est_support_classique` | Généré pour INDETERMINE avec digue et designation renseignées en v0.4. Référencé par les supports internes et par `traces_positions_troncons` externe. Ne pas supprimer sa clé unique sous prétexte du changement des observations. |
| `position_pied_autorisee` | BERGE ou TALUS ; clé unique utilisée par `traces_positions_troncons.fk_trace_position_pied`, hors projection. |
| `position_sommet_autorisee` | BERGE, TALUS ou RISBERME ; même rôle pour `fk_trace_position_sommet`. |
| `ck_troncons_support` | Au plus un des trois supports pour les cinq types structurels, aucun pour les autres. Les structures ne sont donc déjà **pas obligées** d'avoir un support ; le choix A ne consiste pas simplement à rendre une FK nullable. |
| `ck_troncons_crete_fields` | Pour CRETE, impose NULL sur segment/berge supports, côté, position et fonctions/natures/matériaux haut/bas. Le support classique reste possible. La v0.5 conserve exactement la sélection v0.4. |
| Clés et index | Conserver `uq_troncons_type`, `uq_troncons_role_structure`, `uq_troncons_role_support`, `uq_troncons_position_pied`, `uq_troncons_position_sommet`, `idx_troncons_support` et les FK de rôle différées. Les discriminants générés ne sont pas des champs éditables. |

Dépendances entrantes observées dans le DDL : `localisations_objets`, `traces_positions_troncons`, `composants_berges`, `structures_protection`, `segments_hydrographiques__ouvrages`, `ouvrages_hydrauliques__objets_lies`, ainsi que les familles et associations de localisation. Ces tables externes ne sont pas importées. Les deux FK composites des **observations** peuvent disparaître indépendamment : leur cible unique est maintenant le tronçon de n'importe quel type. Les FK composites des supports et de l'objet lié de type berge restent actives.

### Comparaison A/B

| Critère | A — Objets autonomes, sans hiérarchie physique | B — Parent-enfant facultatif simplifié |
|---|---|---|
| Identité, géométrie, digue | Conservées pour chaque objet ; aucun regroupement d'UUID | Identiques à A ; relation optionnelle en plus |
| Crête et talus | Localisation propre suffisante mais relation au corps support perdue | Une relation explicite permet de conserver le contexte de crête/talus sans imposer un support |
| Berge et risberme | Plus de lien physique, ni de qualification héritée du parent | Matrice des types autorisés à redéfinir ; ne pas autoriser implicitement une crête sur une berge |
| Observations | FK simple troncon_id suffit déjà en v0.5 | Même FK simple ; aucune observation automatiquement dupliquée sur les parents |
| Localisations et pied/sommet | Conversion des repères vers XY/axe ; perte éventuelle des rôles à accepter | Rôles de pied/sommet à distinguer de la hiérarchie, jamais déduits automatiquement d'un parent |
| Contraintes | Retrait des supports et de clés possible seulement après audit de toutes les références entrantes | Nouveau contrat : au plus un parent, anti-cycle, pas d'auto-parent, cohérence de digue et matrice de types à arbitrer ; conserver les garanties de concurrence |
| Segment hydrographique | Relation de support abandonnée avec perte explicite de ce contexte | Un cours d'eau n'est pas un parent tronçon ; décider séparément de son éventuel rôle, sans table fictive |
| Coût | Schéma plus simple, coût de reprise et perte de contexte plus élevés si les supports sont utilisés | Reprise moins destructrice, coût de définition/test des cycles, types et rattachements plus élevé |

**Recommandation : instruire B en priorité**, car la démo source et les chemins de migration montrent des relations explicites de crête et de pied ; conserver ces relations facultatives évite une perte de contexte non encore acceptée. Ce n'est **pas un choix appliqué**. A reste pertinent si un inventaire métier confirme que géométrie propre et digue suffisent et si les pertes de rôle sont acceptées. Les données CABBALR/démo gemapi-app consultées ne comportent pas de table `public.troncons` avec ces supports : elles ne permettent pas de mesurer leur fréquence réelle. Les scénarios de digues-app sont fictifs et ne prouvent pas un usage en production.

## Données disponibles et reclassement

- `cabbalr/gpkg/sites_zones.gpkg`, couche `sites_zones` : **41 UUID distincts**, 41 MultiLineString 2D EPSG:3950, valides et non vides ; tous portent le même site parent. Même nombre et familles géométriques dans `cabbalr/data/sites_zones.gpkg`.
- Types : 24 Sentier pédestre, 2 Sentier randonnée, 12 Sentier secondaire, 1 Sentier VTT, 1 Escalier, **1 Grillage**. Le reclassement en cheminements est décidé ; la classification précise est une condition d'import. Escalier peut reprendre ESC ; les 39 sentiers peuvent être proposés en AUT sans perdre leur libellé d'origine. Le cas Grillage doit être explicitement qualifié : ne pas le convertir silencieusement en mobilier ni affirmer qu'il s'agit d'un chemin.
- `cabbalr/data/sites_zones_polygones.gpkg` est un autre jeu : **6 MultiPolygon** valides et non vides, sans UUID patrimonial ni parent explicite. Ce n'est pas une variante géométrique prouvée des 41 lignes. Ne pas les fusionner ni en dériver des axes sans décision et correspondance d'identités.
- La couche fictive `demo/gpkg/sites_terrestres.gpkg:sites_zones` comprend **25 objets** : 17 MultiPolygon, 4 MultiPoint et 4 MultiLineString. Types : zones humides, espaces boisés, prairies, corridors, marais, points d'observation et haies. Ils ne doivent pas tous devenir des cheminements. Le générateur fictif devra remplacer explicitement les scénarios par des cibles v0.5, en conservant l'UUID seulement lorsque l'identité reste la même.
- Contrôles réalisés hors base : décodage WKB et validité Shapely ; ceci ne vaut pas validation PostGIS, métier, QGIS, ni vérification des bases existantes.

## Dépendances opérationnelles des zones à adapter ultérieurement

| Source | Adaptation future |
|---|---|
| `model/schema.sql` : `sites_zones_geom_contract`, FK `site_terrestre_id`, index GiST, `tr_stamp_sites_zones` | Retirer avec la table après conversion contrôlée ; aucune table générique de remplacement |
| `prestations.site_zone_id`, `prestations_site_zone_id_idx`, `prestations_direct_modes`, `prestations_zone_geometry` | Retirer colonne, FK, index et terme de cible ; supprimer uniquement le contrôle propre au mode zone |
| `assert_prestation_relations`, `prestation_relations_complete`, `prestation_relations_parent` | Adapter les cibles au modèle de dix modes, conserver l'exigence différée d'une cible et les règles position/rive |
| `prestations_carte`, `prestations_fiches` | Retirer jointure/colonnes zone ; choisir la géométrie effective de prestation ou enfant selon le contrat ; conserver les agrégations communales |
| `prestations__sites_terrestres` | Remplacer le chemin zone → site par les parents explicites de mobilier/cheminements/végétation ; éviter tout double comptage |
| `mesures07_resoudre` | Remplacer l'argument zone et sa branche géométrique ; adapter signature et droits associés |
| `mesures07_preparer`, trigger `zz_mesures07_preparer` | Adapter comparaisons des cibles, verrous et appel du résolveur ; mesures toujours stockées |
| `mesures07_parent`, triggers `mesures07_dependants` | Retirer cas zone ; définir propagation sur les nouvelles cibles, sans recopier leur géométrie dans la prestation |
| Projection `desordres_cible_directe` | Neuf cibles, zéro ou une ; retirer la FK zone sans toucher aux associations techniques |
| CABBALR : `generer_sql.py`, `00_preparer.sql`, `06_sites.sql`, `09_verifier.sql`, manifest/SHA256SUMS | Remplacer les zones par des cheminements ; adapter ordre d'import, colonnes, validations et comptes, sans exécuter ici |
| Démo : `generer_sites.py`, `generer_prestations.py`, `auditer_prestations_spatial.py`, imports et SQL | Reconcevoir les fixtures et contrôles spatiaux pour les familles conservées, sans réutiliser de données CABBALR |

## Valid, version et champs résiduels

`version` : `avancer_version_ressource()` incrémente OLD.version ; `ck_version_bornee` impose 1..9007199254740991. `avancer_version_desordre_agrege()` touche la version lors des changements de liens/localisations. `resource_mutations.py`, `troncons.py` et `reperage.py` contrôlent les versions attendues et conflits. Ces usages ne sont pas importés comme nouveau journal ; ils expliquent pourquoi la suppression reste à arbitrer.

`valid` : intervient dans les contraintes géométriques de tronçons, les états sources d'exploitation et les vues/DTO des observations. Les nouveaux objets conservent leur contrat géométrique v0.4 même avec valid=false. Aucune assimilation à l'archivage des désordres. Nullabilité v0.4 conservée.

`nombre_desordres` : lu dans `data_views.py` et `queries.py`, exposé dans les modèles d'observation. La cible unique ne prouve pas son inutilité : une quantité constatée n'est pas forcément un nombre d'entités liées. Conservé à arbitrage, sans valeur 1 automatique ni nouvelle borne métier.

`observateur` / `photographe` : mentions documentaires facultatives remplaçant les FK contacts. Simplification de représentation, pas assimilation à un technicien, prestataire ou compte PostgreSQL. La résolution textuelle doit être vérifiable ; la perte de l'identité relationnelle historique est signalée. Les attributions non résolues ne passent pas silencieusement.

## Inventaire colonne par colonne des observations et photos

Les colonnes non encore arbitrées sont conservées, sans règle métier supplémentaire. Les trois références de tronçon convergent, mais seul `troncon_id` subsiste : aucune fusion d'objets.

### public.observations

| Colonne | Décision | Justification |
|---|---|---|
| created_by | Supprimé | Traçabilité commune ; auteur historique non assimilé au compte PostgreSQL. |
| edited_by | Supprimé | Traçabilité commune ; pas de reprise comme auteur courant. |
| id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| desordre_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| troncon_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| ouvrage_hydraulique_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| equipement_mesure_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| cheminement_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| mobilier_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| reseau_technique_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| amenagement_hydraulique_id | Transformé | ah_ouvrage_id ; correspondance explicite, jamais AH parent direct. |
| zone_stockage_id | Transformé | ah_stockage_id ; correspondance explicite. |
| vegetation_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| ouvrage_particulier_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| structure_amenagement_hydraulique_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| organe_protection_collective_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| prestation_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| ouvrage_telecom_energie_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| ouvrage_voirie_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| reseau_hydraulique_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| structure_digue_id | Transformé | troncon_id ; convergence des UUID, sans fusion d’objets. |
| structure_digue_qualifie | Supprimé | Discriminant composite devenu inutile. |
| profil_travers_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| objet_mesure_hydraulique_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| structure_protection_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| segment_hydrographique_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| berge_id | Transformé | troncon_id ; convergence des UUID, conflits bloquants. |
| berge_id_type | Supprimé | Discriminant composite devenu inutile. |
| element_morphologique_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| urgence_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| designation | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| date_observation | Transformé | NOT NULL : constat daté. Source sans date : diagnostic, pas date du jour inventée. |
| evolution | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| suite | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| suite_apporter_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| observateur_id | Transformé | observateur TEXT facultatif ; attribution documentaire, pas un technicien imposé. |
| nombre_desordres | Conservé ; retrait à arbitrer | Champ présent dans data_views.py, models.py et queries.py ; ne pas le recalculer automatiquement depuis une FK unique. |
| valid | Conservé ; retrait à arbitrer | État de validité source, pas archivage. |
| version | Conservé ; retrait à arbitrer | Concurrence, trigger et borne SQL ; aucune suppression validée. |
| composant_berge_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| trace_position_troncon_id | Supprimé | Cible hors périmètre ; diagnostic de non-convertibilité avant tout import. |
| cree_le | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| modifie_par | Ajouté / destination de transformation | text modifie_par "NULL; session_user derniere ecriture" |
| date_modification | Ajouté / destination de transformation | timestamptz date_modification "NULL; clock_timestamp derniere ecriture" |
| ah_ouvrage_id | Ajouté / destination de transformation | uuid ah_ouvrage_id FK "NULL; objet AH, correspondance explicite" |
| ah_stockage_id | Ajouté / destination de transformation | uuid ah_stockage_id FK "NULL; correspondance explicite" |
| ah_section_id | Ajouté / destination de transformation | uuid ah_section_id FK "NULL" |
| site_terrestre_id | Ajouté / destination de transformation | uuid site_terrestre_id FK "NULL; meme si le site possede des enfants" |
| observateur | Ajouté / destination de transformation | text observateur "NULL; attribution metier documentaire, sans FK contacts" |

### public.photos

| Colonne | Décision | Justification |
|---|---|---|
| created_by | Supprimé | Traçabilité commune ; auteur historique non assimilé au compte PostgreSQL. |
| edited_by | Supprimé | Traçabilité commune ; pas de reprise comme auteur courant. |
| id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| observation_id | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| date_photo | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| designation | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| commentaire | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| photographe_id | Transformé | photographe TEXT facultatif ; même règle de résolution du contact. |
| cote_id | Supprimé | Localisation propre interdite pour les photos. |
| borne_debut_aval | Supprimé | Localisation propre interdite pour les photos. |
| borne_debut_distance | Supprimé | Localisation propre interdite pour les photos. |
| position_debut | Supprimé | Localisation propre interdite pour les photos. |
| pr_debut | Supprimé | Localisation propre interdite pour les photos. |
| borne_fin_aval | Supprimé | Localisation propre interdite pour les photos. |
| borne_fin_distance | Supprimé | Localisation propre interdite pour les photos. |
| position_fin | Supprimé | Localisation propre interdite pour les photos. |
| pr_fin | Supprimé | Localisation propre interdite pour les photos. |
| geometry | Supprimé | Localisation propre interdite pour les photos. |
| valid | Conservé ; retrait à arbitrer | État de validité source, pas archivage. |
| version | Conservé ; retrait à arbitrer | Concurrence, trigger et borne SQL ; aucune suppression validée. |
| storage_key | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| systeme_reperage_id | Supprimé | Localisation propre interdite pour les photos. |
| borne_debut_id | Supprimé | Localisation propre interdite pour les photos. |
| borne_fin_id | Supprimé | Localisation propre interdite pour les photos. |
| cree_le | Conservé | Contenu métier, identité ou traçabilité inchangé. |
| modifie_par | Ajouté / destination de transformation | text modifie_par "NULL; session_user derniere ecriture" |
| date_modification | Ajouté / destination de transformation | timestamptz date_modification "NULL; clock_timestamp derniere ecriture" |
| photographe | Ajouté / destination de transformation | text photographe "NULL; attribution documentaire, pas necessairement technicien" |

## Limites de qualification

Contrôles documentaires et lectures locales seulement. Aucune migration ni exécution QGIS/PostGIS. Trois FK externes subsistent : le Mermaid ne constitue pas un schéma autonome installable. Toute perte de contenu ou attribution non expressément acceptée bloque la conversion correspondante. Les originaux v0 à v0.4 sont préservés.
