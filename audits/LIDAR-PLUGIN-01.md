# LIDAR-PLUGIN-01 — LiDAR HD 2026, version d'examen 0.1.0

Date : 17 novembre 2026. Branche : `development`, branche courante conservée.
Développement initial sans commit ni push ; leur réalisation a ensuite été
explicitement demandée, en isolant les changements de ce chantier. Aucun
changement de branche ni accès à Supabase pour ce chantier.
Les modifications métier apparues en parallèle dans le dépôt sont préservées.

## Audit et périmètre

Le script de référence `LiDAR/lidar_ign.py` (V0.7) reste en place, strictement
identique à `HEAD`. SHA-256 :
`9d50aadd1b77f7c292514037528932e02d66142996847d4ab3d5f684218344c9`.
Ses GeoPackages, son projet QGIS et ses tests existants ne sont pas modifiés.
Le plugin n'importe pas le script et le ZIP ne l'embarque pas.

Le constructeur SIG-Prestations existant utilise un manifeste explicite, des
horodatages ZIP fixes et une comparaison binaire archive/sources. Le constructeur
LiDAR reprend ces principes dans `LiDAR/build_plugin.py`. La classe
`SigMilieuxUX` créait son action dans `initGui()` via `iface.addToolBarIcon()`
et la retirait dans `unload()`. Son adaptation se limite à la recherche/création
de la barre commune et au nettoyage des actions. Aucun changement de métier ni
d'icône SIG-Prestations n'est réalisé par ce chantier. Ses métadonnées restent
à QGIS 3.44 minimum : la compatibilité LiDAR ne modifie pas cette exigence.

## Architecture actuelle

Package autonome `LiDAR/lidar_hd_2026/` :

- `__init__.py`, `metadata.txt`, `plugin.py` : entrée QGIS, action unique, barre.
- `dialog.py`, `selection.py` : interface native, capture cartographique,
  prédiagnostic, progression et restitution. Le choix des couches utilise
  `QgsMapLayerComboBox` filtré Polygon. Les sélections propres à l'outil ne
  modifient ni les géométries ni les sélections des couches sources.
- `spatial.py` : copie et transformation des géométries en EPSG:2154, tampon
  0–100 m (25 m par défaut), union pour la surface et grille exacte dédupliquée.
- `engine.py` : paramètres WMS, reprises, cache, copies atomiques, VRT et tâche.
- `rendering.py` : fonction Turbo reprise du script V0.7, avec les deux familles
  de détection d'énumérations conservées, sans statistiques exhaustives initiales.
- `config.py`, `icons/` : configuration publique et ressources locales.

La sélection spatiale, les paramètres GetMap, la grille 256 m / 512 pixels,
la résolution 0,5 m, Float32, NoData -9999, les quatre tentatives sur HTTP
429/500/502/503/504 et le rendu adaptatif reprennent les choix existants.
Les ajouts nécessaires concernent l'instantané de paramètres, le dialogue,
le stockage portable et les écritures concurrentes ; aucune dépendance externe
n'est ajoutée. Le cache existant et ses noms de tuiles sont réutilisés.

Le thread principal lit les couches et les widgets, produit l'instantané spatial
puis le plan immuable de fichiers/blocs. `QgsTask.run()` n'accède à aucune couche
QGIS vivante, aucun widget ni au projet : il effectue uniquement réseau,
verrous Qt, fichiers, GDAL et progression. Les copies et le VRT sont créés après
récupération des blocs disponibles. Seul `finished()` restitue le résultat au
thread principal, où le raster est ajouté, stylé, activé et affiché.
Décharger le plugin annule sa tâche et détache ses rappels graphiques.

Une erreur de bloc peut produire un VRT partiel signalé **INCOMPLET**. Sans aucun
bloc valide, aucun raster n'est ajouté. Une erreur Turbo laisse le raster valide
avec son rendu par défaut et un message d'erreur. Les blocs restent rectangulaires,
sans masque des pixels extérieurs aux polygones, conformément au moteur initial.

## Stockage, diagnostic et concurrence

Le mode local produit `<racine>/<nom>/<nom>.vrt` et `tiles/`. Tous les chemins
sources du VRT sont relatifs. Le dossier exporté est autonome, indépendant du
cache technique. Les noms sont validés selon les contraintes courantes Windows
et Linux. Les dossiers existants sont refusés, jamais écrasés silencieusement.

Le pool reste désactivé tant que `POOL_ROOT = None`. Aucune adresse de partage
n'a été inventée. Lorsqu'il est configuré, il stocke `tiles/` et
`extractions/<nom>/<nom>.vrt`, avec chemins relatifs vers les blocs communs.
Le plugin ne supprime jamais les blocs du pool. Les erreurs d'accès sont
signalées ; le partage doit exister avant l'extraction.

Le prédiagnostic n'effectue aucun appel IGN (ni GetMap ni GetCapabilities).
Il lit les géométries des sources et les fichiers du cache/pool demandé : les
éventuels accès propres à un fournisseur distant ou à un système de fichiers
réseau restent ceux nécessaires à la lecture de ces sources.
Il distingue nombre d'entités, parties polygonales, surface de l'union tamponnée,
blocs nécessaires, blocs cache/pool, blocs manquants, estimation IGN et estimation
de copie. Base : 1 Mio/bloc ; moyenne observée des blocs concernés disponibles
si possible. Les changements d'emprise, couche, tampon ou géométrie invalident
immédiatement le bouton, puis actualisent le diagnostic par temporisation Qt.

Chaque bloc commun ou en cache est protégé par `QLockFile`, revérifié après
acquisition. Les temporaires ont un nom unique et sont créés sur le même volume
que la destination ; publication par renommage atomique. Attente annulable,
maximum 10 minutes ; verrou déclaré périmé après 15 minutes. Les extractions
homonymes sont réservées par création exclusive de dossier. Un échec de
finalisation nettoie seulement le dossier réservé par cette tâche, jamais le
cache ni les blocs du pool. Un verrou laissé par un arrêt brutal est géré par Qt.
La validation multi-hôtes SMB/Windows reste à faire sur le véritable partage.

## Barre SIG-Milieux et icône

Les deux plugins utilisent `QToolBar` avec le même `objectName`
`SIGMilieuxToolbar`, sans s'importer mutuellement. Chargement individuel ou dans
les deux ordres, initialisation répétée, retrait dans les deux ordres et
rechargement sont contrôlés. Le dernier plugin retire la barre vide ; le retrait
de l'autre laisse la barre et les actions restantes en place. LiDAR réutilise
la même `QAction` pour son entrée de menu et sa barre : une seule action créée.

L'icône finale reproduit en SVG natif la référence fournie sous le nom
`LiDAR/a_clean_flat_vector_style_icon_on_a_white_backgr.png` : cercle marine,
scanner, faisceaux bleus et vagues bleue, jaune et rouge. Le fichier demandé
initialement sous le nom `LiDAR/lidar_hd_reference.png` n'était pas présent.
Les couleurs de base ont été échantillonnées sur la référence. Les tracés sont
vectoriels, sans image incorporée, ressource externe ni police. Les légères
variations de texture du bitmap de référence ne sont pas reproduites.
L'extérieur du cercle est transparent ; l'intérieur reste blanc comme sur la
référence. `lidar_hd.png` est l'export Qt SVG 128 × 128 du même dessin.
L'action et les métadonnées utilisent `icons/lidar_hd.svg`.

Les aperçus ont été inspectés à 16, 24, 32 et 128 pixels sur fonds clair et sombre.
À 24 pixels le cercle, le scanner, les faisceaux et les trois vagues restent
identifiables. À 16 pixels les faisceaux sont moins détaillés. La pastille
multicolore précédente est conservée uniquement dans les aperçus ignorés de
`audits/lidar-icons/`, à la demande de l'utilisateur, sans version concurrente
active dans le package ni le ZIP.

## Inventaire des API sensibles

| API | QGIS 3.34 | QGIS 3.40 | QGIS 3.44 | Traitement et contrôle |
| --- | --- | --- | --- | --- |
| `QgsColorRampShader` : interpolation | `Interpolated` | `Qgis.ShaderInterpolationMethod.Linear` | identique 3.40 | détection des attributs, constructeur natif conservé |
| Classification du shader | `QgsColorRampShader.Continuous` | `Qgis.ShaderClassificationMethod.Continuous` | identique 3.40 | même détection, classification de la rampe Turbo |
| Min/max : limites | `QgsRasterMinMaxOrigin.MinMax` | identique 3.34 | `Qgis.RasterRangeLimit.MinimumMaximum` | détection `RasterRangeLimit` |
| Min/max : emprise | `QgsRasterMinMaxOrigin.UpdatedCanvas` | identique 3.34 | `Qgis.RasterRangeExtent.UpdatedCanvas` | même détection ; aucune statistique exhaustive initiale |
| Min/max : précision | `QgsRasterMinMaxOrigin.Estimated` | identique 3.34 | `Qgis.RasterRangeAccuracy.Estimated` | même détection |
| `QgsStyle.defaultStyle().colorRamp("Turbo")` | API existante | API existante | testée sur runtime | absence de palette traitée sans perdre le raster |
| `QgsTask`, `CanCancel`, progression, `finished()` | API existante | API existante | gestionnaire réellement testé | pas de couche vivante ni de widget dans `run()` |
| `QgsMapLayerComboBox`, filtre `PolygonLayer` | alias natif disponible | alias disponible | testé | imports par `qgis.gui` et `qgis.core` |
| `QgsCoordinateTransform`, `QgsGeometry.buffer/intersects/unaryUnion` | API existante | API existante | calculs réels testés | copie avant transformation, contrôle du retour de transformation |
| `QgsMapTool`, événements, `QgsRubberBand` | API existante | API existante | clics/annulation/restauration testés | surbrillance indépendante, menu explicite en cas d'ambiguïté |
| `QToolBar`, `QAction`, `QIcon`, `QSvgRenderer`, `QLockFile` | Qt via `qgis.PyQt` | idem | testés sous Qt 5 | pas d'import direct PyQt5 ni d'outil système de verrouillage |
| GDAL : GeoTIFF / `BuildVRT` / chemins sources | dépend du GDAL fourni | idem | GDAL 3.8.4 testé | validation EPSG/type/grille/NoData/pixels ; réécriture relative explicite |
| Fichiers et chemins | Python fourni avec QGIS | idem | Linux testé | pas de séparateurs Linux imposés ; validation réelle Windows restante |

Sources officielles consultées :

- [Shader QGIS 3.34](https://api.qgis.org/api/3.34/classQgsColorRampShader.html)
  et [shader QGIS 3.40](https://api.qgis.org/api/3.40/classQgsColorRampShader.html).
- [Min/max QGIS 3.40](https://api.qgis.org/api/3.40/classQgsRasterMinMaxOrigin.html)
  et [min/max QGIS 3.44](https://api.qgis.org/api/3.44/classQgsRasterMinMaxOrigin.html).
- [Tâches QGIS 3.34](https://api.qgis.org/api/3.34/classQgsTask.html),
  [sélecteur de couche](https://api.qgis.org/api/3.34/classQgsMapLayerComboBox.html)
  et [outil cartographique](https://api.qgis.org/api/3.34/classQgsMapTool.html).

La vérification documentaire et les simulations d'énumérations ne remplacent
pas une exécution sur chacun des trois runtimes.

## Vérifications effectuées

Environnement effectif : Linux, QGIS **3.44.15-Solothurn**, GDAL **3.8.4**, Qt 5.
Les tests utilisent uniquement des géométries en mémoire et des GeoTIFF Float32
synthétiques, jamais les données réelles CABBALR ni les GeoPackages de référence.
Le réseau Python est interdit ; les réponses HTTP sont simulées.

- Vérification avant commit : **29 tests hors écran réussis en 49,450 s**,
  depuis un instantané composé uniquement des sources déjà commitées et des
  modifications LiDAR/intégration graphique. Les deux processus Linux distincts
  ont partagé le cache avec un seul téléchargement simulé ; le rendu des pixels
  et le rappel graphique avec rafraîchissement explicite sont également validés.
- Polygones simples, MultiPolygon, plusieurs entités, parties disjointes, trous,
  intersection exacte et déduplication, tampons 0/25/100 m, reprojection avant
  tampon, géométries invalides et surface sans double compte.
- Cache vide, partiel, intégral ou corrompu ; validation type/SCR/grille/NoData ;
  HTTP temporaire repris, HTTP définitif et réponse XML refusés ; annulation,
  reprise et conservation des blocs ; VRT partiel et échec total explicites.
- VRT de secteurs disjoints, NoData entre secteurs, chemins relatifs, déplacement
  de dossier, suppression du cache puis réouverture du projet `.qgz` avec style.
- Pool non configuré/inaccessible/déconnecté ; copie du cache vers le pool ;
  réutilisation du pool sans téléchargement ; conservation de ses blocs après
  suppression du seul dossier d'extraction ; conflit homonyme sans écrasement.
- Deux tâches concurrentes sur le même cache, un seul téléchargement simulé,
  aucun `.part` ou verrou résiduel ; contrôle interprocessus séparé également
  réussi, après synchronisation des deux plans avant acquisition des verrous.
- Sélection multicalque avec ambiguïtés simulées, bascule gauche, fin droite,
  annulation Échap, interruption par changement d'outil, retour au dialogue et
  outil précédent ; suppression d'une couche source avec dialogue ouvert.
- Gestionnaire de tâches QGIS réel : exécution worker, rappel sur le thread GUI,
  ajout du raster et conservation du rendu par défaut en cas d'échec Turbo.
- Rendu natif réel d'un GeoTIFF Float32 à gradient d'altitudes : plus de
  100 couleurs distinctes calculées par la rampe continue, et non un simple
  contrôle des propriétés du renderer. Les bornes provisoires 0–1 sont
  remplacées lors du rendu à partir de l'emprise actualisée.
- Deux plugins chargés dans les deux ordres, déchargés dans les deux ordres,
  réinitialisés et rechargés ; icônes présentes, aucune barre/action dupliquée.
- ZIP reproductible, manifeste fermé, fichiers identiques aux sources,
  découverte QGIS et import dans un processus neuf depuis le ZIP extrait.
- SVG natif, fond transparent extérieur, PNG 128 identique au rendu SVG,
  présence des trois couleurs de vagues à 24 pixels, inclusion SVG/PNG dans le ZIP.
- Familles d'énumérations **3.34/3.40 simulées sur le runtime 3.44** ; rendu 3.44
  effectivement exécuté. La suite peut être relancée dans les environnements
  QGIS 3.34 et 3.40, où elle vérifie alors leurs véritables API de rendu.

La sandbox empêchait Qt de matérialiser certains fichiers temporaires (même un
projet QGIS vide échouait avec `Unable to perform zip`). Le même test exécuté
hors sandbox a réussi, de même que la suite complète. Aucun contournement de
cette restriction n'est ajouté au plugin.

Régressions SIG-Prestations : le test du ZIP et le script complet
`plugin/tests/test_qgis_runtime.py` réussissent. Le test indépendant
`test_home_layout` échoue sur un bouton masqué sans connexion de prestations ;
le même échec est reproduit sur la classe de `HEAD`, avant l'adaptation de
barre. Aucun comportement métier n'est changé
pour satisfaire ce test.

### QGIS Desktop et validations restantes

Une recette automatisée a réellement été lancée dans l'exécutable **QGIS
Desktop 3.44 / QgisApp sous Xvfb**, depuis les ZIP extraits : barre commune,
sélection par vrais clics Qt, prédiagnostic, tâche et création du raster avec
renderer Turbo ont été contrôlés (`audits/lidar-desktop/prediagnostic.png`,
`raster.png`). Le premier canevas de recette était fixé explicitement aux
emprises vectorielles : sa capture ne suffit donc pas à valider l'affichage
des pixels raster. La recette a été adaptée pour isoler ensuite le raster,
mais cette dernière version n'a pas pu être exécutée complètement. Le rendu
des pixels est validé séparément par le test natif hors écran décrit ci-dessus.
La recette complète n'est **pas validée** : les premières tentatives ont subi
un signal 11 dans la phase ultérieure de retrait de couches/projet ; les
relances ont atteint leur délai de démarrage. Le nettoyage des signaux de
couches a été renforcé et la suppression avec dialogue ouvert a son propre
test PyQGIS réussi, mais une recette Desktop complète reste à refaire.
La sauvegarde/réouverture est, elle, réussie dans les tests PyQGIS hors écran.
Aucune recette humaine n'est présentée comme effectuée.

Restent à valider avant diffusion générale :

1. Recette complète QGIS Desktop dans un environnement graphique stable.
2. Exécutions réelles avec QGIS 3.34 et 3.40.
3. Installation et recette sous **Windows**, chemins Unicode/UNC, déplacement
   du dossier, annulation et réouverture inclus.
4. Pool sur le véritable partage réseau : ACL, déconnexion, verrouillage et
   renommage entre deux machines/utilisateurs. Aucun partage réel n'est configuré.
5. Contrôle IGN en situation réelle : aucun téléchargement IGN effectué ici.

## Livrables et reproduction

- Sources : `LiDAR/lidar_hd_2026/` ; documentation : `LiDAR/README.md`.
- Constructeur : `LiDAR/build_plugin.py` ; tests : `LiDAR/tests/`.
- Distribution : `plugin/dist/lidar_hd_2026-0.1.0.zip` et ZIP SIG-Prestations
  reconstruit dans `plugin/dist/` pour bénéficier de la barre commune.
- Pour le commit, le ZIP SIG-Prestations 0.7.29 est reconstruit depuis les
  sources déjà commitées, augmentées uniquement de l'intégration graphique.
  Les évolutions métier concurrentes non commitées, dont la version 0.7.30,
  restent hors de ce ZIP et hors du commit LiDAR.
- Correction de l'emplacement de distribution : les ZIP sont générés uniquement
  dans `plugin/dist/` et ignorés par Git, selon la convention SIG-Prestations.
  Les archives précédemment versionnées dans le dossier racine `dist/` sont
  retirées et ce dossier est supprimé ; une règle Git empêche de les réintroduire.
- Aperçus : `audits/lidar-icons/`, fichiers de test/logs ignorés par Git.
- Rapport demandé : le présent fichier, seule exception documentaire à
  l'exclusion Git des sorties d'audit. Aucun fichier temporaire, jeu métier,
  GeoPackage, journal, secret ou fichier de référence bitmap n'entre dans le ZIP.

Reproduction complète et instructions Windows : voir `LiDAR/README.md`.
Cette version est proposée à l'examen et à la recette ; elle n'est pas déclarée
compatible Windows ni prête pour diffusion générale.
