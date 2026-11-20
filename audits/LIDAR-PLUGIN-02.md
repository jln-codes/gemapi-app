# LIDAR-PLUGIN-02 — extraction IGN, barre et dialogue

17 novembre 2026 — LiDAR HD 2026 **0.1.1**, branche `development`.
Le commit et le push ont été autorisés en complément du chantier. Les changements
concurrents restent exclus ; aucun schéma, donnée réelle, projet utilisateur ou
base Supabase n'est modifié par cette intervention.

## Résultat

Le refus des trois blocs est reproduit avec v0.1.0, puis corrigé. Le serveur
répondait avec des GeoTIFF Float32 lisibles ; le rejet provenait exclusivement
du contrôle strict du SCR ajouté dans le plugin. Les GeoTIFF décrivent le
Lambert-93 avec un GEOGCS incomplet. La résolution, la grille, le NoData et les
pixels sont corrects. Aucun paramètre WMS, pixel ni cache existant n'est changé
pour contourner ce problème.

La barre existante pouvait rester masquée et hériter d'un style « texte à côté
de l'icône ». Les deux plugins réutilisent `SIGMilieuxToolbar`, imposent
`Qt.ToolButtonIconOnly` et affichent la barre après ajout de leur propre action.
L'entrée du menu Extensions garde son texte. Aucune barre supplémentaire n'est
créée lorsqu'une barre de ce nom existe.

Le dialogue présente deux colonnes **Emprise** et **Fichiers**, avec des layouts
Qt natifs. Le prédiagnostic couvre la largeur ; les explications secondaires
sont des infobulles. Le défilement du contenu sur écran réduit garde progression
et commandes accessibles. Les valeurs et traitements restent identiques.

## 1. Comparaison HTTP et reproduction du rejet

Le diagnostic appelle les deux fonctions `download_block()` sur les mêmes
coordonnées, dans le même processus et sur le même réseau. Les requêtes sont
interceptées pour être enregistrées puis exécutées réellement, sans toucher au
cache utilisateur. Le script historique est chargé sans son appel final
`main()` ; son fichier reste strictement inchangé.

Les URL construites sont identiques :

```text
https://data.geopf.fr/wms-r/wms
SERVICE=WMS
VERSION=1.3.0
REQUEST=GetMap
LAYERS=IGNF_LIDAR-HD_MNT_ELEVATION.ELEVATIONGRIDCOVERAGE.LAMB93
STYLES=normal
CRS=EPSG:2154
BBOX=x,y,x+256,y+256
WIDTH=512
HEIGHT=512
FORMAT=image/geotiff
EXCEPTIONS=text/xml
```

La seule différence explicite dans les en-têtes avant correction est le
`User-Agent` : `QGIS-LiDAR-IGN-prototype/0.1` pour le script,
`QGIS-LiDAR-HD-2026/0.1.0` pour le plugin. La version corrigée s'annonce en
`QGIS-LiDAR-HD-2026/0.1.1`. Les trois paires de réponses sont identiques octet
pour octet : le `User-Agent` n'est donc pas responsable du refus observé.

| Bloc (origine basse gauche) | BBOX demandée | HTTP | Content-Type | Octets, pour chacun des deux clients | Minimum / maximum exacts (m) |
| --- | --- | --- | --- | --- | --- |
| 667392,7054592 | 667392,7054592,667648,7054848 | 200 | image/geotiff | 1 049 089 | 18,782383 / 19,642279 |
| 667392,7054848 | 667392,7054848,667648,7055104 | 200 | image/geotiff | 1 049 089 | 17,933582 / 20,711765 |
| 667648,7054592 | 667648,7054592,667904,7054848 | 200 | image/geotiff | 1 049 089 | 18,820293 / 19,425842 |

Signature commune des 16 premiers octets :
`49492a00080000001000000104000100` (TIFF little-endian `II*\0`).
Aucune réponse XML/HTML, exception WMS ou erreur d'ouverture GDAL sur ces six
réponses. Chaque lecture complète contient 1 048 576 octets de pixels Float32.

SHA-256, identique entre script et plugin pour chaque bloc :

```text
667392,7054592 08492c7e43d9a5c4ef36968e7810aaee7277787d1bba4c8026f5eff830da12ac
667392,7054848 d8ca73cd1ecabcdb40c518b74c55a68cff8dd18bc3fa0672d26065422ca12dcd
667648,7054592 5cb64f0b24bc04cb23e9217da5479ded0caf4873a73b803975240425f606f1b3
```

### Contrôles séparés, avant correction

| Contrôle du plugin 0.1.0 | Résultat sur les trois blocs |
| --- | --- |
| Signature TIFF, pilote GDAL GTiff | conforme |
| Ouverture GDAL et lecture complète | conformes |
| Dimensions 512 × 512 | conformes |
| Une bande Float32 | conforme |
| NoData -9999 | conforme : -9999,0 |
| Résolution / rotation | conformes : 0,5 / 0 / 0 / -0,5 |
| Origine X et Y du bloc | conformes |
| `actual.IsSame(EPSG:2154)` | **faux : seul contrôle bloquant** |

Géotransformations lues :

```text
(667392, 0.5, 0, 7054848, 0, -0.5)
(667392, 0.5, 0, 7055104, 0, -0.5)
(667648, 0.5, 0, 7054848, 0, -0.5)
```

Le script historique vérifie dimensions, nombre de bandes et Float32 : il
accepte les six fichiers. Le plugin 0.1.0 ajoute `IsSame()` et refuse les six.

## 2. Cause exacte du SCR et correction

Le WKT lu dans les réponses contient :

```text
PROJCS["EPSG:2154",
  GEOGCS["unknown",
    DATUM["unnamed",
      SPHEROID["unretrievable - using WGS84",6378137,298.257223563]],
    PRIMEM["Greenwich",0], UNIT["degree",0.0174532925199433]],
  PROJECTION["Lambert_Conformal_Conic_2SP"],
  PARAMETER["latitude_of_origin",46.5],
  PARAMETER["central_meridian",3],
  PARAMETER["standard_parallel_1",49],
  PARAMETER["standard_parallel_2",44],
  PARAMETER["false_easting",700000],
  PARAMETER["false_northing",6600000],
  UNIT["metre",1], AXIS["Easting",EAST], AXIS["Northing",NORTH]]
```

Le nom `EPSG:2154` n'est pas une autorité EPSG identifiée dans ces fichiers.
Le datum RGF93/ellipsoïde GRS80 officiel est remplacé par des mentions inconnues
et un ellipsoïde de repli WGS84. `IsSameGeogCS()` échoue aussi ; ignorer l'ordre
des axes ne corrige rien. Il ne s'agit pas d'une inversion d'axes ni d'une erreur
sur le BBOX. Tous les paramètres projetés et la grille sont conformes.

La fonction `is_lambert93()` accepte d'abord l'équivalence officielle. Si elle
échoue, elle reconnaît uniquement la signature incomplète observée : nom projeté
exact `EPSG:2154`, GEOGCS `unknown`, datum `unnamed`, nom et valeurs précis du
sphéroïde de repli, méridien de Greenwich et unités angulaires attendues.
Elle remplace alors **sur une copie en mémoire** le seul GEOGCS par le GEOGCS
officiel, puis exige encore `IsSame(EPSG:2154)`. La méthode, les paramètres de
projection, les unités linéaires et les axes doivent donc tous rester cohérents.
Une autre projection, un nom différent, un datum connu différent ou un paramètre
Lambert altéré restent refusés.

Le VRT utilise explicitement EPSG:2154. Chaque source est préalablement contrôlée
avec ses coordonnées exactes ; après cette validation, GDAL peut assembler des
WKT officiels et des WKT IGN incomplets sans ignorer un secteur. L'option
`allowProjectionDifference` intervient uniquement après ce contrôle de toutes
les sources ; elle ne dispense pas de valider le SCR et n'effectue aucune
reprojection. Les pixels, les GeoTIFF du cache et leur géotransformation ne
sont pas réécrits. Un test mélange les deux descriptions du SCR et compare les
pixels et les octets du cache avant/après ; un autre vérifie qu'un mauvais SCR
ne peut pas entrer dans un VRT.

`geotiff_error()` détaille désormais : fichier absent, format non TIFF/signature
et extrait de la réponse, GeoTIFF illisible, dimensions, nombre de bandes, type,
NoData, SCR absent/incorrect/illisible, grille, origine du bloc, lecture corrompue.
Les réponses non TIFF sont rejetées avant toute ouverture GDAL. Une erreur IGN
conserve aussi le statut HTTP, le Content-Type et la taille de la réponse.
Les erreurs HTTP temporaires gardent leur politique de tentatives antérieure.

## 3. Barre d'outils et versions

Reproduction déterministe avant correction : barre existante nommée
`SIGMilieuxToolbar`, masquée, style `ToolButtonTextBesideIcon`. L'ancien
`initGui()` réutilise cette barre mais ne l'affiche pas et conserve le style
texte. Mesure avant correction : barre présente, `visible=false`, `hidden=true`,
style 2 (texte à côté), une action. La présence de l'entrée dans Extensions ne
prouvait donc pas la visibilité du bouton.

Correction appliquée aux deux plugins : réutiliser la barre trouvée, imposer
`ToolButtonIconOnly`, ajouter sa propre action, appeler `show()`. Les méthodes
`unload()` conservent leur nettoyage indépendant : un plugin ne retire pas
l'action de l'autre ; le dernier retire la barre vide. Aucun mécanisme de
compatibilité ni déplacement automatique des actions d'une ancienne version
installée n'est ajouté.

Le profil Linux inspecté en lecture seule contient SIG-Prestations **0.7.26**,
dont le code utilise la barre générale `addToolBarIcon()`, sans barre commune.
Aucun package LiDAR n'a été trouvé dans les deux profils Linux inspectés ; cela
ne permet pas de conclure sur la version chargée sur une autre machine.

La recette Desktop installe réellement depuis les ZIP, dans son propre espace,
**LiDAR 0.1.1** et **SIG-Prestations 0.7.30**. Les chemins chargés et versions sont
enregistrés. Les deux boutons sont visibles, style 0 (icône seule), la barre
existe une seule fois. Une barre masquée et remise en style texte est réaffichée
au rechargement. Le menu conserve son libellé. Le journal LiDAR affiche désormais
la version et le chemin du module chargé.

Une version SIG-Prestations antérieure qui ne crée pas la barre commune doit
être remplacée par le ZIP actuel pour placer les deux icônes ensemble. Le plugin
LiDAR fonctionne individuellement. Aucune installation existante n'est modifiée
automatiquement ; après remplacement de ZIP, redémarrer QGIS et vérifier la
version et le chemin chargés.

## 4. Dialogue et lisibilité

Deux colonnes de paramètres, assemblées par `QGridLayout` et formulaires Qt :

- **Emprise** : couche, entités, sélection cartographique, tampon.
- **Fichiers** : nom, stockage et dossier.

Libellés courts, alignement natif, marges et espacements confortables, largeur
par défaut 820 pixels logiques lorsque l'écran le permet. Les explications de
sélection, de tampon, de stockage et de fichiers sont des infobulles. Le choix
du pool non configuré est explicitement nommé et désactivé. Aucun texte répété
sous chaque paramètre. Le prédiagnostic reste complet et sur toute la largeur.
La progression et les trois commandes restent hors de la zone défilante.

Contrôles réels Ubuntu 24.04.5, Qt 5, Xvfb 1600 × 1000 :

| Échelle Qt | Dialogue (pixels logiques) | Affichage |
| --- | --- | --- |
| 100 % | 820 × 640 | deux colonnes, diagnostic complet, pas de défilement |
| 125 % | 820 × 640 | idem |
| 150 % | 820 × 619 | idem |
| 200 % | 760 × 452 | défilement vertical du contenu, commandes et progression visibles |

Les captures sont réalisées après stabilisation des événements et layouts Qt,
avec vérification des limites des boutons et de leur taille minimale. Ces essais
ne constituent pas une validation des thèmes, polices ou facteurs DPI Windows.

## 5. Tests et non-régression

| Environnement réellement exécuté | Résultat |
| --- | --- |
| QGIS 3.44.15, GDAL 3.8.4, Ubuntu | 35 tests réussis ; packaging du candidat revérifié isolément |
| QGIS 3.34.15, GDAL 3.8.4, conteneur Linux local sans réseau | 34 réussis, 1 non applicable, y compris au contrôle final |
| QGIS 3.40.15, GDAL 3.8.4, conteneur Linux local sans réseau | 34 réussis, 1 non applicable, y compris au contrôle final |
| QGIS Desktop 3.44.15, Qt/Xcb sous Xvfb, ZIP installés dans un espace isolé | recette complète réussie |
| Packaging SIG-Prestations, découverte et import depuis son ZIP | réussi |
| Windows | non disponible, restant à vérifier |

Le cas non applicable en 3.34/3.40 concerne le couple avec le **SIG-Prestations
actuel, qui exige QGIS 3.44**. Le fonctionnement individuel de LiDAR, sa barre,
son dialogue et son rendu ont été testés réellement sur les trois versions.
Les tests de façades d'énumérations restent des simulations distinctes ; ils ne
sont pas utilisés pour prétendre à une exécution sur un autre runtime.

Les tests hors réseau incluent le WKT IGN reproduit sur des pixels synthétiques,
le mélange de WKT, les faux SCR proches, NoData incorrect/absent, type incorrect,
XML et TIFF tronqués ; les autres cas de cache, reprise, annulation, concurrence,
VRT portable, couches Polygon/MultiPolygon et symbologie restent couverts.

Pendant le contrôle final simultané des trois runtimes, le sous-processus de
démarrage QGIS d'un test de packaging a atteint sa limite de 30 secondes. Les
34 autres cas du candidat ont réussi. Le contrôle de packaging LiDAR puis celui
de SIG ont été relancés isolément, avec des répertoires de configuration de test
séparés : deux tests réussis. Aucun contrôle de données ni délai du plugin n'a
été désactivé pour ce motif.

### Téléchargement réel et cache

Une tâche `QgsTaskManager` réelle télécharge les trois blocs dans un cache
technique **d'audit** neuf : trois requêtes, **3 147 267 octets**, zéro échec.
Progression reçue : 30 %, 60 %, 90 %, 100 %. Le VRT est lisible, relatif,
Float32/NoData -9999, min/max 17,933582 / 20,711765. Le rendu Turbo natif fournit
381 couleurs distinctes dans l'échantillon de l'image. La seconde extraction
retrouve les trois blocs : **zéro requête, zéro octet IGN**, même VRT logique et
même rendu. Les fichiers du cache utilisateur existant ne sont pas touchés.

### Recette Desktop

Chargement des deux ZIP et contrôle des versions/chemins ; création et
réutilisation de la barre ; visibilité et style des deux boutons ; déchargement
et rechargement ; clics cartographiques sur deux couches ; prédiagnostic et
nouveau dialogue ; extraction depuis les GeoTIFF synthétiques ; rendu Turbo
visible (min/max 20/70) ; VRT relatif ; sauvegarde et réouverture du projet après
suppression du cache de test. Résultat `ok=true`, phase `projet rouvert`.

Le lanceur Desktop conserve l'extension intégrée **Processing** active :
`qgis.utils.run_script_from_file()` en dépend pour exécuter `--code`. Avec
`--noplugins`, le script pouvait ne pas être exécuté. Le profil reste isolé et
ne contient aucune extension utilisateur. Les captures attendent la fin des
événements Qt pour éviter de capturer un premier layout encore transitoire.

Le script large `plugin/tests/test_qgis_runtime.py` échoue sur l'assertion métier
`_object_load_failures`, ligne 356. Le même échec est reproduit à partir des
sources SIG-Prestations 0.7.30 du commit `ea7a849`, avant les modifications de
ce chantier. Il concerne les familles d'objets du chantier hydro concurrent ;
aucune logique métier SIG n'est modifiée ici pour satisfaire ce test. Les tests
spécifiques de barre, de chargement, de déchargement et de packaging réussissent.

## 6. Livrables et limites

- Package corrigé : `LiDAR/lidar_hd_2026/`, version **0.1.1**.
- ZIP local généré : `plugin/dist/lidar_hd_2026-0.1.1.zip` ; SVG/PNG inclus,
  archive vérifiée contre les sources, sans cache, données ni secrets.
- ZIP SIG avec la correction graphique, documentation et recette Desktop
  mis à jour ; aucun changement métier SIG dans le commit LiDAR.
- Dans `plugin/tests/smoke_import.py`, seuls les faux appels Qt nécessaires à
  la barre sont retenus. L'assertion de requête des cours d'eau, modifiée dans
  le chantier concurrent, reste hors du commit LiDAR et dans le fichier de travail.
- Rapport : le présent fichier. Les réponses IGN, JSON, logs et captures restent
  sous `audits/lidar-plugin-02/`, ignorés par Git. Les profils et jeux de données
  temporaires sont supprimés après vérification.
- Script historique inchangé, SHA-256 :
  `9d50aadd1b77f7c292514037528932e02d66142996847d4ab3d5f684218344c9`.

L'emplacement reste **plugin/dist/** conformément à la correction précédente,
sans recréer de `dist/` racine. Les archives restent générées et ignorées par Git.
Le commit et le push sont limités aux changements LIDAR-PLUGIN-02.

Restent à réaliser : installation et recette réelles Windows (DPI, thèmes,
chemins Unicode/UNC, réseau et cycle de plugins), recettes interactives Desktop
3.34/3.40 et validation d'un véritable pool réseau. Les tests Linux réussis ne
valident pas Windows. Aucune compatibilité Windows n'est déclarée acquise.

Références officielles : [comparaison des SCR GDAL](https://gdal.org/en/stable/api/ogrspatialref.html),
[options BuildVRT](https://gdal.org/en/stable/api/python/utilities.html),
[barre Qt et style des boutons](https://doc.qt.io/archives/qt-5.15/qtoolbar.html),
[API QGIS 3.34](https://api.qgis.org/api/3.34/classQgisInterface.html).
