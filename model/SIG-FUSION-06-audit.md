# SIG-FUSION-06 · Rattachements et autonomie structurelle

## Résultat de la comparaison

| Mesure issue du Mermaid | v0.5 | v0.6 | Écart |
|---|---:|---:|---:|
| Tables métier | 23 | 22 | −1 |
| Tables associatives | 4 | 4 | 0 |
| Référentiels | 22 | 22 | 0 |
| **Tables** | **49** | **48** | **−1** |
| Colonnes | 453 | 425 | −28 |
| Relations internes | 110 | 103 | −7 |
| FK externes | 3 | 0 | −3 |
| Cibles admissibles d’une observation | 13 | 12 | −1 |

Le retrait de 18 colonnes de structures AH, de neuf colonnes de tronçons et d’une cible d’observation explique les 28 colonnes. Les sept relations internes retirées sont deux auto-références de tronçons, quatre liens de la structure AH aux référentiels et une FK des observations. Les 22 référentiels et leurs 298 entrées documentées sont identiques dans les deux versions.

**Sources de vérification.** Projection et audit v0.5 au commit `350d160eb7670611bac33b5380fb4b3cae7b94a6`. Pour la liste des termes de la contrainte de crête, contrat explicite v0.4 repris en v0.5. Lecture du socle dans `model/schema.sql` et du DDL `digues_app/target/schema_current.sql` de digues-app/development à `eecec0a44f25a908484b76f838a7e2be0c8cfee5`. Les identifiants du DDL source ci-dessous permettent de retrouver les dépendances historiques.

## Tronçons · 38 → 29 colonnes

| Colonne retirée | Fonction source et motif de retrait |
|---|---|
| `troncon_support_id` | UUID du tronçon support classique. Le lien récursif disparaît. |
| `berge_support_id` | UUID de la berge support. Seul cet usage de la berge disparaît. |
| `segment_hydrographique_support_id` | UUID du segment support, dernière FK externe d’un tronçon. |
| `berge_support_id_type` | Constante calculée BERGE propre à la FK de support de berge. |
| `troncon_support_qualifie` | Constante calculée vraie du côté enfant de la FK de support classique. |
| `est_support_classique` | Côté parent de la même FK. En v0.5, type INDETERMINE, digue et désignation renseignées. Le consommateur historique `traces_positions_troncons.fk_trace_support_classique` est hors projection. |
| `est_structure` | Qualifiait CRETE, TALUS, TALUS_RISBERME, RISBERME et FRANC_BORD. La FK composite des observations avait disparu en v0.5. `localisations_objets.fk_localisation_structure` est extérieure. Aucun consommateur interne restant. |
| `position_pied_autorisee` | Qualifiait BERGE et TALUS pour `traces_positions_troncons.fk_trace_position_pied` exclusivement dans le DDL historique. Aucun consommateur projeté. |
| `position_sommet_autorisee` | Qualifiait BERGE, TALUS et RISBERME pour `traces_positions_troncons.fk_trace_position_sommet`. Aucun consommateur projeté. |

### Inventaire des clés, index et contrôles

| Objet | Traitement v0.6 |
|---|---|
| `fk_troncon_troncon_support`, `fk_troncon_support_berge` | Retrait des deux FK composites récursives différables. |
| `fk_troncon_segment_hydrographique_support` | Retrait de la FK externe simple. |
| `uq_troncons_role_support`, `uq_troncons_role_structure`, `uq_troncons_position_pied`, `uq_troncons_position_sommet` | Retrait des quatre clés (id, rôle) et de leurs index uniques implicites après examen des consommateurs ci-dessus. |
| `idx_troncons_support` | Retrait de l’index partiel sur le support classique renseigné. |
| `ck_troncons_support` | Retrait du contrôle sur la présence des supports. |
| `ck_troncons_crete_fields` | Seuls les termes `segment_hydrographique_support_id` et `berge_support_id` quittent la liste v0.5. Pour CRETE, huit champs doivent rester NULL : `cote_id`, `position_id`, `fonction_haut_id`, `fonction_bas_id`, `nature_haut_id`, `nature_bas_id`, `materiau_haut_id`, `materiau_bas_id`. |
| `uq_troncons_type` et `fk_ouvrage_lie_berge` | Conservation de UNIQUE (id, type_troncon_id) et de la FK composite différable de `ouvrages_hydrauliques__objets_lies`. Le couple (berge_id, berge_id_type), dont le second terme est la constante générée BERGE, interdit de désigner un talus comme berge. L’annotation v0.5 « NULL » de ce discriminant décrivait insuffisamment son calcul, désormais explicite. |
| `ck_troncons_type`, `ck_troncons_geometry_b4`, `ck_troncons_axe_reperage`, `ck_version_bornee` | Protection du type, de la forme des risbermes et francs-bords validés, de l’axe de repérage et de la version. L’index de digue et l’index spatial de géométrie restent indépendants du retrait. |

**Colonnes conservées (29).** Identité et classification : `id`, `type_troncon_id`, `digue_id` obligatoire, `typologie_troncon_id`, `type_rive_id`. Description et suivi : `designation`, `commentaire`, `date_debut`, `date_fin`, `source_id`, `cote_id`, `position_id`. Géométries : `geometry`, `geometry_reperage`. Construction : `nature_id`, `materiau_id`, `fonction_id`, leurs six variantes haut/bas et `num_couche`. Gestion : `valid`, `version`, `cree_le`, `modifie_par`, `date_modification`.

**Types et usages.** INDETERMINE, BERGE, CRETE, TALUS, TALUS_RISBERME, RISBERME et FRANC_BORD gardent exactement leurs identifiants, codes et libellés. Les cinq typologies constructives sont conservées. Les FK simples vers le tronçon restent accessibles aux sept types pour désordres, observations, prestations, équipements de mesure, ouvrages particuliers et hydrauliques, mobilier, cheminements et végétation. La qualification BERGE concerne uniquement le rôle spécialisé dans les objets liés.

## Structures AH et observations

La table `public.amenagements_hydrauliques__structures` disparaît avec sa PK, ses deux FK historiques `fk_amenagement_hydraulique` et `fk_structure_zone`, ses quatre FK `fk_db2_materiau_id`, `fk_db2_fonction_id`, `fk_db2_nature_id` et `fk_db2_source_id`. Le contrôle `ck_structure_parent_zone_unique` disparaît avec elle. L’index source `ix_structures_amenagements_zone` et le contrôle source `ck_structure_zone_a_qualifier` n’ont plus d’objet cible. Les tables AH du socle, les ouvrages techniques et les référentiels constructifs restent disponibles.

Sur `public.observations`, retrait de `structure_amenagement_hydraulique_id`, de `fk_structure_amenagement_hydraulique` et d’un seul terme de `ck_cible_unique`. Les douze termes restants correspondent aux douze FK vers des tables métier. Les FK d’urgence et de suite à apporter sont des qualifications indépendantes. L’observation reste datée, avec exactement une cible et zéro à plusieurs photos.

## Parent obligatoire des ouvrages hydrauliques

`ck_ouvrage_parent_unique CHECK (num_nonnulls(troncon_id, ah_ouvrage_id, ah_stockage_id) = 1)` remplace la borne supérieure v0.5. Les trois FK vers les PK UUID de `public.troncons`, `milieux.ah_ouvrage` et `milieux.ah_stockage` sont individuellement facultatives et portent **ON DELETE RESTRICT**. La suppression d’un parent référencé exige une réaffectation contrôlée de ses ouvrages. Sur huit combinaisons, les trois à un parent sont admissibles, la combinaison vide et les quatre combinaisons multiples sont refusées. Les 18 colonnes de l’ouvrage sont conservées.

## Inventaire final des dépendances externes

| FK externe v0.5 | Destination historique | Résolution |
|---|---|---|
| `amenagements_hydrauliques__structures.amenagement_hydraulique_id` | `public.amenagements_hydrauliques(id)` | Famille retirée. |
| `amenagements_hydrauliques__structures.zone_stockage_id` | `public.zones_stockage(id)` | Famille retirée. |
| `troncons.segment_hydrographique_support_id` | `public.segments_hydrographiques(id)` | Relation de support retirée. |

Les deux extrémités de chacune des 103 relations sont déclarées. Les 104 colonnes marquées FK sont couvertes une fois, dont les deux colonnes de l’unique FK composite. Vérification des types, des clés cibles, des libellés de relations du socle contre son SQL et des mentions dans les contrats. La référence à `milieux.stamp_modification()` désigne une fonction du socle. Les marqueurs de schéma PostGIS et de SRID sont des paramètres de type géométrique. Le terme « support » du lien entre cours d’eau et section AH désigne son cours d’eau de référence. Aucun de ces éléments ne représente une FK externe à résoudre.

## Reprise future et questions ouvertes

- Inventorier les liens de support abandonnés. Conserver séparément UUID, type, forme et axe de chaque tronçon. Aucune relation de remplacement.
- Inventorier les documents `StructureAmenagementHydraulique` et leurs références. Identifier chaque observation et chaque photo associée, y compris son fichier. Une observation ciblant uniquement la structure reste non convertible jusqu’à une décision individuelle. Conserver les sources intactes.
- Distinguer un ouvrage orphelin d’un conflit de plusieurs candidats. Dans les deux cas, bloquer la conversion. Une correspondance d’UUID et de famille doit être justifiée. Une proximité spatiale ou nominale ne suffit pas.
- Restent à instruire les correspondances individuelles, le sort des constats bloqués et les cas CABBALR/démo déjà identifiés en v0.5. L’inventaire quantitatif des objets historiques et la preuve d’installation et de fonctionnement demandent des travaux ultérieurs. Les présentes vérifications portent sur la projection documentaire.

## Contrôles de livraison

Le rendu SVG par Mermaid CLI contient 48 entités, 425 attributs et 103 traits de relation. La comparaison avec v0.5 a contrôlé les ensembles de tables, de colonnes et de relations, les discriminants, les termes des contrôles de crête et de cible, ainsi que les valeurs de chaque référentiel. La seule annotation précisée sur une colonne conservée est le calcul de `berge_id_type`.

Le PDF compte 70 pages. Les sommaires des pages 2, 3 et 4 donnent la première page de chacune des 48 fiches. Vérification des numéros imprimés, des destinations cliquables sur le nom et le numéro, des renvois entre tables et du retour au sommaire. Les 808 liens internes ont une destination valide. Les noms de colonnes, les entrées des nomenclatures et l’empreinte du Mermaid ont été contrôlés dans le PDF. Douze pages ont fait l’objet d’un contrôle visuel, dont les trois sommaires et les fiches de tronçons, observations, ouvrages hydrauliques, objets liés et types physiques.
