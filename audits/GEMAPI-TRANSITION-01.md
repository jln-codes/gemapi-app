# GEMAPI-TRANSITION-01 — Intégration standard et préparation SIRS

Transition du 19 novembre 2026. Environnement de recette : Ubuntu 24.04.5 LTS,
QGIS 3.44.15-Solothurn. Le chantier LIDAR-EXTRACT-01 est inclus dans la séquence,
avant la création de SIRS. Aucun nouveau développement SIRS.

## État Git initial

| Référence | Tête initiale |
| --- | --- |
| `development`, `origin/development` | `ae297c0493c893563cfc6bd1f0af63d559682225` |
| `dystopic`, `origin/dystopic` | `1caa2ac6592fa6dbc7d6269305e33299af8d6e03` |
| `main` locale | `389331b6e0d7a0e63b98d30c090958d3dcce0462` |
| `origin/main` | `70b2d8b9e20a9bc0280edde2652374dfd9054b7a` |
| Base commune development/dystopic | `70b2d8b9e20a9bc0280edde2652374dfd9054b7a` |

Les branches avaient divergé : quatre commits propres à development, dont la
bibliothèque LiDAR/VRT global, et dix propres à Dystopic. Aucun fast-forward
possible entre elles. La main locale était également en retard sur origin/main.

Le worktree principal contenait une modification non committée de `TODO.md`
(ligne NULLABLE), conservée hors des commits. Le worktree Dystopic était propre.
Tous les fichiers locaux ignorés/non suivis ont été copiés avant les opérations,
avec contrôle SHA-256 ; `TODO.md` a été sauvegardé puis mis temporairement de côté
par un stash limité à ce fichier. La clé n’a jamais été placée dans un stash.

## Historique de l’intégration

1. `a9d07a7` : fusion réelle de Dystopic dans development, parents `ae297c0`
   et `1caa2ac`, avec restauration de l’identité standard et migration du chemin
   de clé. Les deux historiques sont conservés.
2. `7b39e59` : qualification des parcours actuels et correction des bancs devenus
   périmés ; chemins de documentation et compte rendu QGIS actualisés.
3. Extraction LiDAR depuis la version intégrée : subtree
   `ce9f8e04523a537b869feef02b7ef11edbb93d3f`, onze commits pertinents.
   Le dépôt autonome est publié au commit technique `327a4ed`, puis reconstruit
   depuis un clone GitHub neuf avant tout retrait de la source.
4. `04d697ce87d409c2d87acfaec4a6e076022683d1` : retrait de `LiDAR/` de
   GEMAPI-App et documentation du dépôt indépendant. Les fichiers locaux ignorés
   de ce dossier sont déplacés dans la sauvegarde privée.
5. Main est avancée sur development par **fast-forward**, puis les deux branches
   sont publiées. Les anciens commits de development, y compris les chantiers
   modèle/QGIS déjà présents avant cette transition, restent dans leur historique.
6. Retrait du worktree Dystopic sans `--force`, renommage du dossier principal,
   création/publication de `sirs` depuis main nettoyée. Le présent rapport est
   ensuite reporté par fast-forward sur main et sirs ; les trois têtes sont égales.

Aucun rebase, réécriture d’historique ou push forcé. La branche distante Dystopic
est conservée comme référence historique, ainsi que sa branche locale.

## Conflits résolus fichier par fichier

| Fichier en conflit | Résolution retenue |
| --- | --- |
| `plugin.py` | Toolbar persistante, navigation et focus communs conservés ; conversation et renouvellement des brouillons intégrés ; identité standard. |
| `creation.py` | Préremplissage vérifié en lecture seule ajouté au formulaire courant ; contraintes métier conservées ; indicateur privé renommé `_assistant_draft`. |
| `home.ui` | Overlay compact courant, cinq boutons avec Assistant IA avant Aide ; titre standard. |
| `metadata.txt` | Prestations DMNR, icône normale, version 0.8.0. |
| `window_geometry.py` | Ancrage au canevas à droite et tailles communes conservés ; taille initiale de l’assistant ajoutée. |
| `help.md` | Documentation de l’assistant intégrée à l’aide standard ; références visuelles expérimentales retirées. |
| `tools/build_plugin.py` | Un package standard, manifeste fermé, copie binaire des sources sans transformation de namespace. |
| `tests/smoke_import.py` | Union des stubs Qt nécessaires et attentes d’identité standard. |
| `tests/test_home_layout.py` | Cinq boutons et voisin Qt indépendant pour la barre ; aucune importation LiDAR. |
| `tests/test_qgis_runtime.py` | Parcours conservés, cinq boutons et libellés standard. |
| `audits/QGIS-UX-FOCUS-01.md` | Résultats historiques des deux branches préservés, complétés par la qualification intégrée. |

Le contenu LiDAR de development a été vérifié inchangé après la fusion. Le
`.gitignore` existant et son exclusion de clé sont conservés ; seules les
exceptions des deux rapports demandés sont ajoutées.

## Identité et architecture finales

- Nom QGIS et menu : **Prestations DMNR**.
- Identifiant et package : **`sig_prestations`**.
- Icône principale : **`icons/icon.png`**, action cochable ; convention de barre
  `SIGMilieuxToolbar`, titre SIG-Milieux, partagée avec le LiDAR indépendant.
- Version standard : **0.7.35 → 0.8.0**. La numérotation de l’ancien package
  expérimental distinct ne constitue pas celle du plugin standard.
- Le marqueur `experimental=True` déjà présent sur la branche standard est
  conservé ; cette livraison ne déclare pas une qualification Windows générale.
- Accueil : Créer une prestation, Gérer les prestations, Éditer un rapport,
  **Assistant IA**, Aide. Police conservée, panneau enfant du canevas, à droite.

L’assistant reste constitué des trois modules `assistant.py`,
`assistant_dialog.py` et `voice.py`. Mistral interprète les champs et la description
dans une seule réponse structurée. Python résout les références réelles et valide
les propositions. Le formulaire standard prérempli reste l’unique lieu de
sauvegarde humaine ; `record.py` et ses contraintes ne sont pas modifiés.

Mistral Small, Voxtral, l’historique, les corrections groupées, les priorités
exacte/normalisée/phonétique, les trois familles autorisées avec géométrie propre
NULL et les confirmations d’abandon sont conservés. Les réponses tardives des
requêtes annulées ne contaminent pas le nouveau brouillon. Après sauvegarde,
l’assistant prépare un nouveau brouillon et garde l’historique visible.

Le focus cartographique et les caches restent ceux du processus standard :
actualisation ciblée, formulaire masqué, géométrie effective de la prestation,
transformation de SCR et retour au panneau, sans déchargement du plugin.

Principaux fichiers concernés : modules/interface/métadonnées/aide du plugin,
constructeur et tests sous `plugin/`, README racine et plugin, `.gitignore`,
`CABBALR_ACCES.md`, audits. `PHRASES_TESTS.txt` et les audits Dystopic sont intégrés
sans perdre leur provenance. Les 22 fichiers suivis de `LiDAR/` sont transférés
au dépôt autonome avant leur retrait. Aucun changement nouveau dans `model/`,
`demo/` ou `cabbalr/` par rapport à development initial.

## Clé, configuration et installations QGIS

La clé existante est conservée dans le dossier principal
`gemapi-app/MISTRAL_API_KEY.txt`, en permissions 0600, ainsi que dans la sauvegarde
privée. Son exclusion Git et son absence des deux ZIP sont vérifiées avec sa
valeur réelle, sans l’afficher. Aucun fichier de ce nom dans l’historique suivi.

Préférence courante : `sig_prestations/mistral_key_path`. Un chemin expérimental
encore valide est repris par le plugin ; un ancien chemin disparu laisse le
chargement standard demander un fichier valide. Le choix explicite du profil
prime sur `SIG_PRESTATIONS_MISTRAL_KEY_PATH`, puis sur l’ancienne variable de
chemin encore reconnue pour la transition. Aucun secret stocké dans les préférences.

Le profil QGIS local fermé a été sauvegardé avant mise à jour. Les anciennes
installations correspondaient exactement à leurs ZIP connus : standard 0.7.35,
expérimentale 0.10.0 et LiDAR 0.1.2. Le profil reçoit désormais standard 0.8.0 et
LiDAR 0.1.3, tous deux activés. Le dossier expérimental est retiré de l’installation
active et conservé dans la sauvegarde privée. Le chemin de clé est configuré sous
le préfixe standard ; quatorze préférences de chemins locaux sont réancrées vers
les nouveaux dossiers. Les paramètres de connexion PostgreSQL sont contrôlés
identiques avant/après ; le stockage d’authentification QGIS reste en place.

L’utilisateur a fermé sa session QGIS avant les opérations de retrait. Les anciens
processus QGIS/tests résiduels ont été arrêtés ensuite ; aucun enregistrement en
base n’a été déclenché. Les fichiers des projets Démo/CABBALR sont identiques à
l’état initial de development et ne contiennent pas l’ancien chemin absolu.

## Tests et résultats

| Contrôle | Résultat |
| --- | --- |
| Assistant, extraction simulée, descriptions, résolution et UI Qt | 69 tests réussis, dont le banc linguistique ; aucun appel Mistral obligatoire. |
| Dictée/transport Voxtral simulés | 19 tests réussis. |
| Accueil, police, navigation, barre, absence de doublons | 6 tests réussis, puis de nouveau après retrait de LiDAR. |
| Focus et cycle de vie création/édition | 12 tests réussis, géométries propres/héritées, SCR, annulation/échec et caches. |
| Archive standard installée | Test réussi avant/après extraction et depuis un clone GitHub propre. |
| Résolveur après renommage | 36 tests réussis. |
| Métier, capture, cache, performances, types, PDF, gestion, édition et sections AH | 20 pilotes complémentaires exécutés ; les parcours pertinents passent après actualisation de leurs fixtures. |
| Intégration assistant sur PostGIS jetable et ZIP installé | Absence d’écriture avant validation, puis sauvegarde explicite par le formulaire sur les trois familles, géométries NULL. |
| Gestion/édition réelles sur PostGIS jetable | Sauvegarde, conflits de version, rollback, géométries, liens, réouverture et conservation des filtres validés. |
| Rapports PDF | Worker isolé, progression, erreurs/annulation et suite d’intégration PDF réussis. |
| Digues / sections AH | Projet courant à 26 couches, rendu et 14 validations AH natives réussis. |
| Deux extensions | Plugins seuls, deux ordres, retrait de chacun, réactivation sans doublon, dans le banc Qt et QGIS Desktop réel. |
| QGIS Desktop 3.44.15 / X11 virtuel | Huit contrôles réussis : barre vide, plugins seuls, overlay à droite, cinq boutons, assistant/historique et permutations. |
| LiDAR autonome | 53 tests, 4 du script de référence, benchmark synthétique, recette Desktop et clone propre réussis. |

Réouverture du formulaire : environ 56 ms après création et 46 ms après édition
dans le banc Qt à SQL simulé ; ces mesures ne constituent pas un benchmark du
poste utilisateur. Les tests de cache et les parcours PostGIS confirment la
réutilisation de la session et des référentiels sans rechargement général.

Les premiers essais ont révélé des attentes de tests périmées : ancien nom
expérimental, faux SQL sans permissions/sections AH, projet supposé à 25 couches,
formulaire supposé détruit et gestionnaire réaffiché automatiquement. Les tests
ont été alignés sur le modèle et le cycle de vie actuels. L’import installé est
isolé des classes Qt source et ses widgets sont libérés avant l’arrêt QGIS.
Un délai global de 240 s trop court pour les exports PDF successifs a été relevé
pour le second essai, réussi. Les échecs initiaux restent dans les journaux locaux.

Les deux clones propres reproduisent exactement leurs ZIP :

| Archive | Fichiers runtime | SHA-256 |
| --- | --- | --- |
| `plugin/dist/sig_prestations-0.8.0.zip` | 38 | `008dbd100b887fa608e55f589a94c481c9f10d4a5d174181f17ab509bfa0358e` |
| `dist/lidar_hd_2026-0.1.3.zip`, dépôt LiDAR | 11 | `7486e62b4d6e74f4da8d055088d098829338d32f6d1ade27fca17ea7c3518fd2` |

Les logs, JSON et captures sont locaux sous `audits/`, hors Git. Aucune écriture
sur les bases permanentes CABBALR/Démo/Supabase ; les écritures de tests concernent
uniquement des instances PostGIS jetables et des validations explicites du formulaire.

## État GitHub et espaces finaux

Au début du chantier, l’API GitHub renvoyait déjà **jln-codes/gemapi-app**, y compris
pour l’ancienne URL sig-prestations, avec le même identifiant `1436767178`.
Le renommage distant était donc déjà effectif. Origin est actualisé en HTTPS,
protocole conservé. La branche par défaut reste main ; les droits de lecture,
écriture et administration sont vérifiés. Les pushes sont vérifiés par les refs
distantes et les reconstructions depuis GitHub.

| Espace | Branche / état final |
| --- | --- |
| `/home/julien/Projects/gemapi-app` | development, session de développement principale ; modification locale TODO rétablie hors commits. |
| `/home/julien/Projects/gemapi-app-sirs` | sirs, même contenu intégré/nettoyé que main ; worktree propre. |
| `/home/julien/Projects/qgis-lidar-fr` | dépôt indépendant, main publiée ; worktree propre. |
| Ancien worktree sig-prestations-dystopic | retiré par `git worktree remove`, sans force. |

`main`, `development` et `sirs` ont le même contenu applicatif et sont synchronisées
avec le commit final de ce rapport. `dystopic` et `origin/dystopic` restent sur
`1caa2ac`, ancêtre de main. La branche distante historique
`chantier-selecteur-types-hierarchique` (`8e0dcd4`) est également conservée.
Le rapport [LIDAR-EXTRACT-01](LIDAR-EXTRACT-01.md) référence la publication autonome.

Sauvegarde privée, hors dépôt et protégée :
`/home/julien/Projects/gemapi-app-local/GEMAPI-TRANSITION-01/`.
Elle contient les fichiers initiaux non suivis/ignorés, les manifests de contrôle,
la copie finale des 80 fichiers locaux Dystopic, la clé, le patch TODO, les métadonnées
du worktree retiré et les anciennes installations/configuration QGIS. Les anciens
ZIP LiDAR du dossier de distribution principal y sont conservés. Les branches et
l’historique Git restent le moyen de retrouver les anciennes sources.

## Synchronisation de la deuxième machine

Aucun accès à la deuxième machine n’est supposé. Fermer QGIS après avoir traité
ses modifications et travailler depuis le dossier parent des dépôts. Avant toute
suppression, copier tous les fichiers locaux nécessaires, y compris les fichiers
ignorés, dans un dossier privé extérieur aux worktrees. Vérifier leur copie ;
conserver la clé hors Git pendant toute l’opération.

1. Examiner `git status --short` dans les deux worktrees et `git worktree list`.
   Préserver les modifications suivies par copie/patch ou stash limité aux fichiers
   explicitement choisis. Ne pas utiliser `stash -a` pour les secrets ignorés.
2. Actualiser origin en gardant son protocole existant, puis récupérer les refs :

   ```sh
   # Si le remote utilisait HTTPS :
   git remote set-url origin https://github.com/jln-codes/gemapi-app.git
   # S’il utilisait SSH, choisir cette variante à la place :
   # git remote set-url origin git@github.com:jln-codes/gemapi-app.git
   git fetch origin
   git switch development
   git merge --ff-only origin/development
   git switch main
   git merge --ff-only origin/main
   git switch development
   ```

   En cas de divergence ou de modification bloquante, arrêter et examiner les
   commits ; aucune réinitialisation forcée. Vérifier `git log origin/main..dystopic`
   et sauvegarder toute correction locale supplémentaire avant de retirer ce worktree.
3. Vérifier la conservation des fichiers ignorés, particulièrement la clé. Lorsque
   le worktree expérimental est propre et ses commits intégrés, exécuter
   `git worktree remove ../sig-prestations-dystopic` sans force. Ne pas supprimer
   sa branche distante. Conserver les fichiers privés à l’extérieur jusqu’au renommage.
4. Depuis le parent, renommer le dossier principal : sous Ubuntu,
   `mv sig-prestations gemapi-app` ; sous PowerShell,
   `Rename-Item -LiteralPath .\sig-prestations -NewName gemapi-app`.
   Puis entrer dans gemapi-app et lancer `git worktree repair`.
5. Vérifier `git check-ignore MISTRAL_API_KEY.txt`, remettre le fichier privé
   dans ce dossier si souhaité, puis sélectionner son nouveau chemin dans
   **Fichier de clé Mistral…**. Restaurer les modifications locales choisies
   après contrôle des conflits ; ne pas les inclure dans un commit du chantier.
6. Préparer SIRS à partir de la branche publiée :

   ```sh
   git worktree add --track -b sirs ../gemapi-app-sirs origin/sirs
   git worktree list
   ```

   Si sirs existe déjà localement, vérifier son état, utiliser
   `git worktree add ../gemapi-app-sirs sirs`, puis avancer ce worktree par
   fast-forward sur origin/sirs. Le dossier principal reste sur development.
7. Cloner séparément `https://github.com/jln-codes/qgis-lidar-fr.git` dans le
   dossier adjacent qgis-lidar-fr. S’il existe déjà, fetch et fast-forward sa main.
   Construire les deux ZIP avec leurs outils indépendants, puis les installer
   dans QGIS. Sous Windows, employer le Python fourni avec QGIS :
   `python plugin/tools/build_plugin.py` et, dans LiDAR, `python build_plugin.py`.
8. Après sauvegarde de ses éventuels fichiers locaux, retirer l’ancienne extension
   expérimentale de QGIS. Garder l’unique **Prestations DMNR**, plus le LiDAR
   indépendant. Ouvrir le projet depuis son nouveau chemin et vérifier les deux
   icônes, l’accueil et la sélection de clé. Ne pas modifier les paramètres de
   connexion Supabase/CABBALR ni déplacer la bibliothèque LiDAR permanente.

## Réserves et lancement

Sur ce poste, rouvrir QGIS puis le projet Démo ou CABBALR depuis gemapi-app.
Cliquer l’icône habituelle **Prestations DMNR**, puis **Assistant IA**.
L’accueil est un overlay du canevas ; ouvrir le projet pour quitter la page
QGIS des projets récents. La clé locale est déjà configurée dans le profil mis à jour.

Windows natif reste à qualifier avant une diffusion générale, ainsi que les
périphériques audio et le partage SMB réels. Les recettes Desktop effectuées sont
automatisées sous Linux ; aucun nouveau test humain, microphone, Mistral ou Voxtral
réel pendant cette transition. Les résultats linguistiques réels antérieurs et
leurs échecs/ambiguïtés restent décrits dans DYSTOPIC-02 ; la transition conserve
ces limites sans prétendre améliorer le modèle. Aucun nouveau schéma ou donnée
PostgreSQL permanente n’est déployé.


## Complément du 20 novembre 2026 — identité GEMAPI-App 0.8.1

À la demande de l’utilisateur, la nouvelle distribution est désormais
`plugin/dist/gemapi-app-0.8.1.zip`, avec le package Python/QGIS **`gemapi_app`**
et le nom affiché **GEMAPI-App**. Menus, fenêtres, aide, messages et signatures
PDF sont adaptés. Les anciennes archives et les descriptions historiques des
versions précédentes conservent leurs noms et leur contenu.

Le dossier source devient `plugin/gemapi_app/`. Les imports, le widget Qt promu,
le worker PDF, les commandes d’actions cartographiques et les tests utilisent
ce namespace. Les dix références Python de chacun des deux projets QGIS sont
actualisées ; tous les autres octets XML sont vérifiés inchangés par substitution
inverse, et les tests de synchronisation contrôlent les connexions et relations.
Aucune table, donnée ou contrainte PostgreSQL modifiée. `record.py` reste identique
à celui de 0.8.0 ; ses marqueurs de transaction sont conservés.

Le constructeur distingue le nom d’archive `gemapi-app` du package `gemapi_app`.
Le manifeste reste fermé à 38 fichiers runtime. Aucun module relais sous
l’ancien nom. Le profil QGIS local fermé est sauvegardé puis reçoit gemapi_app ;
les anciennes installations sont retirées du dossier actif, et leur configuration
de clé est reprise sous `gemapi_app/mistral_key_path`. Les variables avancées
existantes sont conservées ; le nouveau chemin d’environnement Mistral accepte
aussi les anciens préfixes pour reprendre les configurations existantes.

La recette QGIS Desktop 3.44 sous X11 virtuel passe les huit contrôles du plugin
seul et avec LiDAR, dans les deux ordres. Les tests d’archive installée, assistant,
voix, accueil, focus, validations, chemins photo/PDF, synchronisation des projets,
parcours Qt et processus PDF passent. Le parcours assistant installé sur PostGIS
jetable confirme le préremplissage et la sauvegarde explicite des trois familles.
Les archives SIG antérieures sont contrôlées identiques à leurs empreintes
précédentes. La clé est absente du nouveau ZIP ; TODO.md local reste préservé
hors commit. Windows natif reste à valider.

Le profil local est prêt pour la prochaine ouverture QGIS. Sur l’autre machine,
installer ce nouveau ZIP, désactiver/retirer sig_prestations après sauvegarde de
ses éventuels fichiers locaux, et activer **GEMAPI-App**. Les projets versionnés
actualisés utilisent gemapi_app ; actualiser les commandes Python de ses copies
locales personnelles si elles importaient encore l’ancien package. Les anciennes
versions distribuées ne sont pas renommées.
