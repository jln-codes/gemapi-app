# SIG-FUSION-10 — Compatibilité du plugin QGIS avec v0.6.1

Le plugin GEMAPI-App 0.8.6 et le projet de démonstration utilisent la base v0.6.1. La référence de comparaison du jeu fictif est le commit `64fa2a6d2184c97dc2dfdc253c65cd3e087ef426`. Les essais ont utilisé les sources versionnées pour installer des bases locales jetables.

## Résultats sur le jeu fictif

| Contrôle | Résultat |
|---|---|
| Gestion et rapports globaux | 100 prestations distinctes. Les rapports conservent une fiche par UUID. |
| Localisation effective | 88 géométries propres et 12 empruntées à la végétation. Les données cartographiques proviennent de `milieux.prestations_carte`. |
| Enfants proposés pour les 12 sites | 4 mobiliers, 2 cheminements et 19 objets de végétation. |
| Filtre sur le site `6fb4c2ae-3be1-5ba1-cc5f-31daadd0c6f4` | Les huit UUID du rapport et de la gestion correspondent à la vue `milieux.prestations__sites_terrestres`. |
| Édition d'une prestation historique sur végétation | Modification de l’intitulé. Relecture de la même cible, de la quantité, de l’unité, des deux références photographiques et de leurs commentaires. La géométrie propre reste NULL. |
| Saisie et consultation | Cinq créations par le formulaire standard, une par famille enfant et deux sur les familles AH existantes. Contrôle du rattachement et de la provenance des mesures après sauvegarde. |
| Données provenant d’une autre application | Lecture d’une prestation sur tronçon et sur chacune des trois familles avec un parent hors site. Les requêtes de gestion et de rapport préservent leur identité et ne leur attribuent aucun site. |

## Fichiers et parcours

| Emplacement | Adaptation |
|---|---|
| `plugin/gemapi_app/record.py` | Catalogue des dix cibles, avec schéma, clé de prestation, libellé et géométrie. Une écriture modifie les attributs et le rattachement dans la même instruction, sous contrôle de version `xmin`. |
| `creation.py`, `management.py`, `patrimony_spatial.py` | Lecture des désignations et géométries de `public.mobilier`, `public.cheminements` et `public.vegetation`. Le sélecteur ne propose que les enfants ayant un site direct. Le clic cartographique fournit une référence de recherche. Le technicien confirme l’objet par UUID. La gestion filtre sur le site parent. |
| `assistant.py`, `assistant_dialog.py`, `voice.py` | Le catalogue comprend les deux familles AH existantes et les trois familles de sites. Les noms des sites distinguent les objets homonymes. La vérification du brouillon relit les références sur la connexion active avant d’ouvrir le formulaire standard. |
| `report_data.py`, `report_maps.py`, `report_synthetic_portrait.py` | La requête partagée par les rapports détaillé et synthétique associe les enfants au site par sa FK. La géométrie propre est prioritaire. Les mesures empruntées au patrimoine sont affichées séparément de la quantité déclarée. Les agrégations hydrographiques gardent leurs critères de qualification. |
| `demo/prestations_demo.qgz` | Remplacement des cinq anciennes sources et des vingt relations natives dépendant des zones. Le projet compte 33 couches et 70 relations. Chaque famille dispose d’un catalogue et de trois couches cartographiques en lecture seule. Le filtre de dimension couvre les géométries simples et multiples en EPSG:3950. |
| `demo/README.md`, `plugin/README.md`, `plugin/gemapi_app/help.md`, `metadata.txt` | Connexion au démonstrateur, installation de l’extension, aide aux utilisateurs et version du paquet. |
| `plugin/tests/` | Remplacement de `test_demo_sites_zones_qgis.py` par `test_demo_site_children_qgis.py`. Adaptation des jeux de tests, des assertions de rattachement, des ouvertures de projet et des contrôles SQL, Qt, assistant et PDF. |

Le projet utilise le service libpq `gemapi_demo`. Le nom d’hôte, le port, le nom de la base et le compte sont configurables sur le poste. Les sources des couches et les références mémorisées par les widgets utilisent ce même service. Les propriétés natives RelationReference et ValueRelation sont contrôlées sur le projet distribué avec une connexion de technicien. Le projet CABBALR conserve son propre contrat de couches. L’utilitaire de synchronisation des projets refuse de recopier une configuration entre ces deux modèles divergents.

## Qualification

Les contrôles ci-dessous ont utilisé QGIS 3.44.15 sous Linux, Qt en mode offscreen et le fournisseur PostgreSQL de QGIS. Les cas de test supplémentaires ont été créés uniquement dans les bases jetables.

| Suites représentatives sous `plugin/tests/` | Vérification effectuée |
|---|---|
| `test_demo_site_children_qgis.py` | Installation par l’importeur officiel, ouverture du QGZ, validité des couches et relations, destinations des widgets, sélection et sauvegarde sous le rôle Prestations, refus d’un objet inconnu ou hors site, focus et export des deux formats de rapport. |
| `test_sirs_postgis.py` | 22 tests réussis avec PostGIS dans public puis dans un schéma dédié. Catalogue, droits, concurrence, parents, géométries et traçabilité. La suite dédiée `test_roles_postgres.py` a également vérifié la lecture des vues et les droits des trois profils dans les deux configurations. |
| `test_rattachements_model.py`, `test_postgres_integration.py`, `test_edit_integration.py`, `test_prestation_delete_postgis.py` | 45 contrôles de rattachement dans la première suite. Écriture atomique, remise à NULL des anciennes FK, refus des conflits de version et rollback. Suppression contrôlée et préservation des parents. |
| `test_hydro_selection_integration.py`, `test_digues_qgis.py`, `test_ah_sections.py`, `test_ah_sections_qgis.py` | Sélection de tronçons de cours d’eau distincts, remplacement de la cible, rendu des deux rives, 22 tests des sections AH et 14 contrôles QGIS/PostGIS du parcours AH. |
| `test_management_integration.py`, `test_report_integration.py --suite sql`, `test_report_ah_integration.py` | Recherche et filtre sur volumes augmentés, vérification des ensembles d’UUID et des quantités pour les 100 prestations. Vérification des appartenances directes et indirectes AH et des sélections croisées. Le comparatif PDF AH optionnel de cette dernière suite a été ignoré. |
| `test_assistant.py`, `test_assistant_validation.py`, `test_assistant_qgis.py`, `test_assistant_integration.py` | Respectivement 40, 16 et 29 tests pour les trois premières suites. Homonymes de végétation sur deux sites, familles AH avec catalogues de sites vides, UUID absents et dates à confirmer. Essai d’enregistrement standard depuis l’assistant avec un serveur PostGIS réel et des réponses Mistral simulées. |
| `test_mod_geom_project.py`, `test_patrimony_spatial_integration.py` | Ouverture du projet et du formulaire natif. Les trois couches de prestations couvrent 33 points, 32 lignes et 35 polygones sans UUID dupliqué. La recherche spatiale a exercé trois rayons et les cinq index GiST contrôlés. |
| `test_prestation_focus_qgis.py`, `test_report_maps.py`, `test_report_worker.py`, tests des rapports détaillé et synthétique | Focus par UUID, emprises et projections, cartes avec provenance, exports PDF. Le processus PDF isolé a aussi été exécuté avec accès au fond IGN. |
| `test_qgis_project_sync.py`, `test_voice.py`, `test_voice_stability.py` | 24 tests de configuration des projets et 37 tests vocaux réussis. Deux des quatre scénarios de stabilité vocale ont dépassé le délai de 40 secondes pendant la première exécution en parallèle. Tous deux ont réussi lors de leur réexécution avec le délai d’origine. |
| `plugin/tools/build_plugin.py` et test de paquet | Construction du ZIP installable et comparaison du contenu avec les sources du plugin. |

Pour rejouer le contrôle transversal depuis la racine, avec Docker et le Python de QGIS installé sous Linux :

```sh
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_demo_site_children_qgis.py
```

## Limites de qualification

La validation sous Windows avec une installation réelle de QGIS reste à réaliser. Les scénarios d’assistant exercent le traitement local des réponses et la sauvegarde. La disponibilité du service Mistral et l’accès aux photographies sur un partage réseau dépendent du poste. La gestion patrimoniale des tronçons, des enfants hors site, des ouvrages techniques, des désordres, des observations et de leurs photos relève de gemapi-dev.
