# LIDAR-EXTRACT-01 — Retrait de LiDAR de GEMAPI-App

19 novembre 2026. Le rapport complet, l’historique extrait, les tests et les
instructions Windows/Ubuntu sont dans le [dépôt LiDAR autonome](https://github.com/jln-codes/qgis-lidar-fr/blob/main/LIDAR-EXTRACT-01.md).

Source intégrée : `development`, fusion `a9d07a7`, contenu LiDAR `40bd605`.
`git subtree split --prefix=LiDAR development` donne
`ce9f8e04523a537b869feef02b7ef11edbb93d3f`, avec onze commits pertinents.
Publication autonome vérifiée : `327a4ed2cd05f1381abdf8ecc3f8bcb2a2517fb8`
sur `jln-codes/qgis-lidar-fr`, branche `main`, sans push forcé.

Un clone neuf depuis GitHub reconstruit le ZIP strictement identique et passe
le test d’installation. SHA-256 du ZIP LiDAR 0.1.3 :
`7486e62b4d6e74f4da8d055088d098829338d32f6d1ade27fca17ea7c3518fd2`.
Le retrait du répertoire source intervient seulement après ce contrôle.
Les fichiers ignorés locaux ont été conservés dans la sauvegarde privée de
transition, hors Git. Les audits historiques LiDAR restent dans ce dépôt.

Le nettoyage retire `LiDAR/` et ses constructions de la documentation active.
Les tests du plugin standard n’importent plus LiDAR. Le README conserve un lien
simple ; le constructeur standard reste indépendant. Chaque dépôt construit
son ZIP avec son propre manifeste. Aucun moteur métier ni paramètre IGN changé.

Tests LiDAR : 52 avant extraction, 53 autonomes, 4 du script de référence,
benchmark de 100 tuiles fictives et installation depuis un clone propre.
Le banc de deux ZIP et QGIS Desktop 3.44.15 réel sous X11 virtuel vérifient les
plugins seuls, les deux ordres d’activation, le retrait de chacun et les
réactivations sans doublon. LiDAR seul passe aussi sa recette Desktop avec
sélection cartographique, tâche en cache fictif, Turbo et réouverture du projet.
Les recettes sont automatisées. Windows natif et partage SMB réel restent à tester.
Aucune donnée PostgreSQL permanente modifiée.

Le nettoyage est réalisé sur `development`, puis intégré dans `main` par
fast-forward. Le worktree `sirs` est créé à partir de cette version nettoyée.
L’état final des branches et worktrees est décrit dans `GEMAPI-TRANSITION-01.md`.
