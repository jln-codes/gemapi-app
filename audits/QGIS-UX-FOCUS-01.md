# QGIS-UX-FOCUS-01 — Accueil compact et retour à la carte

## Architecture

Évolution commune réalisée sur `development`, à reporter sélectivement sur
`dystopic`, sans fusion intégrale. Aucun schéma ni aucune donnée PostgreSQL modifiés.

`CompactHomePositioner` installe le `QWidget` d’accueil comme enfant direct du
canevas (`Qt.Widget`), sans décoration système ni fenêtre supplémentaire.
Le layout à une colonne garde la police native : boutons 31 px, espacement 4 px,
marges intérieures 6 px, fond de palette et bordure fine. Le panneau est ancré à
10 px du coin supérieur droit, suit le redimensionnement et le changement d’écran
avec son parent. Aucun déplacement manuel ni interception des clics hors du panneau.
Ordre standard : Créer une prestation, Gérer les prestations, Éditer un rapport, Aide.

Le plugin centralise le masquage des fenêtres fonctionnelles. Les confirmations
d’abandon restent dans le formulaire. Une sauvegarde émet `saved(UUID)` après
réussite SQL seulement. Le formulaire est masqué et protégé contre un second envoi.
L’accueil revient au tour suivant de la boucle Qt, après le focus cartographique.
La session PostgreSQL et les caches de référentiels/patrimoine restent en mémoire.
L’invalidation concerne les prestations et le filtre des années ; la gestion
actualise ses résultats sans reconstruire toutes ses listes.

Le formulaire sauvegardé peut être réutilisé : une nouvelle création le réinitialise
au clic explicite ; une édition relit la fiche, ses associations et sa version.
Un changement de connexion remplace uniquement cette instance périmée.

`prestation_focus.py` lit `milieux.prestations_carte` par UUID vérifié, copie sa
géométrie et la transforme vers le SCR du canevas. Points, lignes, polygones et
multiparties utilisent une emprise augmentée de 30 %, avec une taille minimale
pour les points. La vue canonique gère les géométries propres et héritées des
ouvrages, stockages et zones ; tous les rattachements standard restent autorisés.
Sans géométrie ou si la transformation échoue, l’emprise est conservée et un
message non bloquant apparaît. Aucune surbrillance temporaire ajoutée.

## Validation

QGIS/PyQt natifs 3.44.15 sous Ubuntu, SQL simulé exclusivement :

- 12 tests de focus et cycle de vie : création, édition, sept familles, six types
  géométriques, SCR différents, géométrie absente, annulation, conflit/erreur,
  actualisation ciblée et réutilisation des instances/caches.
- 4 tests d’accueil : ordre, dimensions, police, absence de fenêtre native, ancrage
  après déplacement/redimensionnement (origine négative comprise), interactions
  cartographiques hors du panneau.
- Test de parcours QGIS global : capture, géométries, navigation, sauvegardes
  simulées successives, abandon confirmé, gestion et rapports.
- Réouverture mesurée lors de la dernière exécution : création 11,43 ms,
  édition 42,44 ms (Qt natif avec SQL simulé ; aucune promesse de latence réseau).

Un premier lancement QGIS Desktop 3.44.15 avec profil temporaire isolé avait
confirmé le focus d’une ligne et la police 10 pt de la palette. Cette palette est
remplacée par le panneau enfant demandé dans le complément UX ; les tests et
les tests natifs sont réussis sur le panneau intégré. Deux nouveaux lancements
Desktop ont dépassé le délai de démarrage ; la vérification visuelle finale de
ce panneau reste à confirmer si le lancement isolé ne peut pas aboutir. La connexion est simulée ; aucune prestation
n’a été enregistrée. Les captures demandées restent locales et hors Git.

Les 9 tests de capture et les 10 tests de validation métier passent également.
Le parcours de gestion/édition/suppression UI passe avec transactions simulées.

Les tests de packaging reconstruisent un ZIP déterministe, comparent son manifeste
et son contenu aux sources et vérifient son import depuis un profil temporaire.

## Lancement et limites

Installer le ZIP de `plugin/dist/` dans QGIS 3.44 puis ouvrir le plugin.
L’accueil compact s’affiche immédiatement. Après une sauvegarde humaine, la carte
et l’accueil permettent d’enchaîner une saisie ou de revenir au gestionnaire.

Une validation Windows et un essai de sauvegarde humaine en base de recette
restent nécessaires. Aucun enregistrement réel n’a été effectué pendant ces tests.

## Adaptation Dystopic

Le commit commun est reporté sélectivement, en conservant Mistral, Voxtral,
la distribution expérimentale distincte et ses validations. L’ordre est :
Créer, Gérer, Rapport, Assistant IA, Aide. Le bouton Assistant IA est sans icône.
L’assistant masque l’accueil. Son formulaire prérempli masque l’assistant ;
une annulation confirmée restaure la même conversation. Fermer l’assistant
revient au panneau. Une sauvegarde humaine masque l’assistant et le formulaire,
centre la carte et réaffiche le panneau sans perdre l’historique.

## Action principale à état persistant

L’action principale est cochable. Le premier clic affiche le panneau ; le
second masque les interfaces sans fermer ni réinitialiser les brouillons.
Le clic suivant restaure l’interface précédente si elle existe encore. Les
événements Show/Hide/Close synchronisent l’état coché sur la visibilité réelle,
y compris lors des captures cartographiques et des sauvegardes. Le panneau
ne possède pas de bouton de fermeture. Aucun déchargement ni vidage de cache.
Tests : état coché et différence de pixels dans les styles Qt disponibles sous Ubuntu, masquage
et restauration d’une saisie modifiée, conservation des objets de session/cache.
Ces styles Qt ne constituent pas une validation du système Windows ; celle-ci
reste requise avec QGIS 3.44 sur Windows.

Livrable standard : `plugin/dist/sig_prestations-0.7.35.zip`.

## Contrôles finaux

36 tests unitaires/natifs réussis (accueil 4, focus/cycle de vie 12, validation
métier 10, capture 9, ZIP 1), plus les deux scripts de parcours QGIS et de gestion
avec transactions simulées. Les styles Qt Fusion et Windows sous Ubuntu affichent
un rendu distinct de l’icône cochée ; Windows natif reste à tester.
Le panneau standard est vérifié comme enfant du canevas, sans fenêtre système,
ancré à 10 px à droite. Une capture locale du banc Qt/PyQGIS complète les tests
mais ne remplace pas une recette Desktop. Le lancement Desktop final a dépassé
le délai puis l’accès à DISPLAY :0 s’est révélé indisponible dans ce contexte.

Le ZIP 0.7.35 contient 35 fichiers runtime strictement conformes aux sources.
La valeur réelle de la clé Mistral locale du worktree expérimental a également
été recherchée : absente des fichiers suivis et du ZIP standard. Aucun schéma
ni aucune donnée PostgreSQL modifiés ; TODO.md préexistant laissé hors des commits.
## Résultats finaux Dystopic 0.10.0

- 93 tests unitaires/natifs réussis : assistant 24, banc linguistique 4
  (34 variantes métier et 4 cas de description), conversation/formulaire Qt 12,
  voix simulée 15, accueil 6, focus/cycle de vie 12, métier 10, capture 9, ZIP 1.
- Les scripts de parcours QGIS global et de gestion/édition/suppression UI passent
  également ; toutes les transactions y sont simulées, sans base réelle.
- Réouverture : création 10,50 ms, édition 34,23 ms dans le test Qt à SQL simulé.
- Test explicite assistant → formulaire → abandon refusé/confirmé → assistant,
  historique intact, masquage/restauration par l’icône, sauvegarde humaine simulée
  → carte/accueil, cache et session conservés. Un nouveau brouillon réutilise
  le formulaire sauvegardé après validation des références et réinitialisation ciblée.
- Les styles Qt Fusion et Windows disponibles sous Ubuntu montrent un rendu
  distinct pour l’icône cochée ; cela ne valide pas le système Windows.
- Capture du panneau réel dans un canevas Qt/PyQGIS isolé : 197 × 183 px pour
  un canevas de 600 × 380 px, position (393, 10), cinq boutons de 31 px.
  Police native du contexte de test : 12 pt, sans modification par le plugin.
  Aucun accueil parmi les fenêtres de premier niveau. Capture locale, hors Git.
- Le lancement Desktop final n’a pas abouti : deux délais dépassés, puis accès
  indisponible à DISPLAY :0. Le rendu capturé est celui du banc natif, et non
  une recette manuelle Desktop. Windows, plusieurs écrans physiques et une
  sauvegarde humaine en base de recette restent à valider. Aucun nouvel essai
  microphone réel réalisé dans ce chantier UX.
- ZIP expérimental : `plugin/dist/sig_prestations_dystopic-0.10.0.zip`,
  39 fichiers runtime, import depuis profil isolé avec le plugin stable présent,
  manifeste et octets conformes aux sources. Clé Mistral absente du ZIP et des
  fichiers suivis. ZIP standard : 35 fichiers runtime, même contrôle de conformité.

La description DYSTOPIC-03 et son essai Mistral réel (4/4) sont documentés dans
`audits/DYSTOPIC-02.md`. Aucun schéma ni aucune donnée PostgreSQL modifiés.


## Intégration standard — GEMAPI-TRANSITION-01

L’assistant fait désormais partie de **Prestations DMNR 0.8.0** dans l’unique
package `sig_prestations`. Le panneau conserve cinq boutons dans l’ordre Créer,
Gérer, Rapport, Assistant IA, Aide ; l’icône principale habituelle est cochable.
La distribution expérimentale distincte est retirée. Les résultats précédents
restent ci-dessus pour la traçabilité des deux branches.

La recette de transition confirme le panneau enfant du canevas, à 10 px en haut
à droite, sans fenêtre système ; la conversation, les caches et la session sont
conservés lors des changements de visibilité. Le banc de focus et réouverture
passe ses 12 tests, avec environ 46–56 ms dans le scénario à SQL simulé.
Les parcours de gestion, édition/concurrence et rapports sont également vérifiés
sur PostGIS jetable. Les anciens tests supposant un formulaire détruit et un
retour automatique au gestionnaire ont été adaptés au cycle de vie courant.

Une recette **QGIS Desktop 3.44.15 réelle, sous X11 virtuel**, confirme l’accueil
à droite, les cinq boutons, le masquage/restauration, l’historique de l’assistant
et la barre commune avec le LiDAR autonome dans tous les ordres d’activation.
Cette recette automatisée complète les tests Qt ; elle ne constitue pas une
recette humaine ni une validation Windows. Voir `GEMAPI-TRANSITION-01.md`.
