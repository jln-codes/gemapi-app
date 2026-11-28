# SIG-FUSION-11 — Schéma patrimonial unique

Le commit de départ est `69034f9bc0961e4d7215ea1a3764752c3f75a7dc`. Sur la branche `gemapi-app-sirs`, le modèle à transférer ultérieurement dans `gemapi-dev` utilise le schéma PostgreSQL fixe **gemapi**. La configuration d’un nom personnalisé et le déploiement sur les serveurs partagés relèvent du futur chantier `gemapi-dev`.

## Installation et permissions

`model/schema.sql` crée les objets applicatifs dans `gemapi` dans une transaction d’installation neuve. Il refuse une destination occupée. Le schéma PostgreSQL `public` continue d’exister. L’emplacement de PostGIS est découvert dans `pg_extension`. Une extension existante reste dans son schéma. Les fonctions, vues, expressions de déclenchement et instructions dynamiques qui utilisent les tables métier désignent explicitement `gemapi`. Les chemins de recherche des fonctions à privilèges élevés sont fixés à l’installation.

`model/roles_milieux.sql` conserve la hiérarchie Consultation, Prestations, Patrimoine et les noms de rôles de cluster existants. Les droits sur les tables et les fonctions ciblent les objets de `gemapi`. Le droit USAGE sur le schéma effectif de PostGIS permet d’utiliser ses types et fonctions. Les profils Prestations et Patrimoine conservent leurs périmètres d’écriture distincts. [Matrice des droits](../model/role.md)

Le Mermaid courant représente la même projection que le Mermaid v0.6.1 après remplacement des trois préfixes de schéma. La comparaison textuelle, hors en-tête, conserve également les commentaires de contraintes et les valeurs de référentiels. Les documents de conception versionnés demeurent les témoins historiques.

## Démonstration et QGIS

L’importeur exige le nom explicite d’une base locale vide. Les SQL fictifs, les générateurs et l’audit spatial accèdent aux tables de `gemapi`. Le schéma opérationnel et les 22 catalogues sont installés avant le chargement. [Reconstruction locale](../demo/README.md)

Le plugin 0.8.6 utilise les noms qualifiés de `gemapi` pour les prestations, leurs cibles, les vues cartographiques, les rapports et l’assistant. Les trois familles d’enfants des sites conservent leurs champs `designation` et `geometry`. Les actions des digues et sections AH et la vérification des droits utilisent le même schéma. Le service libpq `gemapi_demo` sélectionne la connexion. Le projet contient 32 couches PostgreSQL et un fond OSM. La comparaison de son archive avec le commit initial retrouve les mêmes octets de styles et de document QGS après substitution des seuls préfixes d’URI dans les sources de couches et de widgets. [Relations QGIS](../docs/qgis_relations.md#connexions-et-comptes)

Les formulaires, les rapports et le cache de session partagent la vérification de connexion. Une couche de prestation ou de cible placée dans un autre schéma, ou plusieurs connexions pour les couches de `gemapi`, déclenchent une erreur avant l’ouverture de la connexion du plugin.

## Résultats sur installations neuves

L’introspection a porté sur PostgreSQL 16.15 et PostGIS 3.4.2. Les deux installations ont été comparées au Mermaid v0.6.1 en tenant compte du seul changement de qualification des objets.

| Schéma applicatif | Emplacement de PostGIS | Tables | Colonnes | FK internes / externes | Référentiels / valeurs | Vues | Tests SQL |
|---|---|---:|---:|---:|---:|---:|---:|
| `gemapi` | `public` | 48 | 431 | 109 / 0 | 22 / 298 | 6 | 11 sur 11 |
| `gemapi` | `extensions` | 48 | 431 | 109 / 0 | 22 / 298 | 6 | 11 sur 11 |

Les 48 tables se répartissent en 22 tables métier, 4 associations et 22 référentiels. Les clés, les colonnes, leurs types et leur nullabilité, les index spatiaux et les identifiants de nomenclature ont été contrôlés. La tentative de seconde installation a échoué et la première installation est restée utilisable. Les trois profils ont été testés par connexion individuelle, y compris pour la lecture des vues et les recalculs déclenchés par une modification de géométrie.

| Parcours | Résultat observé |
|---|---|
| Import fictif sous les deux emplacements de PostGIS | Empreintes identiques entre les deux bases et comparaison des 100 prestations aux GeoPackages. Conservation des UUID, quantités, unités, photos et géométries. Les 100 prestations sont cartographiées, dont 12 par repli sur la végétation. |
| Patrimoine fictif | 12 sites, 19 végétations, 4 mobiliers, 2 cheminements, 10 stockages AH et 13 ouvrages constitutifs. Contrôles de parent, de topologie et de repérage hydrographique réussis. |
| QGIS 3.44.15 sous Linux | Projet distribué ouvert avec PostGIS dans chacun des deux schémas. Les 33 couches, 70 relations et widgets relationnels sont valides. |
| Prestations et rapports | Création sur chacune des trois familles d’enfants de sites, sur ouvrage AH et sur stockage AH. Édition d’une prestation reprise sur végétation. Le site témoin retrouve ses huit prestations dans la gestion et le rapport. Exports détaillé et synthétique produits. Conflit de révision et rollback vérifiés. |
| Hydrographie et assistant | Huit tests d’intégration des rattachements hydrographiques réussis. Assistant testé avec réponses Mistral simulées, trois rattachements enregistrés par le formulaire standard et contrôles de résolution des homonymes. |
| Édition des digues et actions AH | Onze groupes de contrôles réussis. Consultation par profil, édition et suppression contrôlées, refus si un objet est référencé, conflits de révision, boutons de formulaires natifs, actions et annulation. |
| Paquet QGIS | ZIP 0.8.6 reconstruit. Les 38 fichiers de l’archive sont identiques aux sources distribuées. Le test de construction reproductible et de chargement du plugin passe. |

Le test de la source hydrographique attendait encore deux cours d’eau sans nom. Les 58 cours d’eau du GeoPackage témoin sont nommés, comme l’exige le contrat courant. Le test a été aligné sur cette source. Les GeoPackages et les photographies sont identiques au commit de départ.

## Reproduire les vérifications

Depuis la racine du dépôt, avec le Python de QGIS, PostgreSQL/PostGIS local et l’image Docker de qualification disponible, exécuter les contrôles suivants.

```sh
/usr/bin/python3 plugin/tests/test_sirs_postgis.py
/usr/bin/python3 plugin/tests/test_demo_import.py
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_demo_site_children_qgis.py
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_demo_site_children_qgis.py --postgis-extensions
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_assistant_integration.py
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_edit_integration.py
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_hydro_assoc_integration.py
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_digues_edit.py
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_session_data.py
python3 plugin/tools/build_plugin.py
```

Les vérifications SQL et PyQGIS portent sur la démonstration reproductible et des bases jetables. L’ouverture sur un poste QGIS Windows et les exports sur cette plateforme restent à qualifier.
