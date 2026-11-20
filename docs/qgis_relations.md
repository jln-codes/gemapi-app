# Relations du projet QGIS

## État PERF-QGIS-09C au 18 novembre 2026

Le retrait de `prestations_fiches` **n'est pas intégré**. Les projets officiels
conservent 26 couches (25 PostgreSQL + OSM) et 66 relations. La vue SQL demeure
présente ; ce chantier ne modifie ni le schéma, ni les droits, ni les données
Supabase.
Les vérifications en lecture seule confirment que les transitions HYDRO ont
bien été appliquées sur Démo et CABBALR : septième rattachement disponible,
noms obligatoires, 58 et 170 cours d'eau respectivement, aucun anonyme.

L'audit sur copies identifie 12 relations utilisant `prestations_fiches` et
propose de remplacer leurs navigations par le gestionnaire existant, préfiltré
sur les UUID métier. Les candidats ont 25 couches et 54 relations, sans modifier
les trois représentations de `prestations_carte`. Leurs actions vérifient la
couche, la table, l'UUID et la connexion du projet courant ; elles ne sont pas
déployées dans les QGZ officiels.

La qualification native Linux reste incomplète : après des ouvertures successives
de formulaires, une consultation polygonale attend sur le sémaphore du pool
PostgreSQL. La part du pilote et celle du comportement natif restent à départager.
Le premier plantage du formulaire AH était, lui, un défaut identifié du pilote :
son contexte omettait `QgsVectorLayerTools` ; le projet de référence fonctionne
avec le contexte correct. Ces observations ne démontrent pas une régression
causée par le retrait. Elles empêchent de déclarer les copies entièrement validées.
Aucun gain de chargement avant/après n'est donc revendiqué.

Le rapport, la matrice des 12 relations, les copies, le prototype non publié et
les traces restent locaux sous `audits/PERF-QGIS-09C/`. Avant intégration, terminer
les consultations natives des trois cartes dans un pilote Desktop maîtrisé,
rejouer la navigation patrimoniale et le cycle d'écriture jetable, puis seulement
mesurer quelques paires avant/après. La qualification multiversion reste distincte.

Le correctif préalable de capture est publié séparément en **0.7.32** : l'outil
est invalidé et désactivé avant nettoyage, ses événements tardifs deviennent
inertes, ses signaux sont déconnectés et l'outil précédent est restauré. Les
annulations et le déchargement répétés sont idempotents. Aucun tracé automatique
ni changement de disposition du formulaire n'est inclus.

## Connexions et comptes

Le modèle est identique pour les projets Supabase `sig-milieux-demo`
(données fictives) et `cabbalr` (données réelles). Ouvrir le fichier QGIS de
l'environnement souhaité :

| Projet QGIS | Base Supabase |
| --- | --- |
| `demo/prestations_demo.qgz` | `sig-milieux-demo` |
| `cabbalr/prestations_cabbalr.qgz` | `cabbalr` |

Chaque projet contient les mêmes identifiants de couches, 25 couches
PostgreSQL, le fond OSM et 66 relations. Les connexions et les emprises
géographiques restent propres à chaque environnement. Le plugin utilise les connexions du projet ouvert ;
ses caches sont invalidés lors du chargement d'un autre projet. Les actions
des sections AH utilisent l'identifiant de la couche courante. Ne pas charger
simultanément les deux bases dans le même projet.

Les 25 couches PostgreSQL de chaque projet utilisent une chaîne de connexion
uniforme avec l'hôte, le port, la base et TLS `require` dans le `.qgz`, sans
mot de passe. CABBALR peut être transmis seul et ouvert sur un profil vierge.
L'invite native PostgreSQL permet de saisir les identifiants communiqués
séparément. Le projet CABBALR laisse le nom du compte vide. Saisir le nom
complet Lecture, Prestations ou Patrimoine indiqué dans le registre des accès.
Les 25 couches et le plugin utilisent ce même compte pendant la session.

Les trois connexions locales facultatives **CABBALR - Lecture**, **CABBALR - Prestations**
et **CABBALR - Patrimoine** utilisent une connexion directe, TLS `require`, leur nom
complet et aucun mot de passe enregistré. Les anciennes entrées CABBALR des services,
de `.pgpass` et du trousseau ont été supprimées. Les mots de passe se consultent dans
le seul fichier privé `CABBALR_IDENTIFIANTS.local.txt` à la racine, ignoré par Git.
Le projet autonome utilise aussi `require` sans certificat local obligatoire.

Le [registre CABBALR_ACCES.md](../CABBALR_ACCES.md) décrit les droits,
les chemins exacts, les commandes `psql`, la configuration QGIS et le transfert
vers Windows. Il constitue la référence des accès CABBALR.

Le projet CABBALR ne référence aucun service local. Le choix du compte
dans l'invite native est conservé pour la session. Fermer complètement QGIS
avant de rouvrir le même projet avec un autre rôle.
Choisir une connexion dans l'Explorateur ne remplace pas les sources des couches
chargées. La Démo utilise désormais aussi `require` sur ses deux vues consolidées.

L'emprise initiale, le SCR et l'échelle restent ceux de la Démo. Pour voir
l'ensemble des données réelles après ouverture, utiliser **Zoomer sur la
couche** sur les communes ou les cours d'eau. La génération ne recentre pas
silencieusement le projet CABBALR.

## Consultation des prestations et édition via le plugin

Les projets ne chargent plus la couche QGIS non spatiale `prestations` qui
pointait vers `milieux.prestations`. La table PostgreSQL, ses droits et ses
triggers restent inchangés. L'édition native depuis cette ancienne couche
n'est plus proposée dans le panneau QGIS : la création et la modification
passent par le plugin, qui accède directement à la table SQL selon les droits
du compte connecté. Les projets conservent 25 fournisseurs PostgreSQL et
66 relations QGIS. La couche technique cachée des libellés de zones est
conservée à ce stade.

Les trois couches de `milieux.prestations_carte` représentent les prestations
par famille géométrique : points, lignes et polygones. Elles restent
identifiables et sélectionnables. Chacune possède l'action native
**Modifier cette prestation**, qui transmet `prestations_carte.id` (UUID métier)
au formulaire de modification du plugin. L'action vérifie la couche, la connexion
du projet, l'UUID et les droits PostgreSQL effectifs. Sous le profil Lecture,
elle refuse l'édition ; la consultation reste disponible dans le formulaire
QGIS natif et dans le gestionnaire du plugin. Une zone fournit toujours sa géométrie ;
pour un stockage ou un ouvrage AH, la géométrie propre facultative de la
prestation reste prioritaire, puis la vue utilise celle de l'enfant AH si
elle est NULL. Les cours d'eau, digues et sites terrestres conservent leur
géométrie propre obligatoire. La vue ne copie aucune géométrie dans
`prestations.geom` et ne modifie pas la quantité déclarée. Une prestation
sans représentation reste accessible dans le gestionnaire et dans
`prestations_fiches`, mais n'a pas de symbole sur la carte.

La vue non spatiale `prestations_fiches` reste la consultation native
détaillée. Elle présente les libellés des références, les rattachements,
les photographies, les attributs métier et les huit mesures MESURES-07.
Ses relations permettent toujours de naviguer depuis les sites, zones,
AH et digues. Les trois cartes présentent aussi les huit mesures dans
leurs formulaires. Le formulaire du plugin ne possède pas encore un panneau
dédié à ces huit valeurs ; la table `prestations_fiches` est le parcours de
consultation complet, y compris pour une prestation non cartographiable.

Les huit mesures sont `nombre_points`, `longueur_m`, `surface_m2`,
`surface_ha`, `type_geometrie`, `type_geometrie_postgis`,
`possede_geometrie` et `origine_mesures`. Elles proviennent des
valeurs stockées dans `milieux.prestations` et restent en lecture seule
dans les vues. `prestations_carte` les expose en fin de vue ;
`prestations_fiches` conserve les positions de ses six champs existants
et ajoute `nombre_points` et `origine_mesures` à la fin. Aucun
recalcul de longueur ou de surface n'est effectué par ces vues. Les
mesures peuvent provenir de la géométrie propre ou du patrimoine de
rattachement ; `origine_mesures` précise cette provenance. La quantité
déclarée décrit les travaux et reste distincte des dimensions géométriques.
Après une modification, sauvegarder puis recharger la fiche pour consulter
les valeurs enregistrées actualisées.

Le gestionnaire du plugin interroge directement `milieux.prestations` et reste
ouvert aux trois profils. Il affiche **Consulter** sous Lecture et **Modifier**
avec le droit `UPDATE`. **Nouvelle prestation** dépend du droit `INSERT` et
**Supprimer** du droit `DELETE`, évalués sur la connexion PostgreSQL courante.
La suppression requiert une confirmation explicite comprenant le libellé et
l'UUID. Le plugin compare `xmin` à la version obtenue lors de la recherche,
verrouille la ligne et exige exactement une suppression ; une modification
concurrente ou une prestation déjà supprimée provoque un refus. La suppression
ne retire ni les patrimoines, ni les référentiels, ni les fichiers de photos.
Les trois couches cartographiques sont rechargées après succès. L'édition
directe des vues QGIS reste désactivée et `prestations_fiches` reste chargée.

Le cours d'eau conserve son champ natif QGIS `libelle_cours_eau`, dont
l'expression est désormais simplement `"nom"`. Le nom métier est obligatoire
et non blanc dans le schéma courant ; les UUID restent les clés de rattachement.
Le plugin lit ses catalogues indépendamment du filtre de représentation QGIS.
Les widgets et éditeurs relationnels des
couches et fiches conservées restent configurés avec leurs identifiants
QGIS existants. Le synchroniseur refuse toute différence de liste de
couches entre les deux projets ; il ne réintroduit donc pas la couche
retirée à partir d'un projet conforme.

## Synchroniser les deux projets

Choisir explicitement le projet dont la configuration doit faire référence.
La commande sans sens n'est plus autorisée ; une comparaison seule est le
mode par défaut. Enregistrer les modifications à conserver puis fermer la
destination dans QGIS avant toute écriture : une fenêtre restée ouverte peut
réenregistrer son ancienne configuration par-dessus le fichier synchronisé.

Exemple **CABBALR → Démo**, depuis la racine avec le Python de QGIS :

```sh
/usr/bin/python3 cabbalr/scripts/synchroniser_projet_qgis.py --sens cabbalr-vers-demo --simuler
/usr/bin/python3 cabbalr/scripts/synchroniser_projet_qgis.py --sens cabbalr-vers-demo --appliquer
/usr/bin/python3 cabbalr/scripts/synchroniser_projet_qgis.py --sens cabbalr-vers-demo --verifier
```

Pour **Démo → CABBALR**, remplacer le sens par `demo-vers-cabbalr`.
L'écriture exige toujours `--appliquer` ; ni la comparaison, ni
`--simuler`, ni `--verifier` ne modifient les projets. Le bilan structuré
distingue styles, étiquettes, formulaires, actions, ordre/légende,
propriétés du projet, connexions et emprises. `--rapport chemin.json`
permet de le conserver explicitement.

Avant écriture, la destination est sauvegardée dans
`audits/synchronisation_qgis/<projet>-<empreinte>.qgz`.
`--sauvegardes chemin` permet de choisir un autre emplacement local.
La sauvegarde est vérifiée par SHA-256. Une modification de la source ou de
la destination depuis la comparaison annule l'opération. Le remplacement
final est atomique ; une erreur avant ce remplacement laisse la destination
intacte. Les sauvegardes locales restent hors Git.

Le script reporte la configuration graphique et fonctionnelle de la source :
noms et ordre des couches, styles, symboles, étiquettes, légendes, formulaires,
widgets, contraintes QGIS, actions, relations et mise en page. Il conserve
dans la destination :

- Les sources de couches, dont les URI PostgreSQL complètes, leurs utilisateurs, modes TLS et éventuels
  identifiants d'authentification QGIS. Il ne change jamais de compte.
- Les emprises du canevas et de la vue par défaut, les emprises des couches
  et métadonnées spatiales, le SCR et le cadrage des cartes de mise en page.
- Le titre et l'identité du projet, les chemins locaux, signets, annotations,
  vues supplémentaires et métadonnées propres à l'environnement.

Les copies d'URI dans l'arbre, les relations, widgets et paramètres GPS sont
appariées aux couches de destination par leurs identifiants stables.
Aucune connexion SQL n'est exécutée par le script. Les ressources de styles
embarquées sont conservées dans l'archive ; aucune donnée Supabase n'est copiée.

Un changement d'identifiants de couches/relations, de table, géométrie ou
filtre SQL, une URI non appariée ou une ressource embarquée inattendue provoque
un refus explicite. Les ajouts/suppressions de cartes de mise en page exigent
également de définir leur cadrage cible au préalable. Le script ne constitue
pas un outil de fusion automatique de développements parallèles : examiner
la comparaison et choisir la source avant de demander l'écriture.

Rouvrir ensuite la destination dans QGIS. Pour revenir à l'état précédent,
fermer le projet, recopier la sauvegarde sur son fichier de destination puis
le rouvrir. Ne pas réenregistrer par-dessus depuis une ancienne fenêtre
restée ouverte.

Sous Windows, utiliser `python` dans l'environnement livré avec QGIS
(par exemple le shell OSGeo4W). Les tests Linux ne remplacent pas une recette
Windows. Les tests du script se lancent avec
`/usr/bin/python3 plugin/tests/test_qgis_project_sync.py`.

Le portage CABBALR → Démo a été contrôlé sous QGIS Desktop 3.44.15 Linux :
24 couches PostgreSQL et 62 relations valides dans chaque projet, nouvelles
symbologies présentes, formulaires natifs consultables et plugin affichant
100 prestations en Démo, 0 dans CABBALR puis 100 après retour Démo. Les
sources, l'authentification et les emprises de destination sont conservées ;
le projet source n'a pas été modifié. Les 15 tests du script passent.

Le projet `demo/prestations_demo.qgz` contient 62 relations. Leur nom suit la direction du champ référençant vers l'objet référencé : `Source → Cible` lorsqu'une contrainte FK existe dans PostgreSQL, `[QGIS] Source → Cible` lorsqu'il s'agit d'une relation propre au projet, notamment vers une vue. Les noms métier sont courts et les représentations `(points)`, `(lignes)`, `(polygones)`, `(fiches)` et `(référence)` sont précisées. `Vue` distingue les consolidations de parents ; `Liaison` est réservé aux véritables objets intermédiaires.

## Décider de créer ou conserver une relation

Le projet applique désormais **l'ensemble exhaustif** : toutes les combinaisons de FK PostgreSQL découvrables entre les couches chargées sont enregistrées, auxquelles s'ajoutent les relations `[QGIS]` nécessaires aux vues et aux formulaires. Vérifier la couche et les champs, puis documenter l'identifiant interne stable.

Les relations comprennent les références des prestations vers les patrimoines dans les formulaires, les relations des enfants AH et des zones vers leurs parents, les éditeurs 1:N depuis les patrimoines, les trois parcours `prestations_fiches.site_zone_id → sites_zones.id`, les deux paires des vues consolidées `prestations__ah` et `prestations__sites_terrestres`, ainsi que les relations de navigation issues de toutes les FK découvrables.

La table `prestations__sites_zones` et ses anciennes relations N:N ont été retirées lors de `MODEL-RATTACHEMENTS-03`. Dix relations ont ensuite été intégrées : neuf croisements de `site_zone_id` avec les couches géométriques de zones et la relation de la couche de référence des zones vers son site parent. Les quatre relations vers cette couche de référence étaient déjà enregistrées.

À l'ajout d'une couche, lancer « Découvrir les relations », comparer chaque proposition aux relations existantes par **identifiants de couches et couples de champs**, puis importer toutes les combinaisons de FK réellement nouvelles. Ne jamais assimiler l'absence d'un nom identique à une relation nouvelle ; une même FK SQL peut correspondre à plusieurs instances QGIS. Renommer les nouvelles relations selon la convention et consigner ici les relations `[QGIS]` ajoutées manuellement. Répéter cette vérification après chaque ajout ou retrait de couche.

## Découvrir et nommer une relation

Pour vérifier une FK, interroger `pg_constraint` (`contype = 'f'`) et rapprocher `conrelid`, `confrelid`, `conkey` et `confkey` des tables et champs réels. Ne pas se fier au seul nom historique `_fkey`. Dans QGIS, choisir les couches référençante et référencée, les champs correspondants, puis donner un nom français suivant la règle ci-dessus. Si la couche source est une vue sans contrainte FK déclarée, ajouter `[QGIS]`.

Les relations `[QGIS]` actuelles se reconstruisent avec les champs suivants. La cardinalité indiquée est celle de la navigation QGIS ; les vues consolidées sont en lecture seule.

| Identifiant | Couche référençante.champ → couche référencée.champ | Fonction |
|---|---|---|
| `prestation_ah_id_ah_fbc320e_id` | `prestations__ah.ah_id → ah.id` | Vue AH, premier côté du parcours parent–prestations |
| `prestation_prestation_id_prestation_id_1` | `prestations__ah.prestation_id → prestations_fiches.id` | Vue AH, second côté du parcours N:N de consultation |
| `prestation_site_terrestre_id_sites_terr_id` | `prestations__sites_terrestres.site_terrestre_id → sites_terrestres.id` | Vue sites, premier côté |
| `prestation_prestation_id_prestation_id` | `prestations__sites_terrestres.prestation_id → prestations_fiches.id` | Vue sites, second côté |
| `prestation_ah_ouvrage_id_ah_ouvrage_id` | `prestations_fiches.ah_ouvrage_id → ah_ouvrage.id` | Éditeur 1:N des ouvrages et référence des fiches |
| `prestation_ah_stockage_id_ah_stockag_id` | `prestations_fiches.ah_stockage_id → ah_stockage.id` | Éditeur 1:N des stockages et référence des fiches |
| `prestation_cours_eau_id_cours_eau__id` | `prestations_fiches.cours_eau_id → cours_eau.id` | Éditeur 1:N des cours d'eau et référence des fiches |
| `prestation_digue_id_digues_3a5_id` | `prestations_fiches.digue_id → digues.id` | Éditeur 1:N des digues et référence des fiches |
| `prestation_site_terrestre_id_sites_terr_id_1` | `prestations_fiches.site_terrestre_id → sites_terrestres.id` | Référence du site parent dans les fiches |
| `model03_fiches_zone_reference` | `prestations_fiches.site_zone_id → Zones terrestres (référence).id` | Widget de référence commun aux trois géométries |
| `model03_fiches_zone_points` | `prestations_fiches.site_zone_id → sites_zones_points.id` | Éditeur 1:N des zones ponctuelles |
| `model03_fiches_zone_lignes` | `prestations_fiches.site_zone_id → sites_zones_lignes.id` | Éditeur 1:N des zones linéaires |
| `model03_fiches_zone_polygones` | `prestations_fiches.site_zone_id → sites_zones_polygones.id` | Éditeur 1:N des zones polygonales |

Avant de supprimer ou recréer une relation, rechercher son **identifiant interne** dans les `attributeEditorRelation`, les options `RelationReference`, les propriétés `nm-rel`, les expressions et les configurations de widgets. Le nom affiché peut changer ; l'identifiant utilisé par ces éléments doit rester stable. Sauvegarder le `.qgz`, essayer la modification sur une copie, puis vérifier les formulaires et les parcours concernés.

## Sections hydrographiques AH (HYDRO-AH-05)

Le projet charge `milieux.ah_sections` comme table non spatiale de consultation
et `milieux.ah_sections_carte` comme couche cartographique en lecture seule.
Les deux FK de la table et les deux navigations correspondantes de la vue
sont enregistrées, avec ces identifiants stables :

| Identifiant | Référençant → référencé | Usage |
|---|---|---|
| `ah05_sections_ah` | `ah_sections.ah_id → ah.id` | FK réelle du parent |
| `ah05_sections_cours_eau` | `ah_sections.cours_eau_id → cours_eau.id` | FK réelle du support |
| `ah05_carte_ah` | `ah_sections_carte.ah_id → ah.id` | Relation QGIS de consultation dans la fiche AH |
| `ah05_carte_cours_eau` | `ah_sections_carte.cours_eau_id → cours_eau.id` | Navigation QGIS du support |

Le `Relation Editor` de la fiche AH utilise la vue spatiale : état, fractions,
longueur figée, consultation et zoom natifs. Les boutons natifs de création,
liaison et suppression sont masqués sur cette vue. Des actions explicites du
plugin prennent en charge les propositions, leur acceptation et les révisions
serveur ; aucune macro ni initialisation Python de formulaire n'est utilisée.
L'action **Créer une section manuelle…** choisit un cours d'eau qualifié et ses
fractions ; la prévisualisation précède la confirmation explicite. Le stockage
ne contraint ni les limites ni la conformité des références hydrographiques.
Les autres relations et la disposition des six rattachements des prestations
restent identiques.

## HYDRO-ASSOC-01 — Septième rattachement direct

État du chantier : **schéma et plugin 0.7.30 préparés ; migration réelle non
appliquée**. Les bases Démo et CABBALR restent sur les six modes précédents.
Ne pas installer ce paquet sur ces bases avant leur transition autorisée.

### Contrat métier et PostgreSQL

Une prestation choisit exactement un des sept champs `cours_eau_id`, `digue_id`,
`ah_section_id`, `ah_stockage_id`, `ah_ouvrage_id`, `site_terrestre_id` et
`site_zone_id`. `ah_section_id` référence **`ah_sections.id`**, avec index et
`ON DELETE RESTRICT` ; ni l'AH parent, ni son stockage ou son ouvrage ne
remplacent cet identifiant. Supprimer une prestation conserve sa section.
Aucune prestation existante n'est réaffectée par cette évolution.

| Mode | Géométrie propre de l'intervention | Géométrie cartographique et mesures |
| --- | --- | --- |
| Cours d'eau, digue, section AH | Obligatoire, simple ou multiple, point/ligne/polygone | Géométrie propre |
| Site terrestre | Obligatoire, multiple | Géométrie propre |
| Stockage ou ouvrage AH | Facultative | Géométrie propre prioritaire, sinon celle de l'enfant |
| Zone terrestre | Interdite | Géométrie de la zone |

La référence longitudinale `ah_sections.geom_reference` sert à sélectionner le
support ; elle n'est jamais copiée automatiquement dans `prestations.geom`.
Les contraintes de validité, 2D et EPSG:3950 restent applicables. Position et rive
sont autorisées pour la section AH, comme pour cours d'eau/digue/ouvrage.
`prestations_direct_modes` empêche les combinaisons ; la validation différée
`assert_prestation_relations()` impose exactement un rattachement à la fin de
transaction.

Un trigger privé vérifie les nouvelles associations à une section et les
changements de géométrie : cours d'eau qualifié, signature actuelle, fractions
et géométrie de référence cohérentes. Il verrouille la section et le cours
d'eau en lecture partagée pendant la transaction. Son exécution en tant que
propriétaire permet ces verrous sans donner de droit d'édition du patrimoine
au profil Prestations. Une association ancienne devenue obsolète reste lisible
et peut recevoir une modification attributaire sans réaffectation ; elle est
signalée comme référence à revalider. Changer sa géométrie exige une référence
admissible.

Les huit mesures MESURES-07 restent enregistrées dans `prestations`. Le résolveur
conserve son contrat unique à sept arguments : la géométrie propre obligatoire
suffit au nouveau mode, sans nouveau repli sur toute la section. Le trigger
`mesures07_preparer()` inclut `ah_section_id` dans la détection des changements.
Une modification du patrimoine ne recalcule pas la mesure d'une intervention
sur section ayant sa géométrie propre. `prestations_carte` et
`prestations_fiches` exposent les huit valeurs stockées ; `ah_section_id` est
ajouté **à la fin** de chacune des deux vues. Les colonnes antérieures, leurs
types, les UUID et les règles de représentation restent inchangés.

`ah_sections` étant créée plus tard dans le schéma, la colonne est déclarée
avant les contraintes locales des prestations et sa FK est ajoutée seulement
après la création de sa table cible. Le schéma neuf ne dépend d'aucun script de
transition. `prestations__ah` reconnaît les sections enregistrées par jointure
sur leur UUID, avec une seule association prestation/parent.

### Résolution spatiale et sélecteur

`patrimony_spatial.candidate_query()` interroge PostgreSQL directement. La
proximité sélectionne des cours d'eau à examiner ; toutes leurs portions
prioritaires admissibles sont ensuite lues pour reconstruire le complément
libre. Les sections AH doivent être `CONFORME`, qualifiées, de signature
actuelle et égales à la sous-ligne définie par leurs fractions. Les repères de
digues sont soumis aux contrôles correspondants. Le filtre cartographique
CABBALR sur les cours d'eau nommés ne tronque plus le catalogue du formulaire :
une couche temporaire indépendante lit toujours le catalogue hydrographique,
y compris si le filtre cartographique change ensuite. Son regroupement métier
est distinct des options du gestionnaire dans `SessionData`, et les deux
sont invalidés ensemble lors d'une actualisation hydrographique. Le schéma courant
exige désormais des noms métier non blancs pour tous les cours d'eau.

`resolve_watercourse()` traite les identités `(famille, UUID)` au même niveau
pour digues et sections AH. Il construit les intervalles et leurs portions
libres, puis compare les distances sur un échantillonnage couvrant toute la
référence de recherche. La marge de deux rayons d'échantillonnage et la
tolérance de limite d'un mètre empêchent de masquer une possibilité entre deux
échantillons. Jusqu'à trois raffinements sont essayés ; au-delà de 5 000
échantillons ou si la projection ne peut être prouvée, le résultat reste
conservateur. Pour les points, une projection longitudinale complète aussi le
contrôle des distances, notamment près des limites et des méandres.

Une portion totalement couverte propose sa digue ou sa section ; une portion
libre propose son cours d'eau. Une ligne ou un polygone à cheval, deux sections
concurrentes, ou une digue et une section AH simultanément admissibles restent
signalés comme ambigus. **Aucune priorité digue/AH n'est inventée.** Le contrôle
avant enregistrement vérifie le support choisi, même si Distance est décoché,
et refuse une nouvelle attribution hydrographique ambiguë. Il faut préciser
ou subdiviser l'intervention ; le plugin ne découpe ni ne déplace sa géométrie.
Les rattachements historiques inchangés sont conservés et signalés lorsque la
résolution courante diverge.

Les libellés suivent `Cours d'eau (Patrimoine)` : `Clarence (CL5)`,
`La Lawe (ZEC Gosnay1)`, `la Blanche (ZEC Gosnay1)`. Si plusieurs sections du
même AH concernent le même cours d'eau, leurs bornes longitudinales non arrondies
apparaissent sous la forme `— section [début–fin]` (fractions entre 0 et 1).
L'infobulle expose les UUID section/cours d'eau/AH pour lever toute confusion.
Les stockages et ouvrages gardent leurs propres noms et leur nature explicite ;
ils ne se présentent plus comme des sections hydrographiques. La mention
« candidats spatiaux » disparaît. L'organisation du formulaire 0.7.29 est conservée ; seul le texte du message
d'aide de son fichier UI est complété pour le septième mode.

### Gestion, rapports et QGIS

La persistance, la relecture et les contrôles `xmin` incluent le septième champ.
Le gestionnaire permet de filtrer les sections dans la famille AH, distinctement
des stockages et ouvrages ; plusieurs enfants sélectionnés sont des alternatives.
Le filtre Cours d'eau retrouve aussi une prestation de ses sections enregistrées.
Les rapports retrouvent l'AH parent par l'UUID exact de la section, même si sa
référence devient obsolète. Ils distinguent ce lien enregistré de la
reconnaissance indirecte historique par intersection d'une prestation sur cours
d'eau. Aucun produit cartésien avec toutes les sections du parent n'est créé.
Une prestation conserve un seul rattachement direct et ne compte qu'une fois
dans les statistiques globales. Les mesures de l'intervention viennent des
champs stockés ; les mesures du patrimoine affichées comme contexte restent
séparées de la quantité déclarée.

Les deux projets conservent leurs **26 couches, dont 25 PostgreSQL**, leurs
sources, styles, actions, couches d'accrochage et les trois représentations
cartographiques des prestations. Aucune couche permanente n'est ajoutée ; la
couche physique `prestations` n'est pas réintroduite, `prestations_fiches` reste
présente. Quatre relations supplémentaires relient les trois cartes et les
fiches à la couche `ah_sections_carte` déjà chargée : **66 relations au total**.
Les formulaires affichent le nouveau champ en lecture seule avec un widget
`RelationReference`. La fiche de la section cartographique permet la navigation
vers les prestations concernées. Les identifiants des 62 relations précédentes
sont préservés. Le synchroniseur Démo/CABBALR conserve ces configurations et
leurs connexions propres. Pour les URI de widgets mises en cache, l'identifiant
de la couche référencée fait foi pour actualiser l'authentification et TLS.
Le filtre propre au widget est conservé : il peut permettre la lecture de
références masquées par le filtre cartographique. Une référence vers une autre
table est refusée.

### Préparation et ordre du déploiement

1. Vérifier en lecture seule le schéma effectif, les dépendances, les rôles,
   les signatures et les sections conformes. Le diagnostic du 17 novembre 2026
   relève Démo : 104 prestations/1 section conforme ; CABBALR : 7 prestations/
   8 sections conformes. Aucun chevauchement longitudinal digue/AH ni écart
   géométrie/fractions n'est observé. Une prestation Démo sur cours d'eau
   intersecte une section ; elle n'est pas convertie. Ces effectifs sont datés,
   pas des préconditions de volume à imposer lors du déploiement.
2. Générer le SQL ponctuel avec
   `python3 model/preparer_transition_hydro_assoc.py`. Le résultat local est
   `audits/HYDRO-ASSOC-01/transition.sql`. L'outil ne se connecte jamais à une
   base ; il extrait fonctions, contraintes et vues du schéma canonique.
   Conformément à AGENTS.md, cet outil de préparation en attente devra être
   supprimé après les deux transitions validées, sans catalogue de migrations
   historiques. Ne pas exécuter `schema.sql` sur une base existante.
3. Requalifier la transition sur un PostgreSQL jetable et conserver un
   diagnostic récent des deux bases. Le SQL prend un verrou court sur
   `prestations`, refuse un second passage non diagnostiqué, ajoute le champ
   nullable et sa FK/index, remplace les deux contraintes, deux fonctions
   existantes et trois vues, et crée le trigger d'admissibilité. Les vues sont
   remplacées avec `CREATE OR REPLACE`, sans suppression en cascade ; les
   propriétaires, ACL, OID et options `security_invoker` sont conservés.
   Une signature de tous les attributs de prestations contrôle l'absence de
   réécriture métier ; la couverture, l'unicité et les huit mesures des vues
   sont contrôlées avant COMMIT. Aucun rôle ou privilège métier n'est modifié.
4. **Obtenir l'autorisation explicite avant toute application Supabase.**
   Déployer la base avant le plugin et les nouveaux QGZ, en interrompant les
   éditions pendant cette courte transition. Les anciennes prestations restent
   valides. Les logins QGIS doivent déjà avoir accès au schéma PostGIS dans leur
   `search_path` ; cette transition ne change pas les paramètres des comptes.
5. Relire les définitions déployées, vérifier les trois profils et les mesures,
   puis installer le ZIP compatible et les deux QGZ de même génération. Pour
   la préparation courante 0.7.31, appliquer aussi la transition des noms décrite
   ci-dessous avant activation. Après
   validation sur Windows, autoriser l'utilisation métier des sections AH.
   Ne pas utiliser l'ancien plugin pour modifier une prestation nouvellement
   enregistrée sur section : il ne connaît pas son rattachement.

En cas d'échec avant COMMIT, ROLLBACK annule toute la transition. Après COMMIT,
le premier retour arrière est applicatif : conserver les ajouts SQL et revenir
au paquet précédent seulement tant qu'aucune prestation sur section n'existe.
S'il en existe, garder la version qui sait les consulter et diagnostiquer avant
tout retrait de colonne ou vue. Aucune suppression/réaffectation automatique
n'est une stratégie de retour arrière acceptable.

### Qualification

Les tests ciblés sont dans `plugin/tests/test_hydro_assoc_integration.py` et
`test_patrimony_spatial.py` ; ils utilisent un PostGIS jetable et les véritables
API QGIS. La transition a été vérifiée sur une base vide et sur 100 prestations
fictives existantes : signatures métier inchangées et zéro divergence des huit
mesures entre table et vues. Les tests Linux s'exécutent avec QGIS 3.44.15 ;
la recette Windows et la qualification complète QGIS 3.34/3.40 restent à faire.
Le rapport de campagne détaillé et ses résultats bruts sont locaux sous
`audits/HYDRO-ASSOC-01/`, ignorés par Git. Aucun test d'écriture ne vise Supabase.


## HYDRO-DEPLOIEMENT-01 — noms métier obligatoires

État préparé le 17 novembre 2026 : **aucune transition Supabase appliquée**.
Le plugin 0.7.31 utilise directement `cours_eau.nom` ; l'ancien mécanisme de
libellés anonymes est supprimé. Les UUID restent inchangés. Les sources Démo
renomment trois objets synthétiques ; CABBALR conserve ses 170 objets nommés.
Le schéma impose `nom NOT NULL` et `cours_eau_nom_non_vide`, qui rejette aussi
les chaînes composées uniquement d'espaces, tabulations ou sauts de ligne.
Les qualifications hydrographiques et les sept modes ne changent pas.

Les deux QGZ conservent 25 couches PostgreSQL, le fond OSM et 66 relations.
Leurs champs virtuels de libellés lisent directement `"nom"`, en conservant leurs
identifiants et widgets. Le QGZ officiel CABBALR garde provisoirement son filtre
hydrographique tant que sa base réelle n'est pas nettoyée. La copie sans filtre
est un artefact de préparation, pas un projet déjà activé. Le synchroniseur
conserve son exception actuelle de filtre : elle reste nécessaire pendant cette
transition ; après activation de deux projets sans filtre, elle devient inactive.
Sa suppression éventuelle fera l'objet d'un contrôle séparé.

L'ordre des transitions, les précontrôles et la reprise sont décrits dans
[la procédure de déploiement](../cabbalr/sql/README.md#déploiement-coordonné-hydro).
La qualification QGIS 3.34/3.40/3.44 et la recette Windows restent à réaliser
après stabilisation et déploiement autorisé des bases.
