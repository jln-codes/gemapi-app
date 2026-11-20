# GEMAPI-App

Dépôt : [jln-codes/gemapi-app](https://github.com/jln-codes/gemapi-app).
L'historique antérieur à la refonte du dépôt est conservé dans
[gemapi-app-legacy](https://github.com/jln-codes/gemapi-app-legacy).

Modèle PostgreSQL/PostGIS V0.13, données de démonstration et plugin QGIS
**GEMAPI-App 0.8.1**, assistant Mistral et dictée Voxtral
(QGIS 3.44 minimum).

## Organisation

```text
gemapi-app/
├── model/
│   ├── schema.sql             # unique schéma canonique
│   ├── schema.mmd
│   └── role.md                # matrice des rôles PostgreSQL
├── demo/
│   ├── data/                  # 10 imports SQL et importer_base_neuve.sh
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

Le schéma canonique est `model/schema.sql` et son diagramme est
`model/schema.mmd`. Les données réelles CABBALR sont conservées dans
`cabbalr/gpkg/` ; leurs SQL d'import initial sont dans `cabbalr/sql/`.

Le projet du plugin est sous `plugin/` : code dans `gemapi_app/`, tests
dans `tests/` et construction dans `tools/`. Les sorties locales des tests
vont dans `audits/` à la racine. Aucun de ces déplacements ne nécessite de
migration des données métier.

## Utilisation

- [LiDAR HD 2026](https://github.com/jln-codes/qgis-lidar-fr) est développé, testé
  et distribué dans son dépôt autonome. Les deux extensions partagent seulement
  la barre QGIS **SIG-Milieux**, sans dépendance technique.
- Ouvrir [le projet Démo](demo/prestations_demo.qgz) pour `sig-milieux-demo`,
  ou [le projet CABBALR](cabbalr/prestations_cabbalr.qgz) pour les données réelles.
  Les [instructions QGIS](docs/qgis_relations.md#synchroniser-les-deux-projets)
  expliquent comment synchroniser leurs styles, formulaires et relations en
  conservant les connexions propres à chacun.
- [Installer une base de démonstration](demo/README.md) : après activation de
  PostGIS dans une base neuve, lancer depuis la racine
  `bash demo/data/importer_base_neuve.sh nom_base`.
- [Installer, utiliser et tester le plugin](plugin/README.md) : générer le ZIP
  avec `python3 plugin/tools/build_plugin.py`, puis installer
  `plugin/dist/gemapi-app-0.8.1.zip` dans QGIS.

Le ZIP standard embarque uniquement le package `gemapi_app/`, ses modules, les
interfaces Qt, l'icône et le logo institutionnel. Il n'embarque aucune donnée,
aucun schéma, test, outil ou rapport généré.
