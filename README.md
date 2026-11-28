# GEMAPI-App

Dépôt : [jln-codes/gemapi-app](https://github.com/jln-codes/gemapi-app).
L'historique antérieur à la refonte du dépôt est conservé dans
[gemapi-app-legacy](https://github.com/jln-codes/gemapi-app-legacy).

Modèle patrimonial PostgreSQL/PostGIS v0.6.1, données de démonstration et plugin QGIS
**GEMAPI-App 0.8.6**, assistant Mistral, dictée et réponses vocales Voxtral facultatives
(QGIS 3.44 minimum).

## Organisation

```text
gemapi-app/
├── model/
│   ├── schema.sql             # unique schéma canonique
│   ├── schema.mmd
│   └── role.md                # matrice des rôles PostgreSQL
├── demo/
│   ├── data/                  # 15 imports SQL et importer_base_neuve.sh
│   ├── gpkg/                  # 8 GeoPackages
│   ├── prestations_demo.qgz
│   └── README.md
├── cabbalr/                   # données réelles, conservées intégralement
├── plugin/
│   ├── gemapi_app/       # package QGIS : modules, .ui, metadata.txt
│   │   ├── icons/             # icône actuelle de la barre d'outils
│   │   └── assets/logo_cabbalr.webp
│   ├── tests/
│   ├── tools/
│   │   ├── build_plugin.py
│   │   └── icons/             # sources graphiques historiques conservées
│   ├── dist/                  # ZIP du plugin standard, ignorés par Git
│   └── README.md
├── audits/                    # audits demandés ; sorties locales et dist/ ignorés
├── README.md
└── .gitignore
```

Le schéma et ses illustrations ont été déplacés depuis `demo/` vers `model/`.
Le diagramme Mermaid suit le schéma canonique actuel.
`cabbalr/schema.sql` reste une ressource historique
des données réelles ; il n'est pas le schéma canonique et n'est utilisé ni par
la démonstration ni par les tests. Aucun fichier de `cabbalr/` n'a été modifié.

Le projet du plugin est sous `plugin/` : code dans `gemapi_app/`, tests
dans `tests/` et construction dans `tools/`. Les sorties locales des tests
vont dans `audits/` à la racine. Aucun de ces déplacements ne nécessite de
migration des données métier.

## Utilisation

- [LiDAR HD 2026](https://github.com/jln-codes/qgis-lidar-fr) est développé, testé
  et distribué dans son dépôt autonome. Les deux extensions partagent seulement
  la barre QGIS **SIG-Milieux**, sans dépendance technique.
- Créer une base locale vide dédiée, puis exécuter
  `bash demo/data/importer_base_neuve.sh nom_base`. La démonstration et le plugin
  utilisent le schéma fixe `gemapi`. Renseigner le service libpq `gemapi_demo`
  et ouvrir `demo/prestations_demo.qgz`. [Guide de reconstruction](demo/README.md)
- Pour une installation neuve sans données fictives, exécuter `model/schema.sql`,
  puis attribuer les droits avec `model/roles_milieux.sql`. [Profils PostgreSQL](model/role.md)
- [Installer, utiliser et tester le plugin](plugin/README.md) : générer le ZIP
  avec `python3 plugin/tools/build_plugin.py`, puis installer
  `plugin/dist/gemapi-app-0.8.6.zip` dans QGIS.

Le ZIP standard embarque uniquement le package `gemapi_app/`, ses modules, les
interfaces Qt, l'icône et le logo institutionnel. Il n'embarque aucune donnée,
aucun schéma, test, outil ou rapport généré.

## Branches et synchronisation gemapi-app-sirs

`development` porte le socle courant ; `main` reçoit seulement les versions
validées, normalement par fast-forward. `gemapi-app-sirs` reçoit automatiquement chaque push
sur `development`, par fusion normale préservant ses propres commits. La production
n'intervient pas dans ce flux. Cette branche porte son modèle dans `model/schema.sql` et son plugin dans `plugin/`. Voir [AGENTS.md](AGENTS.md).

La branche spécialisée prépare le modèle destiné à être intégré dans `gemapi-dev`. Son archivage est prévu après cette intégration.

La branche spécialisée se nomme définitivement `gemapi-app-sirs`. Le worktree Ubuntu conserve
exactement son chemin `~/Projects/gemapi-app-sirs` ; seule sa branche est renommée
et suit `origin/gemapi-app-sirs`.

Avant une session SIRS sous Ubuntu, depuis n'importe quel répertoire :

```bash
python3 ~/Projects/gemapi-app/tools/git_gemapi_app_sirs.py update
```

Cette commande vérifie le worktree lié `~/Projects/gemapi-app-sirs`, sa branche
`gemapi-app-sirs` et sa propreté, récupère `origin`, puis avance uniquement par fast-forward.
Elle affiche le retard, la synchronisation ou la divergence et refuse les fichiers
modifiés/non suivis et les commits locaux non poussés, sans toucher aux fichiers.
Autre emplacement : `python3 tools/git_gemapi_app_sirs.py update --worktree CHEMIN`.
Prérequis : Python 3 et Git 2.31 ou ultérieur, avec accès à `origin`. Aucun service
résident n'est nécessaire ; GitHub ne peut pas mettre à jour un ordinateur hors ligne.

Le workflow [sync-gemapi-app-sirs.yml](.github/workflows/sync-gemapi-app-sirs.yml) sérialise les exécutions,
récupère les pointes récentes et retente une fusion si un push concurrent sur `gemapi-app-sirs`
refuse la publication. Il teste les mécanismes Git avant publication, puis contrôle
l'ascendance, l'identité d'`AGENTS.md` et l'absence de fichiers du socle supprimés
par SIRS sous `demo/`, `cabbalr/` et `plugin/`. Il vérifie ensuite réellement :

```bash
git fetch origin
git merge-base --is-ancestor origin/development origin/gemapi-app-sirs
```

Un conflit échoue visiblement, affiche les fichiers et laisse la branche distante
SIRS inchangée. Dans un worktree SIRS propre, récupérer `origin`, lancer
`git merge origin/development`, résoudre chaque conflit en préservant les deux
développements, tester, committer et pousser `gemapi-app-sirs`. Ne pas utiliser de choix global
`ours`/`theirs`, de force-push ou de réinitialisation. Relancer ensuite l'exécution
en échec depuis GitHub Actions. Le déclenchement manuel `workflow_dispatch` ne sera
disponible dans l'interface qu'après arrivée du workflow dans la branche par défaut
`main` ; le déclenchement par push fonctionne directement depuis `development`.

La variable de dépôt `SIG_FUSION_SYNC_MODE` conserve son nom et sa valeur lors du renommage.
Le groupe de concurrence `development-to-sig-fusion` et les noms de contrôles
`sync-sig-fusion-direct`, `sync-sig-fusion-protected` et `branch-policy` restent stables
pour les exécutions en cours et les règles GitHub existantes.

Les trois branches étaient sans protection ni ruleset lors du contrôle
GIT-SIG-FUSION-01. Le mode par défaut est donc le push direct avec seulement
`contents: write` pour le job de publication. Si une protection de `gemapi-app-sirs` exige une
PR, définir la variable de dépôt `SIG_FUSION_SYNC_MODE=pull-request`, autoriser la création
de PR par Actions et l'auto-merge dans les paramètres du dépôt, puis rendre le
contrôle `branch-policy` obligatoire sur `gemapi-app-sirs`. Autoriser les commits de fusion :
un squash ou rebase ne satisfait pas la relation d'ancêtre attendue. Ce mode ajoute
seulement au job PR la permission `pull-requests: write`, réutilise une PR
`development → gemapi-app-sirs` et demande une intégration conditionnelle sans contournement
administrateur. Une PR encore ouverte produit un échec explicite « en attente » ;
après son intégration, relancer l'exécution pour confirmer l'état distant.
Ce mode doit être qualifié avec les protections réellement configurées avant usage.

Un push effectué avec `GITHUB_TOKEN` ne déclenche normalement pas les workflows
`push` suivants : les contrôles de synchronisation sont donc exécutés avant le push.
Pour les PR créées par ce jeton, prévoir les éventuelles approbations de workflows
demandées par GitHub ; ne jamais contourner des contrôles obligatoires bloqués.
Voir la [documentation GitHub sur les déclenchements](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
Aucun jeton personnel n'est nécessaire.

Le workflow [branch-policy.yml](.github/workflows/branch-policy.yml) refuse les PR
`gemapi-app-sirs → development/main`, l'ascendance spécifique SIRS même depuis une autre
branche et les changements sous `sirs/` visant le socle. Les commits communs de
`development` hérités par SIRS restent autorisés vers `main`.
Pour bloquer avant fusion, rendre `branch-policy` obligatoire sur `development` et
`main`, imposer les PR et interdire les contournements ainsi que les pushes directs.
Cette proposition de protection modifie le travail direct sur `development` : elle
nécessite une décision de gouvernance et n'est pas activée par ce chantier.
Sans elle, le contrôle des pushes ne fait qu'alerter après publication. Les
administrateurs et les cherry-picks/réécritures hors `sirs/` restent des limites :
Git ne peut pas déduire automatiquement la nature métier d'un changement. Une
revue des modifications des workflows et outils de contrôle est également nécessaire.
`main` conserve son état jusqu'à une livraison autorisée ; les nouvelles instructions
et les workflows y seront installés lors de cette intégration, pas par ce chantier.

Tests Git sans accès aux bases, dans des dépôts isolés sous `audits/` supprimés à la fin :

```bash
python3 tools/test_git_gemapi_app_sirs.py
```
