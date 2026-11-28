# SIG-FUSION-08 · Installation neuve du modèle patrimonial v0.6.1

La branche `gemapi-app-sirs` installe le modèle patrimonial directement depuis `model/schema.sql`. Le seul changement de rattachement par rapport à la v0.6 est l’extension de trois à cinq parents pour le mobilier, les cheminements et la végétation. Le point de départ du travail est `71e3332af0473f7572eff8c555ce0a18804b1528`.

## Contrat installé

| Mesure | Projection v0.6 | Catalogue PostgreSQL v0.6.1 |
|---|---:|---:|
| Tables métier | 22 | 22 |
| Tables associatives | 4 | 4 |
| Tables de référence | 22 | 22 |
| Total des tables applicatives | 48 | 48 |
| Colonnes | 425 | 431 |
| FK internes | 103 | 109 |
| FK externes | 0 | 0 |
| Valeurs initiales des catalogues | 298 | 298 |

Le comptage exclut les relations appartenant à l’extension PostGIS. Il inclut la FK composite BERGE une seule fois. Les 17 entrées des trois catalogues de prestations et les 281 entrées des 19 catalogues patrimoniaux sont installées avec leurs identifiants. Les valeurs NULL restent distinctes des codes explicites « Indéfini ». Les types physiques de tronçons comptent sept valeurs, les typologies constructives cinq. Le diagramme courant et la projection publiée sont identiques octet pour octet. [Schéma courant](schema.mmd) · [Projection v0.6.1](schema_development_v0.6.1.mmd) · [Fiches et sommaires paginés](schema_development_tables_v0.6.1.pdf)

| Enfant | Parents admissibles | Moment du contrôle |
|---|---|---|
| `public.mobilier`, `public.cheminements`, `public.vegetation` | Site terrestre, tronçon, ouvrage AH, stockage AH ou section AH. Chaque table passe de 15 à 17 colonnes. | Cinq UUID individuellement facultatifs. `num_nonnulls(...) = 1` à chaque écriture. Les cinq FK portent `ON DELETE RESTRICT`. |
| `public.ouvrages_hydrauliques` | Tronçon, ouvrage AH ou stockage AH | Exactement un des trois à chaque écriture. |
| `milieux.prestations` | Cours d’eau, digue, tronçon, stockage AH, ouvrage AH, section AH, site terrestre, mobilier, cheminement ou végétation | Au plus une cible à chaque écriture. `prestation_relations_parent` appelle `prestation_relations_complete()` et `assert_prestation_relations(uuid)` sur l’état final. |
| `public.desordres` | Digue, tronçon, trois enfants AH, site terrestre, mobilier, cheminement ou végétation | Zéro ou une cible directe. Trois associations distinctes permettent de référencer des équipements et ouvrages techniques. |
| `public.observations` | Désordre, tronçon, trois enfants AH, site terrestre, les trois nouvelles familles, ouvrage hydraulique, ouvrage particulier ou équipement de mesure | Une cible parmi douze, avec date de constat obligatoire. |
| `public.photos` | Observation obligatoire | La clé du fichier est unique lorsqu’elle est renseignée. L’archivage par `desordres.date_fin` conserve le constat et la photo. Les deux emplacements photo de la prestation restent directs. |

La digue et le type physique du tronçon sont obligatoires. La FK BERGE contrôle le couple identifiant/type à la fin de la transaction grâce à une constante générée et à `uq_troncons_type`. Les crêtes gardent leurs restrictions de champs. Un franc-bord ou une risberme validé exige sa forme valide et non vide. La géométrie de repérage facultative est une ligne de longueur positive. Les repères de digue et les sections hydrographiques d’AH conservent le contrôle des fractions, des signatures et des révisions. `digue_supprimer` indique désormais le blocage par un tronçon ou un désordre direct avant de toucher au repère. Les liens historiques de support et de bornage SIRS ainsi que les structures AH restent hors projection.

## Géométries de prestation et chiffres publiés

| Cible | Localisation dans `prestations_carte` | Sens des mesures |
|---|---|---|
| Cours d’eau, digue, tronçon, site terrestre, section AH | Géométrie propre obligatoire, de type multiple sur site terrestre | Point(s), longueur en mètres ou surface de l’intervention selon sa géométrie. |
| Ouvrage AH, stockage AH, mobilier, cheminement, végétation | Géométrie propre en priorité, sinon géométrie de la cible directe | `origine_mesures` indique `Prestation` ou `Patrimoine de rattachement`. Dans le second cas, la longueur ou la surface décrit l’objet localisé. |

Les formes métier sont en EPSG:3950. `mesures07_resoudre` accepte une géométrie et les cinq UUID pour lesquels le repli est possible. `mesures07_preparer` verrouille la cible empruntée en lecture partagée jusqu’à la fin de la transaction. `mesures07_parent` déclenche le recalcul après changement de forme sur ces cinq tables, uniquement pour les interventions qui empruntent cette forme. La géométrie propre de la prestation reste NULL lorsqu’elle est empruntée. La fiche expose les mesures stockées, avec conversion des m² en hectares dans la colonne générée.

Les essais utilisent notamment une ligne de 5 m, un polygone de 6 m² et deux points. La quantité saisie de 7 et son unité restent identiques après chaque changement de géométrie. Les champs de position et de rive conservent leurs valeurs autorisées et les quatre catégories historiques pouvant les préciser. Tout bilan de travaux doit tenir compte de la provenance avant d’additionner les mesures.

Les six vues restent sous les droits de l’appelant. `prestations_carte` et `prestations_fiches` exposent les nouvelles FK. `prestations__sites_terrestres` associe au site les prestations directes et celles d’un enfant **directement** rattaché à ce site. `prestations__ah` garde les trois branches directes ouvrage, stockage et section. Un mobilier d’une section ou d’un stockage est un enfant valide en base sans étendre les agrégats de consultation AH ou digue. Les vues `ah_sections_carte` et `digues_carte` conservent leurs contrôles de référencement.

## Installation, écriture et droits

L’installation est transactionnelle. Utiliser une base locale neuve dédiée à SIRS avec PostgreSQL 16+ et PostGIS disponible. Exécuter `model/schema.sql`, puis `model/roles_milieux.sql` avec un administrateur habilité à créer les groupes. Le premier script installe PostGIS dans `public` si nécessaire, ou utilise l’emplacement de l’extension déjà installée. Il vérifie les relations préexistantes dans les trois schémas applicatifs, crée les catalogues, charge leurs valeurs, puis crée les objets et leurs dépendances. Une nouvelle exécution sur une base occupée est refusée. Cette procédure est réservée à l’installation neuve. [Schéma SQL](schema.sql) · [Droits d’accès](roles_milieux.sql)

- Les identités métier UUID ont une valeur serveur par défaut. Les PK composites des trois associations techniques incluent les deux UUID existants. Les catalogues SIRS conservent leurs PK texte. L’installation ne crée aucune séquence applicative.
- `stamp_modification()` utilise `session_user` et `clock_timestamp()`. Sur chacune des 22 tables métier, `cree_le` reçoit son défaut serveur et toute tentative de le changer après insertion échoue. Un recalcul des seules mesures empruntées préserve l’auteur et la date de la prestation. Les dates d’intervention, de constat, de photo et d’archivage gardent leur sens métier.
- Les drapeaux `valid` obligatoires démarrent à `false`, ceux qui sont facultatifs conservent NULL par défaut. Une ressource dotée de `version` démarre par défaut à 1. Chaque UPDATE avance la version serveur d’une unité, dans la limite de 9 007 199 254 740 991. Un client peut protéger ses écritures en filtrant sur la version lue et en contrôlant le nombre de lignes modifiées. La prestation continue d’utiliser son mécanisme existant.
- Une écriture dans l’une des trois associations techniques de désordres avance la version des désordres concernés. Une réaffectation traite les deux UUID dans un ordre stable. Les constats et les photos gardent leurs propres versions. La suppression d’un parent référencé demande la résolution explicite des dépendances. La qualification BERGE conserve le délai transactionnel prévu.
- Les formes consultables disposent d’index GiST, y compris l’axe facultatif. Des B-tree couvrent les recherches par parent, cible, observation et désordre. Les FK facultatives vers des objets métier utilisent des index partiels sur leurs valeurs présentes lorsque la PK ne couvre pas déjà le parcours.
- Consultation lit les 48 tables et les six vues. Prestations ajoute l’écriture sur `milieux.prestations` uniquement. Patrimoine ajoute l’écriture sur les inventaires, les associations, les constats et les photos. Les catalogues restent réservés à l’administration pour l’écriture. Les fonctions de validation différée qui prennent des verrous s’exécutent via leurs triggers. Les comptes de saisie n’ont besoin d’aucun droit supplémentaire sur les parents. [Matrice des profils](role.md)

## Qualification reproductible

Depuis la racine du dépôt, sous un compte local ordinaire disposant de PostgreSQL, de PostGIS, de `pg_config` et de `psycopg2` pour le Python utilisé, exécuter la commande suivante.

```bash
/usr/bin/python3 -B plugin/tests/test_sirs_postgis.py
```

La suite initialise pour chaque configuration un cluster et une base `qualification` dans un répertoire temporaire privé. TCP est désactivé. Le banc contrôle le répertoire de données de l’instance, le socket et le nom de base avant installation. Il crée ses propres logins, arrête le serveur et libère son répertoire en fin d’exécution. Les scénarios de révision hydrographique sont partagés avec le test préexistant des rôles. [Suite PostgreSQL/PostGIS](../plugin/tests/test_sirs_postgis.py) · [Scénarios de rôles et de repérage](../plugin/tests/test_roles_postgres.py)

| Contrôle exécuté par installation | Résultat attendu et observé |
|---|---|
| Catalogue PostgreSQL contre le Mermaid | Identité des tables, 431 noms/types/nullabilités, typmods, PK et UK, colonnes ordonnées et destinations des 109 FK, politiques de suppression, clés différées, colonnes générées et index GiST. Comparaison des tuples de nomenclature par identifiant. |
| Trois familles à cinq parents | 32 combinaisons par famille, 5 admises et 27 refusées. Rejet des UUID inconnus et des géométries invalides, vides, de mauvais SRID ou de mauvaise dimension. Sur 15 parents isolés, suppression bloquée puis permise après réaffectation. |
| Ouvrages et tronçons | 3 combinaisons admises sur 8 pour le parent hydraulique. Les sept types de tronçons acceptent un constat. Seule la berge satisfait la FK composite de rôle. Vérification des crêtes, de l’axe et de la validation des francs-bords et risbermes. |
| Désordres, observations et photos | Neuf cibles directes de désordres et rejet des paires. Douze cibles isolées de constats acceptées, zéro et les 66 paires refusés. Rejet d’un constat sans date et d’une clé de fichier dupliquée. Conservation des enfants à l’archivage. |
| Prestations et concurrence | Dix cibles, refus des doubles cibles, complétude différée, règles propres au site et aux positions. Géométrie propre prioritaire, repli, recalcul, quantité et auteur préservés. Deux connexions réelles à des rôles différents, verrou observé avant publication et contrôle de la mesure finale. |
| Permissions et références hydrographiques | Trois logins effectifs, lecture des six vues, matrice de droits sur les tables, refus des écritures indues, recalcul par Patrimoine. Préparation puis revalidation sous contrôle de révision, refus d’une modification libre, diagnostic de suppression de digue. |
| Installation occupée | Refus explicite de la seconde installation. Les lignes de référence restent consultables après annulation. |

Le dernier passage complet a réussi **22 tests sur 22 en 175,707 s**. Les onze scénarios ont été exécutés une fois avec PostGIS préinstallé dans `extensions` et une fois avec son installation dans `public` par le schéma. Les deux serveurs ont été arrêtés et leurs répertoires supprimés. Aucun écart de structure ou de valeurs initiales n’a été trouvé.

Deux ajustements de qualification ont été nécessaires. L’installation de PostGIS indique explicitement `public` lorsqu’il est absent, y compris lorsque la session commence son chemin de recherche par `pg_catalog`. L’initialisation du banc dispose d’un délai de cinq minutes distinct de celui des requêtes métier. Les logins ordinaires vérifient leur destination via le socket et le nom de base. Le contrôle du répertoire de données incombe à la connexion d’administration.

Le PDF de 70 pages reprend les 48 fiches, les numéros de page par table, les liens vers les parents et enfants et le retour au sommaire. Le contrôle documentaire compare les colonnes, les 298 entrées, les destinations des liens et les pages imprimées avec le Mermaid. Les 844 liens internes ont une destination valide. Les pages de sommaire et la fiche mobilier ont également été examinées visuellement. Le rendu SVG du diagramme contient 48 entités, 431 attributs et 109 relations.

## Limites et décisions ultérieures

La qualification concerne PostgreSQL 16.15 et PostGIS 3.4.2 sous Linux, sur des données de test synthétiques. Le repli géométrique est vérifié pour la localisation. L’utilisation de ces mesures dans de futurs indicateurs de travaux reste à définir par indicateur. La volumétrie réelle et les temps de réponse de production restent à mesurer.

Les projets QGIS, le plugin et les générateurs de démonstration conservent des consommateurs de l’ancien modèle de sites. Leur adaptation et leur qualification, y compris sous Windows, constituent une étape ultérieure. La reprise des données réelles, CABBALR et l’évolution du migrateur restent distinctes de l’installation neuve. [Contrat de migration](contrat_migration_sirs_gemapi.md)
