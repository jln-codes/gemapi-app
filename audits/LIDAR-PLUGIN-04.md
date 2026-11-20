# LIDAR-PLUGIN-04 — bibliothèques mutualisées et couverture globale

18 novembre 2026 — LiDAR HD 2026 **0.1.3**, branche `development`.
Base de travail propre : `70b2d8b`, synchronisée avec `origin/development`.

## Architecture livrée

Les deux modes utilisent directement la bibliothèque sélectionnée :

```text
LiDAR HD IGN 2026/
  tiles/mnt_l93_<x>_<y>_256m_512px.tif
  extractions/site_A.vrt
  extractions/site_B.vrt
  mnt_lidar_global.vrt
```

La priorité de récupération est identique en local et dans le pool : tuile
valide dans la bibliothèque, puis cache technique historique, puis IGN.
Une tuile n'est copiée qu'une fois vers la bibliothèque. Chaque extraction
possède un VRT restreint aux blocs intersectant ses polygones tamponnés,
avec sources relatives `../tiles/...`. Le VRT global utilise `tiles/...`.
Seul l'individuel est ajouté automatiquement au projet QGIS.

La sélection polygonale, les transformations, le tampon, la grille 256 m /
512 pixels, le Float32 / NoData -9999, les requêtes IGN, les tentatives HTTP,
la validation des GeoTIFF et le rendu sont conservés. Les fonctions
`download_block`, `is_lambert93`, `geotiff_error`, `check_geotiff`, `validate_name`
et `build_vrt` ont été comparées à HEAD : leurs corps sont identiques.
L'adaptation porte sur l'orchestration du stockage, les verrous et l'inventaire.

Le cache `qgis_lidar_ign_cache` et ses fichiers gardent leur emplacement et leur
format. La bibliothèque ne peut pas être ce cache ou un sous-dossier de celui-ci.
`config.py`, le chemin Windows du pool et le script historique sont inchangés :

```text
J:\1-milieux-aquatiques-et-risques\0. QGIS\Catalogues des couches\LiDAR HD IGN 2026
```

## Publication et concurrence

Un verrou `QLockFile` réserve le VRT individuel avant les transferts ; les
conflits de fichier et d'ancien dossier sont revérifiés sous verrou. Un verrou
par tuile de bibliothèque est acquis avant celui du cache. Une seconde instance
revérifie la tuile après l'attente : même avec deux caches différents, elle
réutilise le résultat de la première au lieu de retélécharger le même bloc.

Les copies, téléchargements et VRT sont publiés depuis un temporaire unique du
même dossier par remplacement atomique. La couverture globale a son propre
verrou. Les réservations d'extraction et du global ne deviennent pas périmées
sur la seule durée d'un traitement long ; l'attente reste annulable et bornée
à dix minutes. Les verrous courts de tuiles conservent leur politique existante.

Aucune tuile mutualisée n'est supprimée. L'annulation avant validation de
l'individuel ne retire que le VRT venant d'être publié par cette tâche ; les
tuiles récupérées restent disponibles pour la reprise. Une annulation pendant
le contrôle global conserve l'individuel déjà enregistré, affiche son chemin
et garde le dialogue ouvert.

## VRT global et contrôle manuel

Après chaque individuel enregistré, y compris un résultat partiel, le moteur
inventorie les GeoTIFF présents directement dans `tiles/`. Il exclut les fichiers
invalides et les temporaires. Il tient compte des ajouts et retraits manuels,
des remplacements, des TIFF et TIFF longs d'extension `.tiff`.

La signature et l'inventaire validé sont stockés dans les métadonnées du VRT,
sans index externe. L'inventaire contient nom, taille, date de modification
nanoseconde et origine du bloc. Le contrôle automatique vérifie le contenu réel
du dossier et revalide les fichiers nouveaux ou modifiés. Les validations des
fichiers dont taille/date sont inchangées sont réutilisées ; cela évite de
relire toute la bibliothèque après chaque extraction depuis des tuiles existantes.
La signature de cet inventaire, la liste relative des sources et la lisibilité
du VRT sont comparées avant de décider de reconstruire. Un inventaire absent
ou incohérent est recalculé. La construction du VRT conserve la validation
complète de ses sources.

Le bouton **Actualiser le VRT global** lance une `QgsTask` indépendante de
l'emprise : il force le contrôle intégral des pixels de toutes les tuiles,
même sans changement de taille/date. Il ne télécharge rien et ne charge pas
le global dans QGIS. Si aucune tuile valide ne reste, seul le VRT global périmé
est retiré ; les GeoTIFF, même invalides, restent en place.

Une erreur de publication du global conserve sa version précédente et
l'individuel réussi. Le raster individuel est chargé et colorisé normalement ;
une notification d'avertissement précise l'échec global. La fermeture après
réussite individuelle complète reste active. Les erreurs, annulations,
individuels incomplets ou échecs Turbo maintiennent le dialogue ouvert.

## Dialogue et anciennes extractions

Le champ **Bibliothèque** désigne un stockage permanent, mémorisé par
`QSettings` après sélection valide, saisie validée ou utilisation. Les choix
de bibliothèque sont libres. L'état affiché distingue un dossier vide, une
structure existante et un dossier à compléter ; un changement affiche le risque
de duplication entre bibliothèques distinctes. Aucun déplacement ni fusion.

Le prédiagnostic reste sans requête IGN : entités, parties, surface tamponnée,
blocs nécessaires, blocs dans la bibliothèque, blocs disponibles **seulement**
dans le cache technique, blocs réellement à télécharger, volume IGN, nouvelles
données estimées dans la bibliothèque et destination exacte du VRT individuel.
La bibliothèque est prioritaire et les deux compteurs sont disjoints.

Les anciens dossiers locaux `<racine>/<nom>/tiles/` et ceux du pool
`extractions/<nom>/<nom>.vrt` ne sont ni déplacés ni modifiés. Leurs noms sont
refusés pour les nouvelles extractions. Les VRT existants ne sont pas écrasés.
Les nouvelles extractions n'ont pas de sous-dossier ni de copies privées.
La portabilité exige de déplacer toute la bibliothèque, pas seulement un VRT.

## Tests effectivement exécutés

| Environnement réel | Résultat final |
| --- | --- |
| QGIS 3.44.15, GDAL 3.8.4, Ubuntu 24.04.5 | **52 tests réussis** |
| QGIS 3.34.15, image Linux locale sans réseau | **51 réussis, 1 non applicable** |
| QGIS 3.40.15, image Linux locale sans réseau | **51 réussis, 1 non applicable** |
| QGIS Desktop 3.44.15, Qt/Xcb sous Xvfb, ZIP 0.1.3 installé dans un espace isolé | **recette réussie** |
| Windows et véritable partage `J:` / SMB | **non disponibles, restant à valider** |

Le cas non applicable sur 3.34/3.40 concerne le couple avec SIG-Prestations,
dont la version courante exige QGIS 3.44. LiDAR seul et les tests de stockage
utilisent les véritables API de chaque runtime. Les façades d'anciennes
énumérations testées séparément sont des simulations, pas des recettes Desktop.

Les douze nouveaux tests et les régressions adaptées couvrent : partage de tuiles
en local/pool, absence de copie supplémentaire, priorité bibliothèque/cache,
VRT restreints et global, mise à jour et absence de réécriture inutile,
ajouts/retraits/fichiers invalides, réparation d'inventaire, contrôle intégral
manuel, anciennes extractions intactes, conflits de noms, déplacement complet
et réouverture de projet, annulation et reprise, publication globale en échec,
deux utilisateurs avec caches distincts et union finale de leur couverture.
Deux vrais processus avec des caches distincts effectuent un seul téléchargement
simulé du bloc commun ; leurs deux VRT sont créés et le global est valide.
Un XML conservant artificiellement taille/date est refusé par le prédiagnostic
d'extraction et le contrôle global manuel. Aucun assouplissement du validateur.

La recette Desktop réutilise le ZIP SIG-Prestations **0.7.33**, sans reconstruction
ni modification. Elle vérifie les deux icônes, la sélection sur deux couches,
les deux blocs du cache technique, l'individuel Turbo/Updated Canvas,
le global créé mais absent du projet, la fermeture automatique et la réouverture
à zéro, puis la réouverture du projet après suppression du cache de test.
Résultat `ok=true`, phase `projet rouvert`.

Une assertion de contrôle initiale lisait le coin vide d'un VRT disjoint et
attendait une altitude au lieu de NoData. Elle vérifie désormais un pixel du
secteur effectivement couvert après déplacement. Les campagnes finales passent.
Aucune requête IGN réelle n'a été nécessaire.

## Performances

Mesure reproductible : `LiDAR/tests/benchmark_library.py`, bibliothèque locale
de **100 GeoTIFF Float32 synthétiques**, grille 10 × 10, trois extractions
successives limitées aux deux premiers blocs. Résultats sous `audits/`.

| Mesure finale, médiane de trois répétitions | Temps |
| --- | ---: |
| Prédiagnostic des deux blocs | 0,036 s |
| Extraction depuis la bibliothèque, contrôle global compris | 0,295 s |
| Ouverture de l'individuel et configuration Turbo | 0,058 s |
| Rendu individuel 512 × 512, deux sources | 0,164 s |
| Rendu global de contrôle 512 × 512, cent sources | 1,996 s |

L'individuel mesure **2 031 octets**, le global avec inventaire **55 337 octets**.
Les trois extractions ajoutent **zéro GeoTIFF**, copient **zéro octet** et ne
transfèrent **aucun octet IGN**. Le global inchangé conserve son horodatage.

Le premier inventaire et la construction complète du global prennent environ
**4,46 s** dans ce petit essai. Le prototype relisant systématiquement les
cent tuiles prenait environ 3,28 s par extraction ; l'inventaire réutilisable
supprime cette lecture systématique. Ces petites séries montrent le coût des
opérations, sans constituer une garantie de latence ou un benchmark SMB.
Le rendu utilise le même `rendering.py`, Turbo, interpolation linéaire,
Minimum/Maximum estimés et Updated Canvas ; son test sur pixels réels passe.

## Reproduction, limites et livraison

```sh
python3 LiDAR/build_plugin.py
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover -s LiDAR/tests -v
QT_QPA_PLATFORM=offscreen /usr/bin/python3 LiDAR/tests/benchmark_library.py
```

Le lanceur Desktop et la préparation du profil isolé sont décrits dans
`LiDAR/README.md`. Les traces locales ignorées sont dans
`audits/lidar-plugin-04/` : logs des trois runtimes, `performance.json`,
`performance-full-scan.json`, `desktop/result.json` et captures Qt.

Le contrôle automatique du global se fonde sur taille/date pour les fichiers
déjà validés : une corruption externe préservant exactement ces métadonnées
requiert le contrôle manuel intégral. Les tuiles utilisées par une extraction
restent toujours validées entièrement. Les suppressions manuelles peuvent
casser d'anciens VRT individuels ; le contrôle global ne restaure pas leurs tuiles.
La première construction, les reconstructions et les contrôles complets restent
proportionnels à la bibliothèque. Les écritures concurrentes et le verrouillage
ont été testés sur disque Linux, pas sur le partage Windows réel. Une validation
Windows/SMB est donc obligatoire avant une diffusion générale.

ZIP généré : `plugin/dist/lidar_hd_2026-0.1.3.zip`, manifeste fermé de 11 fichiers,
SVG/PNG inclus et comparaison binaire avec chaque source actuelle. SHA-256 :
`7486e62b4d6e74f4da8d055088d098829338d32f6d1ade27fca17ea7c3518fd2`.
ZIP, captures et traces sont des artefacts locaux ignorés par Git.
Le commit et le push sur `development` sont autorisés par l'instruction
complémentaire ; seuls les fichiers de ce chantier sont concernés.
