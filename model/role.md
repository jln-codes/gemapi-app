# Rôles PostgreSQL du modèle patrimonial GEMAPI-App-SIRS

Matrice cible : chaque utilisateur PostgreSQL possède un compte individuel `LOGIN`. Les rôles collectifs `NOLOGIN` sont hiérarchiques : Consultation → Gestion des prestations → Gestion du patrimoine ; chaque rôle hérite des droits du précédent.

Les trois profils couvrent le schéma applicatif unique `gemapi`. Leurs noms de rôles PostgreSQL conservent le préfixe `milieux_`.
Une prestation peut viser dix catégories de patrimoine. Le profil Prestations
peut choisir une cible existante. Les triggers prennent les verrous nécessaires
à la validation de la section AH et au calcul des mesures empruntées. Les
interventions sur une section AH conservent leur géométrie propre obligatoire.

| Tables du [schéma courant](schema.sql) | Consultation | Gestion des prestations | Gestion du patrimoine |
| --- | --- | --- | --- |
| `prestations` | S | SIUD | SIUD |
| `ah`, `ah_stockage`, `ah_ouvrage`, `ah_sections`, `sites_terrestres`, `cours_eau`, `digues`, `digues_reperes` | S | S | SIUD |
| `techniciens`, `prestataires`, `communes`, `prestations_categorie`, `types_prestations`, `statuts_prestations` | S | S | S |
| 10 tables métier et 4 associations patrimoniales | S | S | SIUD |
| 19 catalogues patrimoniaux | S | S | S |
| Vues `prestations_carte`, `prestations_fiches`, `digues_carte`, `ah_sections_carte`, `prestations__ah`, `prestations__sites_terrestres` | S | S | S |
| `TRUNCATE` (toutes les tables) | — | — | — |

S = `SELECT`, I = `INSERT`, U = `UPDATE`, D = `DELETE` ; — = aucun droit. Le service SIG administre l'installation PostgreSQL, les référentiels réservés et la structure des tables. PostgreSQL garantit ces droits, indépendamment du plugin QGIS. `DELETE` peut supprimer plusieurs lignes.

Traçabilité : `modifie_par` enregistre le compte PostgreSQL authentifié (`session_user`). Le technicien responsable (`prestations.technicien_id`) est un attribut métier, qu'il dispose ou non d'un compte PostgreSQL ; il ne confère aucun droit.

Sur une base neuve, appliquer `model/schema.sql`, puis `model/roles_milieux.sql` avec le compte administrateur. L’emplacement de PostGIS est détecté dans `pg_extension`. Les droits sur les tables visent le seul schéma `gemapi`.

`roles_milieux.sql` crée uniquement les trois rôles collectifs `NOLOGIN`. Les
vues `prestations__*` sont des vues de consultation, pas des tables d'association
à modifier. Le profil patrimoine possède aussi les droits de lecture et de
verrouillage du support hydrographique nécessaires aux préparations serveur
des digues et sections AH ; leurs géométries ne sont pas éditées librement.

Les comptes `LOGIN` héritent d'un seul profil métier, sans option ADMIN,
SUPERUSER, CREATEDB, CREATEROLE, REPLICATION ou BYPASSRLS. Le fournisseur QGIS
doit pouvoir résoudre les fonctions PostGIS. Le service libpq peut fixer son
`search_path` à `pg_catalog`, au schéma effectif de PostGIS puis à `pg_temp`.
Les requêtes applicatives qualifient explicitement leurs tables dans `gemapi`.
Les mots de passe doivent être définis hors des SQL versionnés. Le poste CABBALR
conserve ses trois mots de passe dans `CABBALR_IDENTIFIANTS.local.txt`, fichier
texte privé à la racine, ignoré par Git. QGIS les demande à l'ouverture du projet,
sans dépendance à `.pgpass`, aux services ou au coffre système ; voir le
[registre d'accès](../CABBALR_ACCES.md).

Pour CABBALR, les comptes fonctionnels validés sont `cabbalr_lecture`,
`cabbalr_prestations` et `cabbalr_patrimoine`, respectivement associés aux trois
profils ci-dessus. Une connexion partagée trace le compte fonctionnel utilisé,
pas une personne. Ces comptes PostgreSQL ne sont pas des utilisateurs Supabase
Auth et n'ont aucun droit d'administration du projet Supabase.

L'installation CABBALR utilise le projet `cabbalr`
(`fmgeqjspogvyhprvinnw`, organisation `jln-codes`, région `eu-west-1`),
distinct du démonstrateur. Pour le pooler **Session**, port 5432, les noms de
connexion sont respectivement
`cabbalr_lecture.fmgeqjspogvyhprvinnw`,
`cabbalr_prestations.fmgeqjspogvyhprvinnw` et
`cabbalr_patrimoine.fmgeqjspogvyhprvinnw`. PostgreSQL conserve le nom court
comme `session_user` ; le suffixe sert au routage du pooler.
L'hôte validé est `aws-1-eu-west-1.pooler.supabase.com`.

Le fichier local de mots de passe est exclu du suivi Git. Les anciennes entrées
CABBALR du coffre système et des fichiers libpq ont été supprimées après validation
des nouveaux accès. Aucune rotation n'est effectuée sans validation explicite ;
le compte administrateur `postgres` n'est pas concerné.

Les deux projets QGIS Démo et CABBALR, leurs connexions propres et leur
synchronisation sont décrits dans [les instructions QGIS](../docs/qgis_relations.md#connexions-et-comptes).

Les fonctions `digue_enregistrer` et `digue_supprimer` sont exécutables uniquement
par Patrimoine et utilisent `SECURITY INVOKER`. Elles ne confèrent aucun droit
supplémentaire sur les tables. La première contrôle aussi la signature du tracé
prévisualisé, la révision du repère et la date de modification du parent. La
seconde vérifie sous verrou les prestations, tronçons et désordres rattachés directement à la digue. Les FK protègent aussi les objets liés.
