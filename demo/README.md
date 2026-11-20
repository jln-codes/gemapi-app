# SIG Milieux — démonstrateur

Ce répertoire contient les données de démonstration du modèle canonique actuel. La définition est conservée dans `../model/`. Les UUID existants sont conservés et les géométries utilisent EPSG:3950.

Les quatre catégories sont initialisées par le schéma canonique. Les neuf types
de `gpkg/referentiels.gpkg` et `data/05_types_prestations.sql` conservent leurs UUID.
Le classement de Suivi de milieu et Étude dans Génie écologique est provisoire ;
les rattachements restent modifiables dans PostgreSQL sans modifier les prestations.

Les catégories sont créées une seule fois par `model/schema.sql` ; le script
`data/05_types_prestations.sql` initialise les types et peut être réexécuté
sans doublon, changement d’UUID ni mise à jour des lignes déjà identiques.
L’importeur complet reste réservé à une base neuve : ne pas rejouer
`schema.sql` sur une base existante.

Pour importer directement le GeoPackage dans une base neuve après
`schema.sql`, les catégories sont déjà présentes. Importer seulement la couche
`types_prestations` dans la table vide, en conservant les colonnes UUID et en
écartant le FID SQLite :

```sh
ogr2ogr -f PostgreSQL "PG:service=demo_local" gpkg/referentiels.gpkg \
  -append -nln milieux.types_prestations \
  -sql "SELECT id,code,libelle,actif,categorie_id FROM types_prestations" -unsetFid
```

Adapter le service libpq à une connexion locale vérifiée. Pour réinitialiser
le référentiel déjà chargé, utiliser le SQL ci-dessus plutôt que refaire un
append OGR. Le test `plugin/tests/test_categories_postgres.py` vérifie cet import,
la concordance des quatre catégories et des neuf types, puis deux passages SQL.
Les tests PostgreSQL automatisés créent leurs propres bases jetables ; ils
ne migrent pas la base de démonstration permanente.


## Contenu

Un AH peut posséder zéro ou un stockage et zéro à plusieurs ouvrages. Ces
enfants sont facultatifs et indépendants ; chacun référence obligatoirement
un parent AH existant. L’unicité de `ah_stockage.ah_id` est garantie par
PostgreSQL et configurée comme contrainte forte dans le projet QGIS.

### Sections hydrographiques des AH

`milieux.ah_sections` référence le **parent AH**. L'utilisateur choisit un cours
d'eau qualifié et ses fractions de début/fin. Plusieurs sections et plusieurs
rivières sont possibles, y compris sans stockage ou au-delà de son emprise.
La géométrie est exclusivement calculée côté serveur avec `ST_LineSubstring`.
Le doublon exact
`(ah_id,cours_eau_id,debut_fraction,fin_fraction)` est interdit.

Le contrôle serveur commun `cours_eau_reference_admissible(geom,direction,valide)`
est utilisé par les repères de digues et les sections AH. Le cours d’eau doit
avoir `direction = TRUE` **et** `valide = TRUE`, une seule partie linéaire simple,
ouverte, valide, 2D et de longueur positive en EPSG:3950. Les fractions doivent
respecter `0 <= début < fin <= 1`. Aucune orientation n’est inférée ou corrigée.
DEMO-AH-01 conserve 57 directions non vérifiées. Le **Ruisseau du Pré Neuf** est
qualifié selon une convention fictive explicitement validée : l'ordre actuel
des sommets définit l'amont vers l'aval du scénario, sans observation de terrain.
Ses UUID et sommets sont inchangés. Une intersection complète avec le stockage
du **RC du Pré des Saules** est explicitement acceptée dans `ah_sections`.

La convention porte exclusivement sur le cours d'eau
`90368380-5d42-4a28-9889-6ae657f84a75`, depuis EPSG:3950
(1692727.2447354454, 9233907.130167473) vers
(1692361.6105395271, 9235579.986351149). Les codes de provenance fictifs existants
ne sont pas des preuves d'orientation. Ne pas étendre cette qualification aux
autres rivières. Le Courant des Saules reste non qualifié ; le référencement
manuel ne fournit aucune preuve de son orientation.

La couche `ah_sections` de `gpkg/ah.gpkg` conserve la décision acceptée, ses fractions de référence,
sa géométrie et la signature hydrographique. `generer_ah_sections.py` régénère
`12_ah_sections.sql` depuis cette couche. L'import restaure les fractions acceptées,
fait calculer la géométrie côté serveur et exige la signature et le WKB identiques ; il refuse des sources
modifiées. Sa réexécution est sans doublon ni modification de la traçabilité.
Pour accepter initialement une décision dans un PostGIS jetable local qualifié,
`generer_ah_sections.py --accept-local PORT` remplit cette couche seulement si
elle est absente ou vide, en conservant les autres couches du GeoPackage AH ;
ce mode ne qualifie aucun cours d'eau.

Parcours de contrôle : rapport parent RC du Pré des Saules, **11 prestations**
(10 directes et l'élagage des boisements de rive gauche indirect, quantité
déclarée 96 m²). Rapport stockage : 8 directes. Rapport Remblai1 : 1 directe
(et une autre sur Remblai2).
Rapport Ruisseau du Pré Neuf : 1 prestation, conservant sa FK rivière et sa
géométrie propre. Rapport global : 100 UUID distincts.

Contrôles reproductibles sur PostGIS jetable :
`/usr/bin/python3 plugin/tests/test_demo_import.py` pour l'installation neuve
et les générateurs ; `QT_QPA_PLATFORM=offscreen DEMO_AH_PDFS=1 /usr/bin/python3
plugin/tests/test_demo_ah_reports.py` pour les appartenances, les cartes et les
six PDF de contrôle dans `audits/demo_ah_01/`. Ces tests ne se connectent pas à
Supabase et ne modifient aucun GeoPackage source.

Pour obtenir des **propositions sans écriture**, utiliser
`SELECT * FROM milieux.ah_sections_candidates(:ah_id)`. L’intersection de
l’unique stockage facultatif avec les cours d’eau admissibles produit des
fractions calculées par le serveur ; les parties disjointes restent séparées,
les contacts ponctuels sont exclus. Sans stockage, aucune proposition spatiale
n’est retournée. Cela n'empêche pas de créer une section manuelle.

Une décision explicite s’enregistre par
`INSERT INTO milieux.ah_sections(ah_id,cours_eau_id,debut_fraction,fin_fraction)
VALUES (:ah,:cours_eau,:debut,:fin)`. Le serveur calcule la sous-ligne avec
`ST_LineSubstring`, en respectant `0 <= début < fin <= 1`,
l'empreinte MD5 de l'EWKB du cours d'eau, l’auteur
(`session_user`) et la date de validation. Une proposition seule ne crée jamais
de référence acceptée.

`ah_sections_carte` expose l’instantané et `etat_reference` : `CONFORME`,
`COURS_EAU_NON_QUALIFIE` ou `REFERENTIEL_MODIFIE` (prioritaire si l’EWKB a changé).
Une modification du cours d’eau ne réécrit aucune section. L’empreinte tient
compte de l’ordre et de la densité des sommets, pas seulement de l’égalité
topologique. Un changement ou une suppression du stockage n'a aucun effet sur
la conformité de la section. Aucune signature du stockage n'est enregistrée.

Après examen métier, revalider explicitement par
`UPDATE milieux.ah_sections SET revision_validation=revision_validation+1
WHERE id=:section`, avec les fractions manuelles examinées. Les changements
de parent, de cours d’eau ou de fractions exigent ce même incrément. Les simples
commentaires ne recalculent pas la référence. La révision et les dates/auteurs
conservent la trace de la dernière validation et modification ; il n’y a pas de
table d’historique des anciennes validations.

Toutes ces fonctions utilisent les droits de l’appelant. Lire la vue exige
`SELECT` sur elle et sur ses tables sources. Valider exige les droits d’écriture
sur `ah_sections`, `SELECT` et un droit `UPDATE` sur au moins une colonne de
`cours_eau`, nécessaire au verrou `FOR SHARE` conservé jusqu’à la fin de la
transaction. Aucun droit sur les cours d’eau n’est accordé automatiquement.
Les opérations respectent commit/rollback ; le code ne valide aucune transaction
du client. Aucun rôle applicatif ni accès public supplémentaire n’est créé.

Le référencement ne change pas les six modes directs antérieurs ni LOC-03 ;
le modèle courant en possède sept, dont le rattachement direct à une section AH.
Les rapports des parents AH utilisent uniquement les sections conformes
sur cours d’eau qualifié et l’intersection exacte avec la géométrie propre de la
prestation directement rattachée à ce cours d’eau. Les rapports enfants restent directs.

Le projet QGIS courant charge les sections acceptées et leur vue cartographique.
Dans la fiche native d’un AH, le bloc **Sections hydrographiques** propose la
consultation relationnelle, le zoom et la recherche de propositions. Le bouton
Tableau du `Relation Editor` affiche leurs colonnes. Les actions d’acceptation,
de modification et de revalidation sont fournies par le plugin **0.7.19**,
sans macro. Voir [le parcours utilisateur](../plugin/README.md#sections-hydrographiques-ah-0719).
Les propositions restent temporaires jusqu’à confirmation explicite ; les
57 cours d’eau non qualifiés de Supabase n’en produisent aucune admissible
(constat du 20 novembre 2026 ; une rivière est qualifiée).

Tests reproductibles sur un PostGIS jetable :
`/usr/bin/python3 plugin/tests/test_ah_sections.py`.

### Qualification des cours d’eau

Qualification HYDRO-QUAL-01 : `direction` est une validation humaine nullable
(TRUE : amont → aval vérifié, FALSE : sens contraire vérifié, NULL : non vérifié).
`section` compte les parties ; `valide` vaut uniquement `direction IS TRUE AND
section = 1`. Les multiparties restent éditables. La qualification ne garantit
ni la simplicité ni la validité topologique requises séparément par les digues.

PostgreSQL 16 utilise deux colonnes générées stockées ; l’expression de `valide`
répète `ST_NumGeometries`, une colonne générée ne pouvant en référencer une autre.
Un trigger BEFORE UPDATE invalide la direction si `ST_AsEWKB` change. Cette
comparaison conserve l’ordre des sommets et le SRID, contrairement à une égalité
topologique qui masquerait notamment une inversion du sens.

Les GPKG utilisent des triggers SQLite persistants installés par
`../model/qualifier_cours_eau_gpkg.py fichier.gpkg --backup audits/sauvegarde.gpkg`.
Ils décodent l’en-tête GeoPackage et le nombre de parties du WKB linéaire avec
les seules fonctions SQLite standard, sans fonction spatiale ajoutée. Les
triggers RTree existants nécessitent toujours les fonctions fournies par QGIS/GDAL.
Les WKB ISO LineString/MultiLineString XY/Z/M sont pris en charge. La comparaison
ignore l’enveloppe GeoPackage et vérifie le WKB et le SRID ; une sérialisation
externe différente du WKB peut invalider prudemment une direction même lorsque
les coordonnées sont équivalentes. Les réécritures identiques par QGIS sont testées.
Le script sauvegarde le fichier, préserve les validations et renomme `sections`
en `section` ; une réapplication conserve les qualifications. Un NULL explicite
dans `valide` est remplacé par le défaut 0 avant le calcul AFTER, grâce à la
politique NOT NULL ON CONFLICT REPLACE (elle ne remplace aucune entité).
Ne jamais utiliser les GPKG
CABBALR pour générer les imports fictifs. Les sauvegardes restent hors Git.

- `../model/schema.sql` : création d'une base PostgreSQL/PostGIS neuve dans le schéma métier `milieux`.
- `../model/schema.mmd` : diagramme relationnel correspondant au schéma SQL.
- Les fichiers SQL numérotés jusqu'à `data/15_prestations.sql` et `data/digues.sql` : imports fictifs dans l'ordre de `importer_base_neuve.sh`.
- `data/generer_cours_eau.py` : reconstruit les imports SQL hydrographiques depuis `gpkg/cours_eau.gpkg`, source fictive unique.
- `data/generer_digues.py` : réexporte `data/digues.sql` depuis `gpkg/digues.gpkg`, sans recalculer les géométries synchronisées depuis QGIS.
- `data/generer_prestations.py` : réexporte les 100 prestations courantes du GeoPackage vers le SQL, sans recalculer leurs géométries ni modifier leurs attributs.
- `data/auditer_prestations_spatial.py` : audite en lecture seule les distances aux patrimoines et les concentrations spatiales ; la connexion est fournie par les variables libpq `PG*` et les livrables sont écrits dans `audits/`.
- `data/importer_base_neuve.sh` : exécution du schéma puis des imports conservés avec `psql`.
- `gpkg/ah.gpkg` et `gpkg/sites_terrestres.gpkg` contiennent 10 AH, 13 ouvrages, 12 sites MultiPolygon et 25 zones fictives (17 MultiPolygon, 4 MultiPoint et 4 MultiLineString). Les ouvrages sont des segments déterministes des contours de stockage, sans valeur de terrain.
- `data/generer_sites.py` réexporte les sites et zones dans `data/10_sites_terrestres.sql` à partir de leur GeoPackage.
- `gpkg/cours_eau.gpkg` : 58 cours d’eau fictifs (53 monosections, cinq multiparties), une direction TRUE par convention fictive DEMO-AH-01, 57 directions NULL.
- `gpkg/ah.gpkg`, couche `ah_sections` : une référence hydrographique acceptée pour RC du Pré des Saules, calculée par le serveur.
- `gpkg/digues.gpkg` : couche spatiale fictive `digues`, trois repères rattachés chacun à une digue.
- `gpkg/prestations.gpkg` : 100 prestations fictives, réparties sur les six types géométriques autorisés.

Le jeu conserve une répartition déterministe des photographies de `photos/` :
25 prestations utilisent les cinq JPEG locaux,
25 utilisent chacune une ou deux des 40 références de `photos/photos_serveur.csv`,
et 50 ne portent aucune photographie dans les sources reproductibles. Les quatre
champs photo sont identiques dans le SQL et le GeoPackage. Les références locales
ont la forme portable `photos/nom.jpg` et sont résolues depuis le dossier de
`prestations_demo.qgz`. Les références distantes `J:\\` sont conservées telles
quelles et nécessitent le lecteur réseau concerné ; elles ne désignent aucun
des cinq fichiers de démonstration locaux.

Les champs décimaux `prestations.quantite`, `ah_stockage.surface_ha` et
`sites_zones.surface_ha` sont stockés en texte dans les GeoPackages : le type
GeoPackage `REAL` arrondit les valeurs décimales de haute précision. Lors d'un
import, convertir explicitement ces textes en `NUMERIC` après validation de leur
syntaxe. Le champ `prestations.statut` contient un code ; résoudre
`statut_id` par `statuts_prestations.code` et refuser tout code inconnu.
Les six FK patrimoniales sont présentes dans le GeoPackage des prestations.
Le référentiel des statuts et ses quatre UUID canoniques sont initialisés par
`model/schema.sql` ; les imports résolvent les codes sans recréer ces lignes.
Les colonnes de traçabilité sont renseignées
par les triggers PostgreSQL. Pour un chargement intermédiaire avec `ogr2ogr`,
utiliser `-unsetDefault` afin de ne pas recopier le défaut SQLite entier `0`
des booléens dans une colonne PostgreSQL. Pour `cours_eau`, omettre `section`
et `valide` des INSERT/UPDATE PostgreSQL : ces colonnes sont générées.
Le fichier SQL 15 conserve explicitement les 100 rattachements fictifs du
modèle actuel au moyen des six clés étrangères directes.

Les 10 stockages et les 12 zones polygonales historiques conservent leurs UUID. Les 13 nouvelles zones ont des UUID déterministes. Chaque parent fictif conserve son UUID. Le modèle autorise zéro ou un stockage et zéro à plusieurs ouvrages par AH ; les données fictives actuelles ont un stockage par parent et trois AH ont deux ouvrages. Les zones polygonales sont des sous-emprises localisées à l'intérieur des sites, avec cinq sites possédant deux polygones distincts.

Un site terrestre peut posséder zéro à plusieurs zones. Chaque zone doit
référencer exactement un site existant par `site_terrestre_id NOT NULL`.
La FK `ON DELETE RESTRICT` interdit de supprimer un site tant qu'une zone le
référence ; un site sans zone est valide. Aucune contenance géométrique n'est
imposée par cette relation.
La table `ah` n'a pas de géométrie : pour le contrôle topologique du jeu fictif,
l'emprise de chaque AH est celle de son stockage unique. Les emprises AH et
sites terrestres ne se chevauchent plus en surface ; les ouvrages suivent les
limites de leur stockage. Les prestations conservent leurs géométries et liens.

Le schéma et les imports détectent automatiquement le schéma d'installation de l'extension PostGIS. La même version fonctionne donc avec PostGIS dans `public`, `extensions` (Supabase) ou un autre schéma, sans variante concurrente.

## Installation neuve

1. Installer l'extension PostGIS dans la base cible, dans le schéma souhaité.
2. Depuis `demo/`, exécuter `bash data/importer_base_neuve.sh [nom_base]`. Le fichier `15_prestations.sql` contient les prestations et leurs six FK patrimoniales.
3. Vérifier les effectifs et les contraintes avant de configurer les relations QGIS.

Le script de création est réservé à une base neuve et s'arrête à la première erreur. Les prestations d'entretien végétal restent présentes comme types de prestations ; aucune association patrimoniale de remplacement n'est déduite.

## Rattachements, géométrie et reconstruction

Chaque prestation choisit exactement un mode : cours d'eau, digue, stockage,
ouvrage, site terrestre parent ou une zone terrestre enfant (six FK nullables dans prestations). Le site parent
et ses zones ne peuvent pas être rattachés simultanément.

La géométrie propre est obligatoire pour cours d'eau, digue et site parent.
Pour un site parent, elle est enregistrée en MultiPoint, MultiLineString ou
MultiPolygon, y compris si elle comporte une seule partie.
Elle est recommandée mais facultative pour les AH ; elle est interdite pour les
zones enfants. Les prestations sur zone conservent `geom = NULL` ; la vue
`milieux.prestations_carte` utilise directement `sites_zones.geom`, sans copie.
Les trois couches de prestations du projet lisent cette vue cartographique,
en lecture seule. L'édition métier reste effectuée par le plugin sur la table
`prestations`. Les mesures de `prestations_fiches` portent sur toute la géométrie
propre. Les filtres communaux utilisent la géométrie cartographique effective.
Les prestations sur zone conservent leur quantité et leur unité déclarées.

Position et rive restent déclaratives, applicables uniquement aux cours d'eau,
digues et ouvrages ; leurs défauts sont Indéfini et Indéfinie.

La source SQL 15 installe les prestations et leurs rattachements
dans une transaction. generer_prestations.py réexporte les 100 objets du
GeoPackage courant, sans translation, copie de géométrie ou recalage historique.
Les coordonnées modifiées manuellement restent donc conservées.

Les 100 prestations conservent leurs UUID, attributs et rattachements. Les 12
prestations sur zone n'ont aucune géométrie propre ; celles des autres modes
restent conservées. Leurs 100 rattachements sont
répartis en 62 cours d'eau, 1 digue, 13 stockages, 6 ouvrages, 6 sites parents et
12 zones. Les sept FK figurent dans `15_prestations.sql` ; celle des sections AH
reste `NULL` pour ces 100 prestations initiales.

## Politique de consolidation des données fictives

Supabase est la référence pour les modifications manuelles apportées au jeu de
démonstration. Après une modification validée, les GeoPackages et les imports
SQL canoniques du dépôt sont resynchronisés afin qu'une installation neuve
reproduise directement l'état courant, sans rejouer une chaîne de migrations.

Les scripts génériques d'import, d'export et d'audit sont conservés lorsqu'ils
rendent un service permanent. Les migrations et correctifs ponctuels sont
supprimés après application et validation de leur résultat dans les sources
canoniques. L'historique Git suffit à retrouver ces opérations passées.

## Traçabilité

Chaque table métier conserve automatiquement `modifie_par` (compte PostgreSQL `session_user`) et `date_modification`. Chaque prestation porte un `technicien_id` obligatoire, indépendant du compte auteur.


## Digues dans QGIS (DIG-02)

La création d’un repère ou un changement de rivière/fractions exige le même
contrôle de qualification que les sections AH. Les changements attributaires
sans recalcul (par exemple rive ou nom) restent possibles pour un repère existant.
La vue conserve sa géométrie figée et expose `COURS_EAU_NON_QUALIFIE` si sa
signature est inchangée mais que son support n’est pas admissible. Si l’EWKB
diffère, `REFERENTIEL_MODIFIE` reste prioritaire. Aucun tracé n’est inversé.

Les trois repères fictifs existants sont conservés sur des supports non vérifiés.
`gpkg/digues.gpkg` conserve leur géométrie et leur `geom_riviere_signature` acceptées.
`generer_digues.py` exporte ces instantanés sans recalculer leur signature ou leur
forme depuis le cours d’eau actuel. L’import SQL administratif exige des tables
vides et les droits du propriétaire : dans une transaction verrouillée, il suspend
uniquement `digues_reperes_prepare_trg`, restaure les trois instantanés, exécute
les contraintes différées, puis réactive ce trigger avant commit. Les CHECK, FK,
contraintes de complétude des digues et triggers de traçabilité restent actifs.
Une erreur annule toute la restauration, y compris la suspension du trigger.
Ce chemin de reconstruction ne sert jamais à créer ou modifier un repère métier ;
aucun mode de contournement n’est ajouté au serveur. La seule qualification
fictive DEMO-AH-01 ne concerne aucun des trois supports des digues existantes.

Le projet `prestations_demo.qgz` contient la vue de consultation
`milieux.digues_carte` au-dessus des cours d'eau. La couche est en
lecture seule et sa visibilité se commande dans le groupe **Milieux**. Elle est disponible après une installation neuve de la base.

La rivière conserve son style bleu. Les sections en rive gauche sont vertes
et décalées de **−1,6 mm** ; celles en rive droite sont orange et décalées de
**+1,6 mm**. Une référence devenue différente du tracé actuel ou portée par un cours d’eau
non qualifié reçoit en plus un trait rouge discontinu. Le symbole apparaît jusqu'à l'échelle
1:75 000 et le nom de la digue est étiqueté aux échelles de détail jusqu'à
1:25 000. La table attributaire montre par défaut la digue, la rivière, la
rive et l'état du référencement.

Le décalage est **uniquement graphique** : les sections restent des portions
de l'axe de la rivière, pas les géométries physiques des ouvrages. Les rives
G/D sont relatives au sens de numérisation. Avant une lecture hydraulique des
rives, vérifier que chaque rivière suit bien le sens amont → aval. La capture
`images/dig02_sections_rives.png` utilise une rivière et deux sections
fictives, posées sur le même intervalle.
