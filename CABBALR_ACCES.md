# Accès PostgreSQL CABBALR

Ce document public ne contient aucun mot de passe. Il concerne uniquement le
projet Supabase `cabbalr`, distinct du démonstrateur `sig-milieux-demo`.

## Serveur et profils

| Paramètre | Valeur |
| --- | --- |
| Projet | `cabbalr` — `fmgeqjspogvyhprvinnw` |
| Organisation / région | `jln-codes` / `eu-west-1` |
| Serveur Session pooler | `aws-1-eu-west-1.pooler.supabase.com` |
| Port / base / schéma | `5432` / `postgres` / `milieux` |
| TLS du projet autonome | `require` |

| Profil | Nom complet à saisir dans QGIS ou psql | Droits |
| --- | --- | --- |
| Lecture | `cabbalr_lecture.fmgeqjspogvyhprvinnw` | Consultation |
| Prestations | `cabbalr_prestations.fmgeqjspogvyhprvinnw` | Consultation et création/modification/suppression des prestations |
| Patrimoine | `cabbalr_patrimoine.fmgeqjspogvyhprvinnw` | Droits précédents et gestion des patrimoines, repères de digues et sections AH |

Les noms de comptes sont conservés. Le suffixe `.fmgeqjspogvyhprvinnw` sert
au routage du pooler ; PostgreSQL identifie les comptes par leur nom court.
Ces comptes ne sont pas des utilisateurs Supabase Auth et n'administrent
ni le schéma, ni les rôles, ni le projet. La matrice des permissions figure
dans [`model/role.md`](model/role.md).

## Retrouver les mots de passe

Le registre local unique est le fichier texte :

`CABBALR_IDENTIFIANTS.local.txt`

Chemin cible sur le poste Ubuntu après renommage :
`/home/julien/Projects/gemapi-app/CABBALR_IDENTIFIANTS.local.txt`.
Chemin cible sur le poste Windows après synchronisation :
`C:\Users\julien.lorion\gemapi-app\CABBALR_IDENTIFIANTS.local.txt`.

L'ouvrir directement dans un éditeur de texte. Il contient l'hôte, le port,
la base, les trois noms complets et leurs mots de passe actifs. Il est en
texte clair, avec permissions Linux **0600**, et explicitement ignoré par Git.
Il ne fait pas partie d'un clone du dépôt et ne doit jamais être commité.

Les trois phrases de passe sont distinctes et faciles à saisir en ASCII,
sans accent. Elles ont été renouvelées le **12 novembre 2026**, sans renommer
les comptes ni changer leurs droits. Les anciens mots de passe ont été
vérifiés comme refusés sur de nouvelles connexions.

Les anciennes entrées de ces trois comptes ont été retirées de GNOME Keyring,
`.pgpass` et `.pg_service.conf`. L'ancien fichier de bascule
`.config/sig-prestations/pg_service_cabbalr.conf` a été supprimé. Les accès de
la Démo et les autres configurations PostgreSQL sont préservés.
Aucun coffre, fichier de service ou fichier libpq de mots de passe n'est
nécessaire pour utiliser le projet CABBALR.

## Ouvrir le projet QGIS

| Projet | Destination |
| --- | --- |
| `demo/prestations_demo.qgz` | Supabase `sig-milieux-demo` |
| `cabbalr/prestations_cabbalr.qgz` | Supabase `cabbalr` |

1. Ouvrir `cabbalr/prestations_cabbalr.qgz` dans QGIS 3.44.
2. Dans l'invite PostgreSQL, saisir le **nom complet** du profil souhaité et
   son mot de passe, consultés dans le fichier local.
3. Les 25 couches PostgreSQL et le plugin utilisent ce compte pour la session.
   Une seule invite est nécessaire dans une session vierge.
4. Fermer complètement QGIS avant de rouvrir le projet avec un autre compte.

Le `.qgz` reste autonome : hôte, port, base et TLS intégrés, sans utilisateur
prérempli, mot de passe, service, `authcfg` ou certificat local obligatoire.
TLS `require` conserve le compromis du projet portable : chiffrement du
trafic sans imposer une autorité de confiance sur le poste destinataire.

Les trois connexions facultatives **CABBALR - Lecture**, **CABBALR - Prestations**
et **CABBALR - Patrimoine** de l'Explorateur QGIS utilisent désormais une
connexion directe et leur nom complet, sans mot de passe enregistré.
Sélectionner l'une de ces connexions ne change pas le compte des couches
d'un projet déjà ouvert ; le compte du projet se choisit à son ouverture.

Pour transmettre le projet à un collègue, envoyer le seul `.qgz` puis
communiquer séparément le nom complet et le mot de passe du profil autorisé.
Ne pas joindre le registre des trois mots de passe au projet QGIS.
Le collègue n'a besoin ni de `.pgpass`, ni de `.pg_service.conf`, ni du trousseau.

## Connexion psql

Exemple pour Lecture, avec saisie du mot de passe dans l'invite masquée :

```sh
psql -X -W "host=aws-1-eu-west-1.pooler.supabase.com port=5432 dbname=postgres user=cabbalr_lecture.fmgeqjspogvyhprvinnw sslmode=require"
```

Pour les autres profils, remplacer uniquement l'utilisateur par le nom complet
correspondant. Ne jamais ajouter le mot de passe à cette commande ou à une URI.

Contrôle d'identité sans écriture :

```sql
SELECT current_user, session_user;
```

La traçabilité `modifie_par` utilise `session_user`. Les noms étant conservés,
la rotation ne change ni les valeurs historiques ni les noms enregistrés lors
des prochaines modifications. Le technicien responsable reste indépendant du
compte de connexion.

## Édition et configuration commune

La couche **prestations** utilise directement `milieux.prestations` :
Prestations et Patrimoine peuvent l'éditer ; Lecture reste en consultation.
`prestations_fiches` et les couches cartographiques restent des vues de
consultation. Les huit mesures PostgreSQL sont en lecture seule.

Les identifiants des 25 couches, les 62 relations, les formulaires, styles et
actions restent communs aux deux projets. Leurs connexions et emprises restent
propres à chaque environnement. La synchronisation est décrite dans
[`docs/qgis_relations.md`](docs/qgis_relations.md#synchroniser-les-deux-projets).

Les contrôles effectués sur ce poste sont Linux. Une recette QGIS Windows
reste à effectuer ; le projet portable et le fichier texte peuvent être
transmis séparément, sans configuration libpq préalable.
