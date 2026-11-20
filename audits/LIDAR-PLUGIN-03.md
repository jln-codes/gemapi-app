# LIDAR-PLUGIN-03 — finalisation du dialogue

18 novembre 2026 — LiDAR HD 2026 **0.1.2**, branche `development`.

## Périmètre et corrections

Le dialogue conserve les colonnes **Emprise** et **Fichiers**, le prédiagnostic
complet, la progression et les commandes sur toute la largeur. L'étirement
placé après le diagnostic et le facteur d'étirement de la zone défilante sont
supprimés. La hauteur est calculée à partir des layouts Qt et plafonnée à la
hauteur disponible de l'écran. La zone de contenu défile lorsque nécessaire ;
les commandes restent à l'extérieur. L'espacement diagnostic/progression vaut
**14 pixels logiques**, sans espace vide intermédiaire.

Après une extraction réussie, `task_finished()` vérifie les références du VRT
en lecture seule : fichiers présents et ensemble des blocs attendu complet.
Le raster doit être valide, ajouté au projet, colorisé avec Turbo, activé et
rafraîchi avant la notification de réussite. Un `QTimer` à délai nul, appartenant
au dialogue, ferme ensuite la fenêtre après le retour du callback. Le timer est
arrêté à la réouverture ou au déchargement du plugin.

Les échecs, annulations, fichiers sources absents, VRT invalides ou incomplets,
échecs de chargement/activation et erreurs Turbo conservent le dialogue ouvert
avec un bilan explicite. Un raster lisible reste chargé si Turbo échoue, avec
son rendu par défaut ; aucune notification de réussite n'est alors envoyée.
Le contrôle du contenu du VRT détecte également une extraction incomplète lorsque
la liste d'erreurs de la tâche est vide. L'ajout du raster émet `layersAdded` :
le diagnostic différé correspondant est arrêté pour préserver le bilan affiché.
La réouverture depuis l'icône remet la progression à zéro lorsque la tâche est
terminée ; une tâche encore en cours conserve sa progression.

Les deux appels de gestion du menu Extensions sont retirés de LiDAR.
La `QAction`, l'icône SVG, la barre `SIGMilieuxToolbar` et ses règles de partage
restent identiques. Aucun menu de remplacement ni mécanisme de migration n'est
ajouté. Le gestionnaire d'extensions découvre toujours le plugin et ses métadonnées.

**Aucun changement** dans le moteur de téléchargement, le cache, la génération
des VRT, les paramètres techniques, la sélection spatiale, le rendu Turbo ni
SIG-Prestations. Le script historique reste strictement identique. Les ZIP
SIG-Prestations préexistants ont été réutilisés, sans reconstruction et avec
contrôle de leurs empreintes avant/après.

## Tests effectivement exécutés

| Environnement | Résultat |
| --- | --- |
| QGIS 3.44.15 / GDAL 3.8.4, Ubuntu, PyQGIS réel | **40 tests réussis** |
| QGIS 3.34.15 / GDAL 3.8.4, image Linux locale, réseau désactivé | **39 réussis, 1 non applicable** |
| QGIS 3.40.15 / GDAL 3.8.4, image Linux locale, réseau désactivé | **39 réussis, 1 non applicable** |
| QGIS Desktop 3.44.15, Qt/Xcb, Xvfb, ZIP installés | recette complète réussie |
| Nouveau processus QGIS Desktop, même profil isolé, retrait de 0.1.1 puis chargement de 0.1.2 | recette complète réussie, aucun menu résiduel |
| Affichage Qt natif à 100 %, 150 %, 200 % sous Ubuntu | géométrie et captures contrôlées |
| Windows ; recettes humaines Desktop 3.34/3.40 | **non exécutés, restant à réaliser** |

Le cas non applicable sur 3.34/3.40 est le couple avec le SIG-Prestations actuel,
qui exige QGIS 3.44. LiDAR seul, sa barre, son dialogue, la fermeture après succès
et son rendu sont testés avec les véritables API de chaque version. Les tests
de façades des anciennes énumérations restent des **simulations** distinctes.
Les tests PyQGIS hors écran ne constituent pas des recettes QGIS Desktop.

Les cinq nouveaux tests couvrent la fermeture d'une vraie `QgsTask` avec 100 %
des blocs synthétiques en cache et sa réouverture à 0 %, l'échec et l'annulation,
les VRT partiels avec/sans liste d'erreurs, les VRT invalides/sources absentes/
échecs de chargement ou d'activation et l'absence d'appels de menu au rechargement.
Le test existant d'échec Turbo vérifie désormais le maintien de la fenêtre et
du message d'avertissement après traitement des événements Qt.

Les régressions existantes restent couvertes : géométries Polygon/MultiPolygon,
tampons, sélection cartographique et ambiguïtés, cache partiel/intégral, reprise,
annulation, concurrence entre threads/processus, VRT disjoints et relatifs,
déplacement de dossier et réouverture d'un projet, pool indisponible, rendu,
icônes et packaging. Aucune requête IGN n'a été nécessaire.

La recette Desktop utilise **LiDAR 0.1.2** et le ZIP existant
**SIG-Prestations 0.7.31**. Elle contrôle les deux boutons visibles avec icône
seule, l'absence de doublons, le déchargement/rechargement de chaque plugin,
l'absence de sous-menu Extensions, les clics sur deux couches polygonales,
le prédiagnostic de deux blocs en cache, l'extraction, Turbo/Updated Canvas,
la fermeture automatique, la réouverture à zéro et la réouverture du projet
après suppression du cache de test. Résultats `ok=true` dans les deux processus.
La vérification ponctuelle de mise à jour a reproduit l'ancien menu 0.1.1,
constaté sa suppression par son `unload()`, puis chargé 0.1.2 sans recréer ce menu.

Le premier contrôle Desktop consultait la visibilité avant l'exécution du timer
de fermeture. Le lanceur de recette attend désormais les tours de boucle Qt
nécessaires à la fermeture différée. La recette finale passe sans imposer une
fermeture dans le test avant de vérifier ce comportement.

## Affichage et captures locales

Écran virtuel 1600 × 1000 pixels physiques, Qt 5.15.13 sous Ubuntu 24.04.5 :

| Échelle | Taille logique du dialogue | Diagnostic/progression | Défilement |
| --- | --- | --- | --- |
| 100 % | 820 × 599 | 14 px | aucun |
| 150 % | 820 × 599 | 14 px | aucun |
| 200 % | 760 × 452 | 14 px | vertical, sans défilement horizontal |

Les deux colonnes et les trois commandes sont visibles aux trois échelles.
À 200 %, le bas du prédiagnostic s'atteint par défilement ; au bas de la zone,
l'espacement jusqu'à la progression reste de 14 pixels logiques.
Les dimensions tiennent compte des retours à la ligne du diagnostic.

Captures et résultats locaux, **non versionnés** conformément à `AGENTS.md` :

- `audits/lidar-plugin-03/dialog-scale-1.png`, `dialog-scale-1.5.png`, `dialog-scale-2.png` ; mesures JSON associées.
- `audits/lidar-plugin-03/desktop/prediagnostic.png`, `toolbar.png`, `raster.png` et `result.json`.
- `audits/lidar-plugin-03/desktop-update/result.json`, `menu-update.json`.
- `audits/lidar-plugin-03/tests-qgis-3.34.log`, `tests-qgis-3.40.log`, `tests-qgis-3.44.log`.

Ces essais ne valident pas Windows. La recette Windows doit encore vérifier
installation du ZIP, facteurs DPI 100/150/200 %, fermeture et réouverture,
dialogue maintenu après erreur/annulation, menu absent après mise à jour et
redémarrage, et présence des deux boutons avec le SIG-Prestations courant.

## Reproduction et API

Depuis la racine, avec le Python fourni par QGIS :

```sh
python3 LiDAR/build_plugin.py
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover -s LiDAR/tests -v
```

La commande Desktop, le profil Processing et les prérequis sont décrits dans
`LiDAR/README.md`. Réutiliser le ZIP SIG-Prestations courant s'il existe ; ne pas
le reconstruire pour ce chantier. Pour vérifier une autre échelle de la géométrie
avec le test existant :

```sh
PYTHONPATH=LiDAR/tests QT_QPA_PLATFORM=xcb QT_SCALE_FACTOR=2 \
QT_ENABLE_HIGHDPI_SCALING=1 xvfb-run -a -s '-screen 0 1600x1000x24' \
/usr/bin/python3 -m unittest \
test_plugin.PluginTests.test_dialog_two_parameter_columns_and_full_width_controls -v
```

API concernées : layouts Qt (`totalHeightForWidth`, `sizeHint`, `QScrollArea`),
`QDialog.screen().availableGeometry()`, timers Qt possédés par le dialogue,
`QgsRasterLayer.isValid()`, retour de `QgsProject.addMapLayer()` et de
`iface.setActiveLayer()`. Elles sont exercées sur les trois runtimes Linux.
Les noms d'énumérations Turbo et les statistiques restent gérés par
`rendering.py`, inchangé ; inventaire complet dans `LIDAR-PLUGIN-01.md`.
Les chemins des sources VRT sont résolus par `pathlib`, sans convention Linux
ajoutée au code du plugin.

## Livraison

- Sources : `LiDAR/lidar_hd_2026/`, métadonnées **0.1.2**.
- ZIP généré localement : `plugin/dist/lidar_hd_2026-0.1.2.zip`.
- Manifeste fermé de **11 fichiers**, SVG et PNG inclus, chaque contenu identique
  aux sources actuelles ; archive reproductible contrôlée par les tests.
- SHA-256 : `ed23d4f5dddea37cb20e0ff525ec3e1e55f3c9ef262ab013d6d9bb80bca0fd53`.
- Le ZIP et les captures restent des artefacts locaux ignorés par Git ; les
  sources, tests, instructions et ce rapport permettent de reproduire la livraison.
- Commit et push sur `development` autorisés explicitement par la dernière
  instruction utilisateur ; seules les modifications LIDAR-PLUGIN-03 sont incluses.
