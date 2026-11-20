# Chargement initial canonique CABBALR

Ces fichiers contiennent les données **réelles CABBALR**, issues exclusivement
des huit GeoPackages de `cabbalr/gpkg/`. Ils ne doivent jamais être
chargés dans `sig-milieux-demo`. Aucune prestation n'est importée.

Le chargement couvre les colonnes du modèle canonique. **Ce n'est pas encore
une migration intégrale sans perte d'information** : les sept attributs
complémentaires des sites/zones ont un inventaire exhaustif dans
[`../gpkg/attributs_complementaires.json`](../gpkg/attributs_complementaires.json) et une
proposition séparée dans
[`../gpkg/ATTRIBUTS_COMPLEMENTAIRES.md`](../gpkg/ATTRIBUTS_COMPLEMENTAIRES.md).
Leur destination PostgreSQL reste à valider. Les GeoPackages sont conservés.

## Prérequis et destination

- PostgreSQL 16 ou version compatible, PostGIS 3.4 ou version compatible.
- Une base CABBALR dédiée, vide avant installation du schéma. Sa création et
  les comptes relèvent de l'administrateur ; ces fichiers ne créent aucune base.
- PostGIS installé dans `public` **ou** dans un schéma d'extension distinct.
  Les SQL découvrent son schéma dans le catalogue, sans supposer `public`.
- Installer le fichier courant `model/schema.sql`. Il constitue l'unique
  définition du modèle ; aucun ancien schéma n'est reconstruit.
- Exécuter comme propriétaire des tables, ou rôle administratif disposant
  déjà des mêmes droits, avec accès aux fonctions PostGIS et métier. L'import
  doit pouvoir verrouiller les tables et modifier leurs triggers de
  traçabilité. Aucun droit applicatif n'est élargi par les SQL.

Installer PostGIS au choix, avant le schéma :

```sql
CREATE EXTENSION postgis;
```

Ou, sur une base sans PostGIS :

```sql
CREATE SCHEMA extensions;
CREATE EXTENSION postgis WITH SCHEMA extensions;
```

Les exemples `psql` ci-dessous partent de la racine du dépôt et utilisent le
nom de base indicatif `base_cabbalr`. Configurer hôte, port et utilisateur par
les moyens habituels de PostgreSQL. Aucun mot de passe ni chaîne de connexion
n'est fourni dans ces livrables. Aucun outil Supabase ou Python n'est requis
sur le serveur de destination.

## Installation

Installer d'abord le schéma, une seule fois, sur la base neuve :

```sh
psql -X --set=ON_ERROR_STOP=1 --dbname=base_cabbalr --file=model/schema.sql
```

Charger ensuite **tous les fichiers dans la même invocation `psql`**, dans cet
ordre. Les lignes suivantes forment une seule commande ; sous un autre shell,
on peut placer tous les arguments sur une ligne.

```sh
psql -X --set=ON_ERROR_STOP=1 --dbname=base_cabbalr \
  --file=cabbalr/sql/00_preparer.sql \
  --file=cabbalr/sql/01_referentiels.sql \
  --file=cabbalr/sql/02_techniciens.sql \
  --file=cabbalr/sql/03_communes.sql \
  --file=cabbalr/sql/04_cours_eau.sql \
  --file=cabbalr/sql/05_ah.sql \
  --file=cabbalr/sql/06_sites.sql \
  --file=cabbalr/sql/07_digues.sql \
  --file=cabbalr/sql/08_ah_sections.sql \
  --file=cabbalr/sql/09_verifier.sql
```

`00_preparer.sql` ouvre la transaction ; `09_verifier.sql` la valide après
contrôles. Ne pas ouvrir une nouvelle connexion pour chaque fichier, ne pas
les exécuter en parallèle et ne pas ajouter `--single-transaction` autour de
ce jeu qui possède déjà son `BEGIN`/`COMMIT`. Les dix fichiers ne contiennent
que du SQL PostgreSQL standard et peuvent aussi être envoyés dans cet ordre
sur une seule connexion administrative. Il faut arrêter au premier échec.

Pour le transfert final, les dix fichiers `.sql` et le schéma canonique sont
suffisants. Les géométries sont embarquées en WKB hexadécimal avec SRID 3950 ;
le serveur n'ouvre aucun GeoPackage. Le générateur, GDAL et les API Supabase
ne participent pas à l'exécution du chargement.

## Protection des données et traçabilité

L'import est réservé à une installation initiale. Toutes les tables métier
doivent être vides, sauf les quatre catégories et quatre statuts initialisés
par le schéma. Les UUID, libellés et ordres des catégories sont vérifiés, ainsi
que les UUID/codes/libellés des statuts. Ces lignes ne sont pas réinsérées.

Les tables cibles sont verrouillées pendant la transaction. Une cible non
vide, un référentiel différent, une contrainte non validée ou un trigger
désactivé provoque un refus. Il n'y a ni fusion, ni écrasement, ni
`ON CONFLICT`, ni suppression de données. Un second chargement est refusé.

Seuls les triggers `tr_stamp_*` des tables effectivement chargées sont
suspendus, pour conserver `modifie_par` et `date_modification`, y compris les
NULL. Les FK, contrôles géométriques, contraintes différées, qualification et
préparation des références restent actifs. Les contraintes différées sont
vérifiées avant de réactiver les triggers de traçabilité : cela évite un
`ALTER TABLE` avec des événements de triggers encore en attente. Une
vérification finale exige que tous les triggers soient réactivés avant commit.

Avec `ON_ERROR_STOP=1`, une erreur ferme la connexion avec transaction annulée :
les insertions et les désactivations de triggers sont toutes annulées.
Dans une session interactive, exécuter `ROLLBACK` après toute erreur, puis
diagnostiquer avant de reprendre. Ne pas tenter de continuer fichier par fichier.

Les dates historiques portent un fuseau explicite et sont converties en UTC
sans changer leur instant. Les dates absentes restent NULL. Les nouveaux
`valide_par` / `date_validation` des sections AH décrivent la validation serveur
au chargement ; ils ne sont pas des dates historiques inventées. Les UUID
existants sont conservés ; les FID GeoPackage ne servent jamais d'identifiants
métier.

## Références et choix métier

Les fractions et rattachements existants alimentent les triggers normaux
`digues_reperes_prepare` et `ah_sections_prepare`. Les anciennes géométries et
signatures exportées des digues ne sont pas utilisées. Aucun trigger de
préparation n'est désactivé et aucune direction n'est attribuée par l'import.

Le serveur calcule `ST_LineSubstring`, les signatures et l'état des références.
Le chargement des sections préparées doit correspondre à une acceptation
explicite des cours d'eau et fractions par le responsable métier. Si une
source devient non qualifiée, l'import échoue et la transaction est annulée.

Les sites sont des MultiPolygon et les zones acceptent MultiPoint,
MultiLineString et MultiPolygon, en EPSG:3950. Les 41 zones de Vallée Carreau
référencent son UUID conservé après le regroupement.
Les sites sans zone sont valides. Aucune contenance spatiale des zones dans
leur parent n'est imposée ni corrigée. Aucune mesure déclarée n'est recalculée.
Les colonnes générées `cours_eau.section` et `valide` sont omises des INSERT.

## Contrôles après chargement

Le dernier fichier impose les effectifs suivants et la conformité des références :

| Table | Effectif |
|---|---:|
| `prestations_categorie` / `types_prestations` | 4 / 9 |
| `prestataires` / `techniciens` | 6 / 10 |
| `communes` / `cours_eau` | 100 / 170 |
| `ah` / `ah_stockage` / `ah_ouvrage` | 9 / 8 / 9 |
| `ah_sections` | 8 conformes |
| `digues` / `digues_reperes` | 15 / 15 conformes |
| `sites_terrestres` / `sites_zones` | 16 / 41 |
| `statuts_prestations` / `prestations` | 4 / 0 |

Contrôles complémentaires en lecture seule :

```sql
SELECT count(*) FROM milieux.sites_terrestres s
WHERE NOT EXISTS (SELECT FROM milieux.sites_zones z WHERE z.site_terrestre_id=s.id);
-- 15
SELECT etat_reference, count(*) FROM milieux.ah_sections_carte GROUP BY 1;
SELECT etat_referentiel, count(*) FROM milieux.digues_carte GROUP BY 1;
SELECT count(*) FROM milieux.prestations;
-- 0
```

Les tests de développement comparent en plus tous les UUID, attributs canoniques,
instants historiques et WKB des géométries non calculées aux sources. Ils
contrôlent aussi les fractions/signatures et le résultat des fonctions serveur.

## Régénération et empreintes

Sur le poste de préparation doté de Python et GDAL/OGR :

```sh
python3 cabbalr/scripts/generer_sql.py
python3 cabbalr/scripts/test_sql.py
```

Le second appel nécessite Docker et l'image `postgis/postgis:16-3.4`. Les tests
utilisent uniquement des conteneurs jetables, sans connexion distante ; seuls
le schéma et les SQL sont copiés dans le serveur de test, pas les GeoPackages.
Les sorties locales de tests sont à conserver sous `audits/`.

Le générateur lit une liste fixe de huit fichiers dans `cabbalr/gpkg/`. Il ne
parcourt pas d'autres dossiers, ne lit ni `prestataires.gpkg` ni `prestations.gpkg` et ne
modifie aucune source. Enregistrer et fermer les sources avant génération :
un journal d'écriture actif provoque un refus.

`manifest.json` contient les empreintes des sources, du schéma et leurs effectifs.
`SHA256SUMS` couvre les SQL, le manifeste et l'inventaire complémentaire.
Depuis `cabbalr/sql/`, sur le poste de préparation, on peut utiliser :

```sh
sha256sum --check SHA256SUMS
```

L'entrée `../gpkg/attributs_complementaires.json` concerne uniquement l'inventaire
séparé ; ce fichier n'est pas nécessaire à l'exécution SQL sur la destination.
Deux générations avec les mêmes sources et schéma produisent les mêmes octets
et empreintes. Aucun horodatage de génération ni secret n'est embarqué.
Après modification d'un GeoPackage ou du modèle, régénérer et revalider
l'ensemble ; ne pas mélanger les fragments de générations différentes.


## Déploiement coordonné HYDRO

**Préparation uniquement : aucune migration Supabase appliquée.** HYDRO-ASSOC-01
reste le chantier publié `ea7a849`. Le paquet 0.7.31 ajoute la suppression des
libellés anonymes et nécessite également les transitions de noms décrites ici.
Ne pas l'activer sur les bases réelles avant validation des deux transitions.

Les sources CABBALR actuelles contiennent 170 cours d'eau nommés ; 2 129 objets
anonymes ont été retirés du GeoPackage de travail après vérification des
références. Les originaux de `cabbalr/cours_eau_work/` restent intacts. Démo garde
58 objets ; seuls trois noms synthétiques changent :

| UUID | Nom métier |
|---|---|
| `33e78301-dc78-5a54-be41-a3ea7d6ff73d` | Fossé démo A |
| `746637dd-3706-5b78-ae35-9b76fee85d51` | Écoulement démo B |
| `97e74118-4e72-5d4c-b6fc-f27f5e211444` | Fossé démo C |

Le schéma neuf impose un nom non NULL et non blanc. Il ne dépend d'aucun script
de transition. Le générateur CABBALR refuse aussi les sources anonymes.

### Préparer et faire relire les scripts

Depuis la racine, avec la sauvegarde du GeoPackage antérieur au nettoyage :

```sh
python3 model/preparer_transition_hydro_assoc.py
python3 model/preparer_transition_hydro_noms.py --original-cabbalr CHEMIN_SAUVEGARDE_GPKG
```

Ces commandes n'ouvrent aucune connexion PostgreSQL. Elles produisent dans
`audits/` les scripts ponctuels A (`HYDRO-ASSOC-01/transition.sql`), Démo
(`HYDRO-DEPLOIEMENT-01/migrations/demo-renommage-noms.sql`) et CABBALR
(`HYDRO-DEPLOIEMENT-01/migrations/cabbalr-nettoyage-noms.sql`). Le SQL CABBALR
embarque l'inventaire explicite des 2 299 UUID et noms d'origine. Un inventaire
original erroné, un ensemble différent en base ou une référence étrangère vers
un objet à supprimer provoquent un refus. Aucune suppression en cascade.
Conserver les sauvegardes et empreintes sous `audits/`, hors Git. Supprimer les
outils ponctuels de transition après vérification des deux déploiements réels ;
ne pas les transformer en dépendances d'installation.

### Démo

1. Suspendre les écritures métier ; diagnostiquer de nouveau schéma, 58 cours
   d'eau, trois UUID anonymes, prestations, mesures, rôles et dépendances.
2. Sauvegarder la base complète, schéma/droits inclus, et vérifier sa restauration
   sur une base isolée. Garder le plugin et les projets opérationnels précédents.
3. Après autorisation explicite, appliquer A puis contrôler le septième mode,
   les vues, les huit mesures et la conservation des prestations.
4. Appliquer le SQL Démo : renommer exactement trois objets puis imposer le nom
   obligatoire. La traçabilité du cours d'eau est préservée ; aucun rattachement,
   UUID, géométrie ou autre attribut ne change, y compris la prestation sur B.
5. Vérifier noms, mesures, droits et relations ; activer plugin 0.7.31 et QGZ
   compatibles, puis contrôler consultation, création, modification et rapports.

### CABBALR

1. Suspendre les écritures, refaire le diagnostic et sauvegarder/restaurer comme
   pour Démo. Comparer l'ensemble exact des UUID avec l'inventaire préparé.
2. Après autorisation explicite, appliquer A et vérifier les données et le schéma.
3. Appliquer le SQL CABBALR : il verrouille les tables, refuse toute dépendance
   vers un UUID supprimé, supprime les 2 129 objets explicitement inventoriés,
   puis impose les noms obligatoires. Toute anomalie annule la transaction.
4. Vérifier les 170 UUID nommés et leurs attributs/géométries, les repères, sections,
   prestations, huit mesures et droits des trois profils.
5. Activer ensuite seulement le QGZ CABBALR sans filtre hydrographique et le
   plugin 0.7.31. Conserver 25 couches PostgreSQL et 66 relations. Contrôler les
   widgets, catalogues, sélection, substitution spatiale et rapports.

Exécuter chaque script sur une connexion administrative avec arrêt au premier
échec (`psql -X --set=ON_ERROR_STOP=1 --file=...`), jamais avec un rôle métier.
Ne pas relancer aveuglément un script déjà validé : ils refusent cet état.
Les scripts de noms contrôlent les signatures complètes des prestations,
parents/enfants AH, sections et digues ainsi que propriétaires, ACL et options
avant validation. Ils ne changent aucun droit ni aucune qualification.

### Reprise et recette finale

Avant COMMIT, toute erreur impose ROLLBACK ; ne pas poursuivre dans une connexion
avec transaction en erreur. Après un COMMIT réussi, arrêter les écritures avant
une reprise. Restaurer la sauvegarde vérifiée sur une base isolée, comparer les
données et décider de la restauration complète ou d'une correction ciblée.
Ne pas reconstruire les cours d'eau supprimés depuis un export incomplet et ne
pas annuler A en supprimant la colonne si des prestations section AH existent.
Si B échoue après A, garder les applications suspendues et diagnostiquer B ;
A peut rester en place sans réaffecter les prestations historiques.

La qualification QGIS 3.34/3.40/3.44 (Ubuntu natif et Docker) est volontairement
reportée à la fin, après déploiement autorisé et stabilisation. La recette
Windows reste obligatoire avant diffusion générale. Les tests de préparation
n'équivalent pas à cette qualification.
