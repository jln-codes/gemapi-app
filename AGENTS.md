# AGENTS.md — GEMAPI-App

## 1. Principe fondamental

**GEMAPI-App est un projet en développement. Le dépôt doit représenter exclusivement son état actuel, sans accumulation d'architectures historiques.**

La simplicité, la cohérence et la reproductibilité priment sur la conservation de mécanismes de compatibilité devenus inutiles.

## 2. Source unique de vérité

- `model/schema.sql` est le schéma PostgreSQL/PostGIS canonique pour une installation neuve.
- `model/schema.mmd` représente ce schéma.
- `demo/` contient uniquement les données fictives et les outils nécessaires à la démonstration actuelle.
- `plugin/` doit fonctionner exclusivement avec le schéma courant.
- Les tests doivent valider prioritairement une installation neuve et le fonctionnement actuel.

**Aucune fonctionnalité courante ne doit dépendre d'un ancien schéma ou d'anciennes données.**

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

Toute évolution du modèle doit être intégrée directement dans `model/schema.sql`.

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

Les bases PostgreSQL jetables sont réservées aux tests automatisés.

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

## 7. Évolutions du modèle

Lors d'une modification du schéma :

1. Identifier les dépendances réelles.
2. Modifier le schéma canonique.
3. Adapter les données fictives et leurs générateurs.
4. Adapter le plugin, le projet QGIS et les rapports concernés.
5. Adapter les tests existants au modèle actuel.
6. Supprimer les références devenues obsolètes.
7. Vérifier une installation neuve complète.

Ne pas laisser plusieurs modèles concurrents actifs.

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

- Travailler directement sur `main` par défaut pour les évolutions courantes, corrections, migrations et petits chantiers définitifs.
- Ne pas créer de branche simplement pour isoler un chantier destiné à être immédiatement intégré.
- Réserver les branches dédiées aux expérimentations, développements réellement parallèles ou modifications présentant un risque particulier.
- Conserver des commits cohérents et clairement identifiés par chantier.
- Intégrer une branche temporaire validée par `git merge --ff-only`, sans commit de fusion ; si le fast-forward est impossible, signaler le blocage sans forcer l’historique.
- Ne supprimer une branche locale qu’après vérification que tous ses commits sont intégrés dans `main`.
- Ne pas effectuer de push distant sans instruction explicite.

### Exception temporaire — PERF-QGIS-03

- Travailler exclusivement sur la branche `development` pour PERF-QGIS-03 ; conserver `main` intacte jusqu'à la recette fonctionnelle complète.
- Les commits locaux cohérents avec ce chantier sont autorisés sur `development`.
- Ne pas pousser `development` ni la fusionner dans `main` sans validation explicite.
- Préserver les modifications locales préexistantes et les exclure des commits PERF-QGIS-03.
