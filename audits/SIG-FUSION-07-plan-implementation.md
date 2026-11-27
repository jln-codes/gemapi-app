# SIG-FUSION-07 · Plan d’implémentation de la projection v0.6

**Base de travail.** `gemapi-app-sirs` à `feabcb8926bdc91e4d71fb90ebd3710b07b09d3e`. Le diagramme et les fiches v0.6 sont le contrat de conception. Le [rapport de préparation](SIG-FUSION-07-implementation-readiness.md) donne le delta des 16 tables actuelles, les 103 relations cibles, les corps SQL et les consommateurs QGIS. Les chemins sous `sirs/` cités ici désignent des emplacements proposés pour de futurs travaux.

## Architecture et ordre des décisions

Une installation SIRS comprend **une base** PostgreSQL 16+ avec PostGIS, les tables GEMAPI de milieux, les objets patrimoniaux de public et les catalogues de referentiel. Une connexion QGIS donne accès aux trois schémas sous les droits du même utilisateur. Démo et production peuvent être deux installations indépendantes du même modèle, chacune avec son projet, sa connexion et sa racine de fichiers. Aucun routage entre locataires ni catalogue central de bases.

Pour respecter la séparation du projet, proposer un schéma courant spécialisé dans `sirs/`, installable à vide. Le socle partagé `model/schema.sql`, le plugin et le projet commun gardent leur propre qualification. L’installation SIRS reprend les définitions encore applicables et y intègre directement les différences documentées. Éviter la séquence « installer les zones, les supprimer, réparer ensuite les vues » à chaque installation. Lors de futures évolutions communes, comparer les définitions et comportements partagés. La lecture du code digues-app éclaire les cas historiques ; sa réutilisation intégrale introduirait des dépendances écartées du modèle.

**Socle minimal installable (fin L03).** Une base locale vide peut reconstruire les 48 tables, 425 colonnes, 103 FK, 22 catalogues peuplés, règles différées, traçabilité et mesures, puis recevoir une première prestation, un ouvrage, un désordre, un constat et une photo de test. Un rôle de lecture peut interroger les vues ; un gestionnaire peut enregistrer une prestation sans droits d’édition du parent. Aucune interface, donnée de démonstration ou source SIRS n’est un prérequis de cette preuve.

| Ordre | Lot et objectif | Dépendances et sortie |
|---|---|---|
| L01 | Fixer et amorcer le contrat d’installation et les catalogues | Point de départ. Clés/valeurs stables et environnement isolé. |
| L02 | Construire l’inventaire patrimonial et ses règles d’écriture | L01. Parents et enfants prêts pour le suivi et les prestations. |
| L03 | Fermer le suivi, les dix modes, les mesures et les accès SQL | L02. Socle minimal accepté indépendamment de QGIS. |
| L04 | Exposer les bonnes couches, relations et sélecteurs | L03. Consultation et recherche sur mini-fixture dédiée. |
| L05 | Rétablir le cycle de vie des prestations | L04. Écriture et consultation de chacun des dix modes. |
| L06 | Ouvrir l’inventaire, les désordres et les observations | L04 ; partage de la capture avec L05. Suivi métier qualifié. |
| L07 | Construire la démonstration SIRS reproductible | L03 pour les données, L04 pour le projet. Peut progresser pendant L05/L06. |
| L08 | Adapter rapports, cartes et restitution photographique | L05 + L07 pour prestations ; L06 pour le suivi. |
| L09 | Étendre l’assistant par familles et règles de dessin | L05 + catalogues L07. Indépendant de l’export L08. |
| L10 | Qualifier installation, régressions, paquet et Windows | Tous les lots requis pour les parcours publiés. |

## Lots de réalisation

### L01 · Installation vide et références

- **Périmètre et fichiers.** Partir de `model/schema.sql`, `model/roles_milieux.sql` et des blocs VALUE de `model/schema_development_v0.6.mmd`. Préparer dans `sirs/` le point d’entrée d’installation neuve, la découverte du schéma réel de PostGIS, les trois espaces de noms et le chargement des catalogues. Aucun mécanisme de sélection de base dans le SQL métier.
- **Préalables et risques.** Vérifier base explicitement sélectionnée et vide, version du serveur et extension disponible. Arrêter l’installation sur collision d’objets. Fixer typmods/SRID, valeurs initiales de version/valid lorsqu’elles manquent au Mermaid et politique de clé fichier. Une base hôte peut déjà utiliser public : ce cas relève d’une transition spécifique.
- **Essais et acceptation.** Deux installations vides indépendantes, extension dans public puis dans un autre schéma. Comparer les 298 tuples des 22 référentiels, identifiants, dépendances catégorie/type et contraintes uniques. Les sept types physiques et cinq typologies doivent correspondre exactement. Refuser un id/catégorie discordant et faire remonter l’erreur au lanceur.

### L02 · Patrimoine, géométries et traçabilité

- **Périmètre et fichiers.** Dans le DDL SIRS, reprendre milieux.digues, repères, AH, stockages, ouvrages AH, sections, sites et autres tables conservées. Ajouter public.troncons, les trois familles techniques et mobilier/cheminements/végétation avec leurs FK. Adapter stamp_modification et indices spatiaux ; traiter signatures hydro comme dans `model/schema.sql`.
- **Préalables et risques.** L01. Distinguer geom, geometry, geometry_reperage et geom_reference ; un axe de repérage ou un repère hydro ne transforme pas une géométrie facultative en géométrie obligatoire. Spécifier un comportement cohérent en écriture concurrente pour version. Vérifier le stamp sur les référentiels qui n’ont pas de cree_le.
- **Essais et acceptation.** Tester les sept types, une crête invalide et les huit champs interdits, BERGE qualifiée, axes/surfaces invalides, parents manquants/ambigus, et immutabilité de cree_le. Les trois affectations valides sur huit d’un ouvrage hydraulique passent. Pour chacune, la suppression d’un parent utilisé échoue et réussit après réaffectation contrôlée. Préserver qualification/revalidation des repères et sections en transaction.

### L03 · Suivi, prestations et premier schéma complet

- **Périmètre.** Après L02, installer désordres, observations, photos, quatre associations et contraintes des objets liés ; finaliser prestations, vues et droits. Livrer par incréments vérifiables : d’abord les FK du suivi, puis comptage des cibles, puis vues/mesures/permissions. Créer les deux tables d’extrémité avant leurs FK composites. Sources de comportement : `model/schema.sql` et `model/roles_milieux.sql`.
- **Contrats.** Valider le repli des trois nouvelles familles avant de figer mesures07_resoudre/preparer/parent. Poser vues et fonctions après leurs dépendances, étendre le trigger différé, contrôler les GRANT après création. Exposer l’agrégation digue et les parents AH/site, sous une identité stable par objet ; limiter la reconnaissance hydro indirecte au rapport.
- **Essais et acceptation.** Comparer le catalogue serveur au Mermaid, y compris PK/UK et cibles composites. Dix prestations à cible unique passent ; zéro échoue au commit et chaque paire échoue au contrôle immédiat. Douze cibles d’observations datées admises, zéro ou deux refusées. Tester désordre sans cible directe + association, archivage et conservation des photos. Mesures avant/après déplacement d’un enfant, basculement de cible et deux transactions simultanées. Exercer les trois profils avec SELECT et écritures autorisées/refusées. Cette étape livre le socle minimal.
- **Risque principal.** Une vue juste sur le cas nominal peut masquer une propagation incorrecte des mesures ou un privilège manquant lorsque la forme est héritée.

### L04 · Projet QGIS et lecture du patrimoine

- **Fichiers et dépendances.** L03. Utiliser `demo/prestations_demo.qgz` comme référence de configuration pour le projet spécialisé, `plugin/gemapi_app/session_data.py`, `patrimony_spatial.py`, `creation.py`, `prestation_focus.py`, `watercourse_labels.py`. Décrire dans les lecteurs spécialisés les correspondances autorisées entre famille, schéma/table/vue, id, libellé, forme et parent. Utiliser des identifiants SQL fixes.
- **Travaux.** Retirer cinq sources QGIS zonales et leurs vingt relations ; contrôler aussi relations de formulaire, champs affichés, expression d’étiquette, sous-requêtes, clés provider et filtre de dimension. Ajouter les couches et fiches nécessaires, maintenir le même service de connexion et les trois représentations de prestations_carte.
- **Essais et acceptation.** Charger le projet de test à froid ; aucune couche invalide ou relation pendante. Vérifier les expressions et actions avec un utilisateur Consultation. Tester nom absent, deux homonymes, forme NULL ou multipartie et cache vidé après changement de projet. Une couche homonyme d’une autre connexion ne doit jamais servir à une action d’écriture.

### L05 · Prestations et dessin

- **Fichiers.** Après L04 : `record.py`, `creation.py`, `management.py`, `plugin.py`, `permissions.py`, `digitize.py`, `create.ui` et `form.ui` dans le périmètre QGIS décrit par l’audit. Préserver la voie commune sur le schéma du socle ; qualifier les ajouts spécialisés sur le projet SIRS.
- **Travaux.** Aligner les dix cibles dans SQL de lecture, formulaire, changement de famille, carte, sérialisation atomique INSERT/UPDATE, liste de gestion et suppression. Modifier les retours aux couches et le contrôle des champs position/rive. Préserver choix du type, déroulé de capture, deux photos et xmin.
- **Essais et acceptation.** Créer, relire et modifier chaque mode y compris par action carte ; changer de cible avec/sans dessin, annuler, fermer et réouvrir. Une valeur obsolète ou un conflit de version refuse l’enregistrement et conserve le brouillon. Mesures et focus de la carte correspondent à l’objet enregistré. Risques : effacement d’une autre FK, deux formes concurrentes ou double comptage à la lecture.

### L06 · Inventaire, constats et fichiers

- **Fichiers.** L04, contrat de capture de L05. Entrées du projet spécialisé et du plugin (accueil, permissions, session, accès aux couches) ; `digues.py`, `ah_sections.py` pour les actions existantes ; `photo_paths.py` pour comparer le contrat des fichiers. Éviter de surcharger le formulaire prestation pour une observation.
- **Travaux.** Distinguer composants AH du socle, ouvrages techniques, équipements et tronçons. Permettre recherche, création et édition des trois nouvelles familles. Depuis l’objet ou le désordre, accéder aux observations datées, à l’historique et aux fichiers associés. Prévoir affichage d’une localisation indisponible. Exposer la réaffectation avant suppression d’un parent protégé.
- **Essais et acceptation.** Un désordre archivé conserve UUID, visites et photos ; un constat sur mobilier sans désordre reste autonome. Deux observations sur la même cible restent distinctes. Vérifier refus d’édition sans droit, concurrence, fichier inaccessible, clé déjà utilisée et échec après sélection d’un fichier. Aucune copie ou suppression de fichier sans convention validée. La galerie enrichie peut être livrée après lecture fiable des références.

### L07 · Jeu fictif et projet de démonstration

- **Sources concernées.** `demo/README.md`, `demo/data/importer_base_neuve.sh`, `generer_sites.py`, `generer_prestations.py`, `auditer_prestations_spatial.py`, `generer_digues.py` et `generer_ah_sections.py` sous `demo/data/`. Préparer les ressources du démonstrateur spécialisé séparément des données permanentes.
- **Travaux.** Après L03, créer références et parents avant enfants, associations après leurs deux extrémités, prestations/observations après leurs cibles, photos en dernier. Répartir les anciens scénarios fictifs de zones selon leur usage entre site ou enfants. Conserver les identités d’objets de même sens ; utiliser des UUID déterministes pour les nouveaux cas. Obtenir des fichiers accessibles depuis le projet de démonstration. Intégrer le projet L04.
- **Essais et acceptation.** Reconstruire deux fois à partir de bases vides et comparer ids, géométries, affectations et mesures (hors horodatages d’exécution). Vérifier cas directs et indirects, un site sans enfant, tronçon sans forme, familles mixtes, archivage et deux circuits photo. Conserver ou expliquer les écarts aux témoins du jeu existant (100 prestations distinctes, 11 au rapport AH témoin). Ne jamais rejouer l’importeur neuf sur une base permanente.

### L08 · Rapports et exports

- **Fichiers.** Après L05/L07, `report_data.py`, `report_dialog.py`, `report_maps.py`, `report_pdf.py`, `report_synthetic_portrait.py`, `report_worker.py` et `report.ui`. Le suivi documentaire dépend aussi de L06.
- **Travaux.** Faire évoluer ensemble sélection SQL, ROW_FIELDS, filtres/compteurs et lignes sérialisées. Cartographier la forme de prestation ou celle de l’enfant selon la règle SQL. Conserver les contextes parents et agrégats sans doublon. Garder les photos directes des prestations et traiter séparément la restitution des photos de constats.
- **Essais et acceptation.** Ids et totaux identiques entre gestion, rapport global et liste filtrée attendue. Tester la même prestation reconnue par plusieurs sections, mesures propres/empruntées, photo absente, imprimés détaillés et synthétiques, lots multipages et texte accentué. Vérifier géométrie et cadrage sur le PDF rendu, intégrité du fichier et traitement de l’échec du worker.

### L09 · Assistant de saisie

- **Fichiers.** L05/L07. `assistant.py`, `assistant_dialog.py`, `creation.py`, `voice.py` et tests assistant. D’abord restaurer le parcours existant sur AH/stockage après retrait de zone, puis étendre les familles avec repli, enfin celles à dessin obligatoire.
- **Travaux.** Adapter le contexte des catalogues, les propositions admises, les libellés et le contrôle au retour dans le formulaire. Conserver vérification des identités et preuves de dates. Autoriser le transfert d’un brouillon à compléter pour le dessin tout en interdisant son écriture incomplète. Mesurer la taille de la demande avant élargissement aux tronçons.
- **Essais et acceptation.** Réponses simulées : deux parents homonymes, type de tronçon pris pour un nom, confusion entre ouvrage AH et ouvrage hydraulique technique, objet disparu après proposition, conflit de dates, multi-cible, besoin de dessin. Aucun UUID fourni par le modèle n’est accepté comme décision. Pas de géométrie synthétique ni d’écriture avant confirmation humaine.

### L10 · Qualification et mise en service ultérieure

- **Dépendances et fichiers.** L01 à L09 ; projet SIRS, `plugin/tools/build_plugin.py`, `plugin/tests/test_package.py`, `pdf_runtime.py`, `report_worker.py`, documentation d’installation et matrice ci-dessous. Les adaptations spécialisées doivent conserver le comportement du plugin sur les installations communes auxquelles il reste destiné.
- **Travaux.** Repartir d’un clone et d’une base locale vide, puis ouvrir le projet avec chaque profil, installer le ZIP correspondant aux sources, répéter les parcours sur QGIS Linux et Windows. Comparer résultats de rapports et lisibilité des caractères, chemins des photos, authentification et processus enfants.
- **Acceptation.** Enregistrer versions des environnements, défauts et résultats séparés pour les deux OS. Une validation Windows réelle est nécessaire pour une diffusion générale. Le feu vert d’installation neuve reste indépendant de toute reprise d’une base existante.

## Matrice de qualification

Les noms suivants désignent des fichiers de `plugin/tests/`. « Disponible » signifie présent dans le dépôt ; aucun résultat d’exécution de ces suites n’est revendiqué par cet audit.

| Domaine | Disponible sur le socle | À faire évoluer pour SIRS | À créer / condition de passage |
|---|---|---|---|
| Installation SQL/PostGIS | test_postgres_integration.py, test_demo_import.py, test_categories_postgres.py | Ajouter l’entrée SIRS et les 22 catalogues en base jetable ; contrôler schéma réel de l’extension. | Introspection indépendante des 48 tables, 425 colonnes, 103 FK, clés uniques et différabilité ; 298 valeurs et références exactes ; aucun objet hors périmètre. |
| Contraintes et concurrence | test_rattachements_model.py, test_prestations_native_measures.py, test_ah_sections.py, test_prestation_delete_postgis.py | Sept → dix cibles, repli des géométries, propagation et suppression protégée. | Matrices zéro/une/toutes paires, dont 12 observations et 9 désordres ; huit états parent ouvrage, six cibles objets liés, BERGE composite, CHECK crête, archivage et version ; exercices multi-session du stamp/recalcul. |
| Privilèges | test_roles_postgres.py, test_categories_postgres.py | Tester vues security_invoker et signatures modifiées sous les trois profils. | Lecture et écritures autorisées/refusées dans les trois schémas, verrouillage du parent sans élargir les droits et refus de modifier cree_le. |
| PyQGIS, provider et carte | test_qgis_project_sync.py, test_demo_sites_zones_qgis.py, test_patrimony_spatial_integration.py, test_digues_qgis.py, test_ah_sections_qgis.py | Garder les tests zone du socle pour son projet ; remplacer les assertions zonales dans le parcours spécialisé. Préserver les identifications et les traces. | Sources/relations/actions SIRS résolues, sélection sans géométrie, noms identiques dans deux familles, filtre Multi*, connexion unique, focus et invalidation de cache. |
| Formulaires et cycles d’écriture | test_form_metier_ui.py, test_edit_integration.py, test_prestation_lifecycle_qgis.py, test_digitize_trace.py, test_photo_ui.py | Cibles, changement de dessin, gestion des anciennes FK, droits et deux photos. | Création de chaque famille, parcours désordre/observation/photo et archivage/relecture ; abandon et modification concurrente. |
| Mesures, rapports et photos | test_report_data.py, test_report_maps.py, test_demo_ah_reports.py, test_detailed_report.py, test_synthetic_portrait_report.py, test_photo_paths.py, test_report_worker.py | Retirer hypothèses zone, couvrir tous les parents, comparer quantités propres et héritées, PDFs et export par lots. | Fichiers manquants/clé en collision, galerie liée à la bonne visite, constats sans localisation, comptage indépendant du nombre de photos, comparaison visuelle. |
| Assistant IA | test_assistant_validation.py, test_assistant_linguistics.py, test_assistant_integration.py, test_assistant_qgis.py, test_voice.py | Faire évoluer options, catalogues, dialogue de correction et hypothèse NULL. Conserver preuves, refus d’ambiguïté, nouveau brouillon et réponses tardives. | Dix familles autorisées pour prestation, refus d’une famille technique hors liste, brouillon à dessiner et refus de sauvegarde prématurée ; catalogue changé/partiel et sélection humaine. |
| Démonstration | test_demo_import.py, test_demo_topologie.py, test_demo_ah_reports.py | Tester ressources spécialisées et import neuf ; garder témoins hydro/sections du socle. | Reproductibilité à partir du jeu fictif seul, aucune source réelle, présence des scénarios et cohérence UUID/mesures dans QGIS. |
| Installation du plugin et Windows | smoke_import.py, test_package.py, test_pdf_runtime.py, test_pdf_export_modes.py, test_qgis_runtime.py | Installer le ZIP en profil neuf, sonder les dépendances réellement embarquées et les URI de connexion locales. | Exécution sur Windows QGIS et Linux QGIS, chemins Unicode/espaces/partages, polices, processus PDF, lectures de fichiers, choix de connexion, permissions, tests manuels d’actions et de capture. Plateforme Qt native Windows, offscreen pour tests Linux applicables. |

## Installation neuve, transition et décisions différées

- **Installation neuve.** Exiger une destination locale explicitement nommée, PostGIS installé et objets cibles absents. Installer définitions, contraintes, fonctions, triggers, vues et rôles dans un ordre testé ; contrôler le catalogue et un premier parcours à blanc. Charger les exemples uniquement dans la base choisie pour la démonstration. La base de production peut rester vide de données fictives. Les chemins et comptes du projet QGIS identifient sa seule base.
- **Base existante.** Une transition nécessite un inventaire séparé des schémas, données, dépendances SQL/QGIS et droits effectifs. Préparer une sauvegarde dont la restauration a été testée et répéter sur copie isolée. Qualifier les objets qui perdent une cible et les références de fichiers, conserver les UUID d’identité établie, refuser pertes ou affectations implicites. Comparer effectifs, géométries, liens, permissions et parcours avant bascule contrôlée et décision de retour. Le DDL d’installation neuve ne s’applique pas sur cette base.
- **Choix techniques avant publication.** Documenter le mode de stockage des photos patrimoniales, les droits d’écriture et de suppression associés, les défauts laissés ouverts dans le Mermaid, la politique de version et les résultats du test de repli géométrique. Le comptage d’objets ne vaut pas qualification des performances.
- **Périmètre différé.** La reprise CABBALR est un chantier distinct, potentiellement dépendant du migrateur. Les conversions de données réelles et l’adaptation éventuelle du migrateur feront l’objet d’une intervention indépendante.
