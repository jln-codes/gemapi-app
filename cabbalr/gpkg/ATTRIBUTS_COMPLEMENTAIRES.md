# Attributs CABBALR hors modèle canonique — proposition à valider

Les SQL de `sql/` chargent uniquement le modèle canonique actuel. Ils ne
constituent pas une migration intégrale de tous les attributs CABBALR.
Ce document propose leur conservation ; **il ne modifie pas le schéma**.

L'inventaire exhaustif [`attributs_complementaires.json`](attributs_complementaires.json)
contient, pour chaque UUID de site ou zone, toutes les valeurs des sept champs
ci-dessous, y compris les NULL. Il est régénéré depuis les sources et couvert
par `sql/SHA256SUMS`. Les GeoPackages d'origine restent conservés sans modification.

| Couche / champ | Type SQLite source | Valeurs actuelles | Correspondance possible, soumise à décision |
|---|---|---|---|
| Sites / `surface_m2` | `MEDIUMINT` | 19 renseignées | Ajouter un attribut métier de surface déclarée en m² ; conserver la valeur source, sans substitution par une mesure géométrique. |
| Sites / `surface_ha` | `MEDIUMINT` | 19 renseignées | Ajouter un attribut de surface déclarée en hectares ; les entiers source ne doivent pas être transformés en mesures plus précises inventées. |
| Zones / `niveau` | `MEDIUMINT` | 41 renseignées, valeurs 0 et 2 | Conserver dans un attribut entier ; expliciter la signification métier avant toute nomenclature. |
| Zones / `longueur` | `MEDIUMINT` | 41 renseignées | Conserver la longueur déclarée ; confirmer l'unité et la règle métier avant un éventuel champ numérique cible. Ne pas recalculer depuis le tracé. |
| Zones / `entretien` | `TEXT(256)` | 17 renseignées, 24 NULL | Attribut texte décrivant l'entretien ; aucune conversion automatique en dates ou fréquences normalisées. |
| Zones / `gestionnaire` | `TEXT(256)` | 17 renseignées, 24 NULL | Attribut texte ; un référentiel de gestionnaires demanderait une validation distincte et des correspondances explicites. |
| Zones / `type` | `TEXT(256)` | 41 renseignées, 6 libellés | Les valeurs sont déjà reprises dans `nom` et `type_site` sur les sources actuelles. Valider si `type_site` devient la destination de référence, tout en conservant la provenance et le champ source jusqu'à décision. |

## Proposition de conservation

Pour cette préparation, conserver ensemble les huit GeoPackages, l'inventaire
JSON exhaustif et leurs empreintes. Les données non chargées dans PostgreSQL
restent ainsi disponibles, reliées par leurs UUID, sans être présentées comme
déjà migrées. L'inventaire ne remplace pas les fichiers sources.

Avant une migration permanente déclarée complète, valider les champs métier
nécessaires dans les tables concernées et leur type, puis adapter **ensemble**
le schéma canonique, les générateurs et les tests. Les ajouts proposés ci-dessus
sont une piste de décision, pas une nouvelle structure déjà implémentée.

Il ne faut ni créer silencieusement des colonnes ad hoc à l'import, ni effacer
les champs sources, ni prétendre que la projection canonique seule conserve
toute l'information. Aucun de ces attributs ne doit servir à modifier les
géométries, les rattachements, les quantités ou les unités d'une prestation.
