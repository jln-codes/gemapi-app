# AGENTS.md — GEMAPI-App

## 1. Principe fondamental

**GEMAPI-App est un projet en développement. Le dépôt doit représenter exclusivement son état actuel, sans accumulation d'architectures historiques.**

La simplicité, la cohérence et la reproductibilité priment sur la conservation de mécanismes de compatibilité devenus inutiles.

## 2. Source unique de vérité

- `model/schema.sql` est le schéma PostgreSQL/PostGIS canonique du socle GEMAPI-App pour une installation neuve.
- `model/schema.mmd` représente ce schéma.
- `demo/` contient uniquement les données fictives et les outils nécessaires à la démonstration actuelle.
- `plugin/` doit fonctionner exclusivement avec le schéma courant.
- Les tests doivent valider prioritairement une installation neuve et le fonctionnement actuel.

**Aucune fonctionnalité courante ne doit dépendre d'un ancien schéma ou d'anciennes données.**

SIRS est une extension spécialisée du socle, pas une version historique. Son modèle
peut disposer d'un schéma autonome dans `sirs/`, sans imposer sa structure aux bases
Démo et CABBALR ni de changements au plugin ou aux projets QGIS communs.

## 3. Interdiction du legacy

Ne pas créer ni maintenir :

- De répertoires `legacy/`, `archive/`, `old/` ou équivalents.
- De copies historiques des GeoPackages ou du schéma SQL.
- De fixtures correspondant à d'anciens modèles.
- De mécanismes de compatibilité avec des tables supprimées.
- De tests imposant de reconstruire une ancienne version du schéma.
- De fichiers intermédiaires devenant des dépendances permanentes.

Les fichiers devenus obsolètes doivent être supprimés, et non déplacés vers un répertoire d'archives.

L'historique Git constitue le moyen de retrouver les anciennes versions.

## 4. Politique de migration

**Ne pas accumuler de migrations SQL dans le dépôt.**

Toute évolution du modèle commun doit être intégrée directement dans `model/schema.sql`.
Le modèle SIRS évolue dans son propre schéma courant ; ses migrations et transitions
utilisent exclusivement des bases PostgreSQL/PostGIS locales, indépendantes de Supabase.
Les changements SIRS ne déclenchent aucune intervention sur Supabase.

Pour mettre à jour la base Supabase existante :

1. Auditer son état réel et ses dépendances.
2. Préparer si nécessaire un script SQL ponctuel de transition.
3. Préserver les données qui ne sont pas explicitement destinées à être supprimées.
4. Exécuter la transition après validation des préconditions.
5. Contrôler les données, contraintes et fonctionnalités.
6. Supprimer le script temporaire après utilisation.

Un script de transition ne doit jamais devenir une dépendance de l'installation neuve.

Ne pas modifier rétroactivement des migrations déjà exécutées pour simuler une installation neuve.

## 5. Supabase et données

Supabase est la base PostgreSQL/PostGIS permanente de démonstration.

Les bases PostgreSQL jetables sont réservées aux tests automatisés. Les bases métier
SIRS sont locales et permanentes ; elles ne sont pas des bases de test.

- Ne jamais supposer que Supabase a été mis à jour parce que les tests locaux réussissent.
- Ne pas modifier Supabase sans autorisation explicite.
- Avant toute suppression, contrôler les données et les dépendances.
- Ne jamais utiliser `DROP CASCADE` pour contourner une dépendance non comprise.
- Ne conserver aucune table d'archive devenue inutile après une transition contrôlée.
- Ne jamais supprimer de données non reproductibles sans validation explicite.

## 6. Séparation des données

- `cabbalr/` contient les données réelles. Ne jamais les modifier sans demande explicite.
- `demo/` contient exclusivement des données fictives.
- Ne jamais utiliser les données réelles pour fabriquer les fixtures de démonstration.
- Préserver les UUID des objets existants lorsqu'une évolution ne change pas leur identité.
- Les générateurs fictifs doivent être déterministes et reproductibles.
- `demo/` et `cabbalr/` restent versionnés dans les trois branches permanentes.
- Aucun développement SIRS ne doit supprimer les données Démo parce qu'il ne les utilise pas.

## 7. Évolutions du modèle

Lors d'une modification du schéma commun :

1. Identifier les dépendances réelles.
2. Modifier le schéma canonique.
3. Adapter les données fictives et leurs générateurs.
4. Adapter le plugin, le projet QGIS et les rapports concernés.
5. Adapter les tests existants au modèle actuel.
6. Supprimer les références devenues obsolètes.
7. Vérifier une installation neuve complète.

Ne pas laisser plusieurs modèles concurrents actifs pour une même application.
Le schéma autonome SIRS est une extension spécialisée, isolée autant que possible
dans `sirs/`. Son évolution ne doit pas modifier le plugin et les projets QGIS du
socle commun dans le périmètre initial SIRS.

Ne pas conserver un ancien mécanisme simplement parce qu'un test historique en dépend.

## 8. Discipline de développement

- Privilégier la modification des fichiers existants plutôt que la création de nouveaux fichiers.
- Limiter les documents et rapports intermédiaires.
- Ne pas introduire de tables, abstractions, scripts ou dépendances sans besoin démontré.
- Respecter les conventions de nommage du modèle.
- Séparer clairement les modifications du dépôt et les opérations sur Supabase.
- Ne pas inclure de modifications non liées dans un commit.
- Signaler les incompatibilités plutôt que créer silencieusement des contournements.

## 9. Critère de réussite

À tout moment, un clone propre du dépôt doit permettre de reconstruire l'application de démonstration à partir du seul modèle actuel, de ses données fictives et des outils documentés.

**Une seule architecture active. Une seule source de vérité. Aucun héritage technique inutile.**

## 10. Compatibilité multiplateforme du plugin QGIS

Windows est la plateforme cible prioritaire du plugin (environ 90 % des usages), même lorsque le développement et les premiers tests ont lieu sous Linux. Le plugin doit aussi fonctionner sous Linux avec QGIS et ses dépendances intégrées.

- Ne jamais déduire d'un test réussi sous Linux que le comportement fonctionne sous Windows.
- Privilégier les API portables de PyQGIS, Qt et Python. Éviter les chemins, exécutables et conventions propres à Linux.
- Vérifier les chemins et leurs séparateurs, les encodages, les permissions, les processus enfants, les environnements Python/QGIS et le packaging sur les deux plateformes.
- Pour les PDF, contrôler les polices réellement disponibles, le rendu Unicode, l'incorporation ou le rendu des caractères, ainsi que le fonctionnement de Qt en mode `offscreen`. Ne pas imposer une police ou une dépendance disponible uniquement sous Linux.
- Chaque livraison du plugin doit produire un ZIP installable et vérifier que son contenu correspond aux sources actuelles.
- Les tests Linux restent utiles, mais une validation Windows est obligatoire avant de déclarer une version compatible Windows ou prête pour une diffusion générale. Si Windows ne peut pas être testé dans l'environnement de développement, signaler explicitement cette validation restante.
- Ne pas ajouter de mécanisme complexe de compatibilité ni de dépendance supplémentaire lorsque les API natives de QGIS suffisent.

## 11. Gestion des artefacts

- Écrire les sorties locales des tests et audits dans `audits/` à la racine du dépôt ; ne jamais utiliser `plugin/output/`.
- Ne jamais versionner les sorties temporaires, PDF générés, captures ou logs de tests.
- Ne pas créer automatiquement un rapport Markdown pour chaque intervention.
- Présenter les résultats des audits dans la réponse finale, sauf demande explicite de documentation permanente.
- Réutiliser ou mettre à jour les documents existants plutôt qu'en créer de nouveaux.
- Ne conserver dans Git que les sources, tests, ressources nécessaires et documents pérennes.
- Supprimer les fichiers temporaires générés pendant les tests lorsqu'ils ne sont plus nécessaires.
- Vérifier `git status` et les nouveaux fichiers avant chaque commit.

## 12. Politique Git

- Le dépôt actif est `jln-codes/gemapi-app`, jamais `gemapi-app-legacy`.
- Trois branches permanentes : `development` pour le développement commun courant,
  `main` pour la production validée, `gemapi-app-sirs` pour le développement spécialisé SIRS.
- `gemapi-app-sirs` est le nom définitif de la branche spécialisée. Le modèle métier
  peut conserver le nom SIRS et le répertoire `sirs/` ; le chemin du worktree
  `~/Projects/gemapi-app-sirs` reste inchangé.
- Travailler directement sur `development` pour les évolutions du socle et sur
  `gemapi-app-sirs` pour les évolutions spécialisées. Préserver les modifications locales préexistantes.
- Intégrer `development` dans `main` après validation, normalement par fast-forward.
  Si cela est impossible, signaler le blocage sans réécrire l'historique.
- Chaque push réussi sur `development` déclenche sa synchronisation vers `gemapi-app-sirs`,
  indépendamment de `main`. Lorsque SIRS a ses propres commits, utiliser une fusion
  normale ; le fast-forward n'est pas une exigence pour ce flux.
- Les flux `gemapi-app-sirs → development` et `gemapi-app-sirs → main` sont interdits, y compris par
  cherry-pick de changements spécifiques. Extraire une idée commune en la
  redéveloppant et en la validant sur `development`, sans importer l'ascendance SIRS.
- Ne jamais synchroniser par force-push, `reset --hard`, réécriture d'historique,
  remplacement de SIRS par une copie de `development`, ou suppression des changements SIRS.
- Un conflit arrête la synchronisation sans publication. Résoudre explicitement
  les fichiers sur `gemapi-app-sirs` après examen des deux côtés, puis tester et pousser `gemapi-app-sirs` ;
  ne pas choisir globalement `ours`/`theirs` ni effacer des fichiers pour contourner le conflit.
- Après synchronisation, vérifier les références distantes récentes avec
  `git merge-base --is-ancestor origin/development origin/gemapi-app-sirs` (code attendu : 0).
  Une fusion locale ou une PR ouverte ne prouve pas la publication sur `origin/gemapi-app-sirs`.
- Ne pas créer de branche simplement pour isoler un chantier destiné à être immédiatement intégré.
- Réserver les branches dédiées aux expérimentations, développements réellement parallèles ou modifications présentant un risque particulier.
- Conserver des commits cohérents et clairement identifiés par chantier.
- Intégrer une branche temporaire validée dans sa branche de destination par
  `git merge --ff-only` lorsque possible ; ne pas forcer l'historique en cas de blocage.
- Ne supprimer une branche locale qu'après vérification que tous ses commits sont
  intégrés dans sa destination (`development` pour le commun, `gemapi-app-sirs` pour le spécialisé).
- Ne pas effectuer de push distant sans instruction explicite.
- Conserver ce fichier identique sur les branches lors des intégrations autorisées.
  Ne pas modifier `main` hors d'une livraison autorisée pour y recopier les instructions.

### Synchronisation GitHub et protections

- `.github/workflows/sync-gemapi-app-sirs.yml` sérialise les synchronisations. Les contrôles
  Git et leurs tests sont exécutés avant publication, car un push avec
  `GITHUB_TOKEN` ne déclenche normalement pas les autres workflows `push`.
- Ne jamais contourner une protection GitHub. Le mode direct est destiné à une
  branche `gemapi-app-sirs` autorisant ces pushes ; si une protection les interdit, configurer
  le mode PR décrit dans le README, ses contrôles obligatoires et l'auto-merge.
- Le contrôle `branch-policy` signale les PR inverses, les commits portant
  l'ascendance propre à SIRS et les changements sous `sirs/` visant le socle.
  Il doit devenir obligatoire avec interdiction des pushes directs pour bloquer
  les PR avant fusion. Un workflow `push` seul ne peut qu'alerter après publication.
- Le Markdown n'est pas une protection technique. Les administrateurs, contournements
  de règles et réécritures/cherry-picks hors `sirs/` restent des limites explicites ;
  une revue humaine reste nécessaire pour identifier la nature métier d'un changement.

### Début d'une session locale SIRS

Depuis n'importe quel répertoire sous Ubuntu :

```bash
python3 ~/Projects/gemapi-app/tools/git_gemapi_app_sirs.py update
```

La commande cible par défaut `~/Projects/gemapi-app-sirs` ; un autre emplacement
se fournit par `update --worktree CHEMIN`. Elle vérifie le worktree lié au même
dépôt, la branche `gemapi-app-sirs` et la propreté (y compris les fichiers non suivis), récupère
`origin`, puis n'autorise que `git merge --ff-only origin/gemapi-app-sirs`. Elle refuse les
commits locaux non poussés et les divergences sans déplacer ni supprimer de fichiers.
GitHub Actions met à jour le dépôt distant, pas un ordinateur éteint ou déconnecté :
cette récupération locale est volontaire, à la demande, sans service résident.
