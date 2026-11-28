# SIG-FUSION-09 · Démonstration v0.6.1

## Inventaire et décisions

Source avant transformation : commit `8e8363b5688561a794584ac2fe047b73ad23b288`. Pour les 25 lignes, les coordonnées et le parent sont conservés strictement. Un UUID différent désigne un scénario fictif de remplacement. La surface déclarée et le type source sont conservés en commentaire.

| UUID source | Nom source | Type source | Géométrie | Site parent | Prestations | Destination et type | Motif | UUID cible |
|---|---|---|---|---|---:|---|---|---|
| 780ed467-e05b-5fc9-8cc3-b5c27b29d40d | Zone naturelle du secteur 01 | Zone humide | MULTIPOLYGON | Espace naturel du Bois des Aulnes (6fb4c2ae-3be1-5ba1-cc5f-31daadd0c6f4) | 7 | vegetation / BUISSONS_ARBUSTES | Scénario de fourré entretenu par débroussaillage | bff5831d-cf51-540b-a0b7-6186661c5df1 |
| fd2951d8-4fea-58f7-9001-916bcd9e70ec | Zone naturelle du secteur 02 | Espace boisé | MULTIPOLYGON | Marais des Trois Saules (3aeae4d1-b11c-e369-1689-7ab0d81adcc5) | 0 | vegetation / ARBRES | Boisement explicite | fd2951d8-4fea-58f7-9001-916bcd9e70ec |
| fcb46f36-90df-550e-a01a-a0406b0d3638 | Zone naturelle du secteur 03 | Prairie | MULTIPOLYGON | Terril du Bois des Dames (9eb31c5f-1542-bc55-481c-a574c9375a5e) | 0 | vegetation / HERBACEES | Couvert herbacé explicite | fcb46f36-90df-550e-a01a-a0406b0d3638 |
| 5244c330-5ed9-5cee-a36f-7ade8b8bca15 | Zone naturelle du secteur 04 | Corridor écologique | MULTIPOLYGON | Zone humide du Pré des Joncs (05446c45-bafe-4260-61dc-06a83477dfc1) | 0 | cheminements / AUT | Scénario de voie d’entretien du corridor, emprise surfacique | 433f073b-5ab1-5800-bbf1-0e4529b2116e |
| 0833c88a-7a46-56a5-9dbc-505695bc0c03 | Zone naturelle du secteur 05 | Marais | MULTIPOLYGON | Parc paysager des Saules (13e06e11-a784-0e52-d9b2-316732172afe) | 0 | vegetation / HERBACEES | Scénario de roselière sur le marais | 38459524-defe-57ee-be20-e4d0ee450ad9 |
| 8e82c4e2-7895-5adb-b9e6-31e36ffaa95f | Zone naturelle du secteur 06 | Prairie humide | MULTIPOLYGON | Bois du Petit Marais (b423ed8b-468a-121b-2a20-700694dacaa8) | 2 | vegetation / HERBACEES | Couvert herbacé explicite | 8e82c4e2-7895-5adb-b9e6-31e36ffaa95f |
| ae305883-cc61-5e1f-a201-246baddd0243 | Zone naturelle du secteur 07 | Zone humide | MULTIPOLYGON | Parc du Moulin Vert (b57bdd4e-d8a9-dd5d-7f8c-34526c512fcd) | 3 | vegetation / BUISSONS_ARBUSTES | Scénario de fourré entretenu par débroussaillage | 07115a09-9b63-5cf0-a6a3-169c19669cbf |
| 4abd7aa5-104f-56ff-873d-d8ac83f41990 | Zone naturelle du secteur 08 | Espace boisé | MULTIPOLYGON | Coulée verte du Val des Prés (6e9fb42d-bb39-0c57-e7b7-89c9c5a532b9) | 0 | vegetation / ARBRES | Boisement explicite | 4abd7aa5-104f-56ff-873d-d8ac83f41990 |
| 0ffdbbf2-1dd5-567d-884b-65a24bd27d7d | Zone naturelle du secteur 09 | Prairie | MULTIPOLYGON | Bois de la Grande Rosière (0a633343-f3a8-1328-4450-1a6f0060eeb7) | 0 | vegetation / HERBACEES | Couvert herbacé explicite | 0ffdbbf2-1dd5-567d-884b-65a24bd27d7d |
| 65f82de1-c9a0-504a-ab61-9ec7194ffacf | Zone naturelle du secteur 10 | Corridor écologique | MULTIPOLYGON | Terril des Bruyères (70f22923-dbe9-a171-3e37-fe0dac3da631) | 0 | cheminements / AUT | Scénario de voie d’entretien du corridor, emprise surfacique | 234bb599-1ce9-51d9-a16b-31f422c20413 |
| 244d75e5-bc7d-5815-b650-58799120d1c2 | Zone naturelle du secteur 11 | Marais | MULTIPOLYGON | Friche écologique des Quatre Vents (36044374-b91d-e253-59d6-3a237be2375d) | 0 | vegetation / HERBACEES | Scénario de roselière sur le marais | 01d3583e-9708-5404-8512-092779b87fde |
| 5dc5dccc-73af-59d8-9b30-52b0a81186b3 | Zone naturelle du secteur 12 | Prairie humide | MULTIPOLYGON | Prairies humides de la Nave (9e6cf606-da1c-cecf-51e8-6824fa0b9161) | 0 | vegetation / HERBACEES | Couvert herbacé explicite | 5dc5dccc-73af-59d8-9b30-52b0a81186b3 |
| cc982ca1-04b4-525e-afbc-9814390e54bd | Boisement du secteur 01 | Espace boisé | MULTIPOLYGON | Espace naturel du Bois des Aulnes (6fb4c2ae-3be1-5ba1-cc5f-31daadd0c6f4) | 0 | vegetation / ARBRES | Boisement explicite | cc982ca1-04b4-525e-afbc-9814390e54bd |
| ed400cba-64ac-53ab-a7a7-71392fdfa5e0 | Point d'observation du secteur 01 | Point d'observation | MULTIPOINT | Espace naturel du Bois des Aulnes (6fb4c2ae-3be1-5ba1-cc5f-31daadd0c6f4) | 0 | mobilier / PAN | Scénario de signalétique du point d’observation | 102757e4-f8ce-5047-b2bb-18a6e8447056 |
| 1c9d8376-72fa-595c-b103-b23378397d26 | Haie du secteur 01 | Haie | MULTILINESTRING | Espace naturel du Bois des Aulnes (6fb4c2ae-3be1-5ba1-cc5f-31daadd0c6f4) | 0 | vegetation / BUISSONS_ARBUSTES | Haie conservée, strate arbustive choisie pour la démo | 1c9d8376-72fa-595c-b103-b23378397d26 |
| f7d9dcc5-b942-54b6-88cf-e7c6e501a237 | Boisement du secteur 02 | Espace boisé | MULTIPOLYGON | Marais des Trois Saules (3aeae4d1-b11c-e369-1689-7ab0d81adcc5) | 0 | vegetation / ARBRES | Boisement explicite | f7d9dcc5-b942-54b6-88cf-e7c6e501a237 |
| 985fb671-1c91-590f-8b11-d570fe780da0 | Boisement du secteur 03 | Espace boisé | MULTIPOLYGON | Terril du Bois des Dames (9eb31c5f-1542-bc55-481c-a574c9375a5e) | 0 | vegetation / ARBRES | Boisement explicite | 985fb671-1c91-590f-8b11-d570fe780da0 |
| 28e8303c-cfb5-567a-b9ed-65c59223d541 | Point d'observation du secteur 03 | Point d'observation | MULTIPOINT | Terril du Bois des Dames (9eb31c5f-1542-bc55-481c-a574c9375a5e) | 0 | mobilier / PAN | Scénario de signalétique du point d’observation | 33d95a89-1a23-5373-98e3-254503578a6b |
| ef2c457b-9400-5471-953b-20d69b7cc8a5 | Haie du secteur 03 | Haie | MULTILINESTRING | Terril du Bois des Dames (9eb31c5f-1542-bc55-481c-a574c9375a5e) | 0 | vegetation / BUISSONS_ARBUSTES | Haie conservée, strate arbustive choisie pour la démo | ef2c457b-9400-5471-953b-20d69b7cc8a5 |
| 28373c1b-4c8f-5a1d-87a9-5a5be0536f67 | Boisement du secteur 06 | Espace boisé | MULTIPOLYGON | Bois du Petit Marais (b423ed8b-468a-121b-2a20-700694dacaa8) | 0 | vegetation / ARBRES | Boisement explicite | 28373c1b-4c8f-5a1d-87a9-5a5be0536f67 |
| 6af20212-9831-5f61-b8c6-619732d8b7a2 | Point d'observation du secteur 06 | Point d'observation | MULTIPOINT | Bois du Petit Marais (b423ed8b-468a-121b-2a20-700694dacaa8) | 0 | mobilier / PAN | Scénario de signalétique du point d’observation | 04bfcb97-f9d8-5b3a-afd4-ffc9a5eccbbf |
| 46f91339-0057-51ab-9cc8-b69ec6a92414 | Haie du secteur 06 | Haie | MULTILINESTRING | Bois du Petit Marais (b423ed8b-468a-121b-2a20-700694dacaa8) | 0 | vegetation / BUISSONS_ARBUSTES | Haie conservée, strate arbustive choisie pour la démo | 46f91339-0057-51ab-9cc8-b69ec6a92414 |
| 21b20688-2f42-5c93-be99-b9dd66c92f77 | Boisement du secteur 07 | Espace boisé | MULTIPOLYGON | Parc du Moulin Vert (b57bdd4e-d8a9-dd5d-7f8c-34526c512fcd) | 0 | vegetation / ARBRES | Boisement explicite | 21b20688-2f42-5c93-be99-b9dd66c92f77 |
| 8723feca-c404-55b9-a62d-26a2e000805a | Point d'observation du secteur 07 | Point d'observation | MULTIPOINT | Parc du Moulin Vert (b57bdd4e-d8a9-dd5d-7f8c-34526c512fcd) | 0 | mobilier / PAN | Scénario de signalétique du point d’observation | b8ea52c6-e308-5dcf-8f25-fc587bf5744f |
| dd78df20-581c-57e6-ae08-4567dce434e1 | Haie du secteur 07 | Haie | MULTILINESTRING | Parc du Moulin Vert (b57bdd4e-d8a9-dd5d-7f8c-34526c512fcd) | 0 | vegetation / BUISSONS_ARBUSTES | Haie conservée, strate arbustive choisie pour la démo | dd78df20-581c-57e6-ae08-4567dce434e1 |

## Prestations réaffectées

Les douze interventions décrivent un débroussaillage. Les sept interventions du secteur 01 et les trois du secteur 07 concernent le fourré fictif. Les deux du secteur 06 concernent la prairie humide. Chaque intervention conserve sa géométrie propre NULL, sa quantité déclarée, son unité et son UUID.

| UUID prestation | Intitulé | Zone source | Rattachement unique |
|---|---|---|---|
| 8b36ab40-2f75-5a11-a4af-83dcced846be | Débroussaillage des berges du fossé — rive gauche | 780ed467-e05b-5fc9-8cc3-b5c27b29d40d | vegetation_id = bff5831d-cf51-540b-a0b7-6186661c5df1 |
| 810f2f86-df40-5389-8a81-572c52bae0f5 | Débroussaillage des berges du fossé — rive droite | 780ed467-e05b-5fc9-8cc3-b5c27b29d40d | vegetation_id = bff5831d-cf51-540b-a0b7-6186661c5df1 |
| 60a6c622-d646-5791-8f88-49e4e2b1c54b | Débroussaillage des berges du fossé — tronçon nord | 780ed467-e05b-5fc9-8cc3-b5c27b29d40d | vegetation_id = bff5831d-cf51-540b-a0b7-6186661c5df1 |
| a98738cf-9e4e-5639-8bd2-a4da37f7bb39 | Débroussaillage des berges du fossé — tronçon sud | 780ed467-e05b-5fc9-8cc3-b5c27b29d40d | vegetation_id = bff5831d-cf51-540b-a0b7-6186661c5df1 |
| 454f4772-bd6b-51f0-81b9-2cd5a01351f2 | Débroussaillage des berges du fossé — abords des ouvrages | 780ed467-e05b-5fc9-8cc3-b5c27b29d40d | vegetation_id = bff5831d-cf51-540b-a0b7-6186661c5df1 |
| 95851a76-ea21-5a25-9c76-8be0aad4004a | Débroussaillage des berges du fossé — abords des ouvrages | 780ed467-e05b-5fc9-8cc3-b5c27b29d40d | vegetation_id = bff5831d-cf51-540b-a0b7-6186661c5df1 |
| 8e904660-31d5-5160-a894-9bdb08da2278 | Débroussaillage des berges du fossé — accès de maintenance | 780ed467-e05b-5fc9-8cc3-b5c27b29d40d | vegetation_id = bff5831d-cf51-540b-a0b7-6186661c5df1 |
| 3d0aa2cb-9b82-50b1-9214-73534984ce6d | Débroussaillage de la zone humide — secteur amont | 8e82c4e2-7895-5adb-b9e6-31e36ffaa95f | vegetation_id = 8e82c4e2-7895-5adb-b9e6-31e36ffaa95f |
| 7f0dd352-476a-5b0b-9518-099296df3d4b | Débroussaillage de la zone humide — rive gauche | 8e82c4e2-7895-5adb-b9e6-31e36ffaa95f | vegetation_id = 8e82c4e2-7895-5adb-b9e6-31e36ffaa95f |
| 97668893-eee1-5eb1-b788-a11617eb7552 | Débroussaillage de la zone humide — rive droite | ae305883-cc61-5e1f-a201-246baddd0243 | vegetation_id = 07115a09-9b63-5cf0-a6a3-169c19669cbf |
| bd96d3be-e9d7-5637-91a3-a681243805d7 | Débroussaillage de la zone humide — tronçon nord | ae305883-cc61-5e1f-a201-246baddd0243 | vegetation_id = 07115a09-9b63-5cf0-a6a3-169c19669cbf |
| b8c1cd4f-6b09-5a0f-aaf4-6012400a4c5c | Débroussaillage de la zone humide — tronçon sud | ae305883-cc61-5e1f-a201-246baddd0243 | vegetation_id = 07115a09-9b63-5cf0-a6a3-169c19669cbf |

## Bilan avant et après

| Objet fictif | Avant | Après | Contrôle |
|---|---:|---:|---|
| Sites terrestres | 12 | 12 | Identités et coordonnées des parents conservées |
| Zones | 25 | 0 | Couche source retirée du GeoPackage courant |
| Végétation / mobilier / cheminements | 0 / 0 / 0 | 19 / 4 / 2 | Tous enfants directs du site initial, autres parents NULL |
| AH / stockages / ouvrages AH / sections AH | 10 / 10 / 13 / 1 | 10 / 10 / 13 / 1 | Référence de section conforme |
| Cours d’eau | 58 | 58 | 1 qualifié, 57 sans direction validée |
| Digues / repères | 3 / 3 | 3 / 3 | UUID, WKB et signatures figés |
| Prestations | 100 | 100 | 88 géométries propres, 12 empruntées |
| Tronçons | 0 | 7 | Un de chaque type physique sur la Digue des Prés |
| Ouvrages particuliers / équipements / ouvrages hydrauliques | 0 / 0 / 0 | 1 / 1 / 1 | Escalier de crête, échelle limnimétrique de berge, vanne de franc-bord |
| Désordres / observations / photos patrimoniales | 0 / 0 / 0 | 2 / 4 / 3 | Deux constats successifs pour l’érosion active, constat de réparation pour l’affaissement archivé, lecture ordinaire sur l’équipement |

| Cible de prestation | Avant | Après |
|---|---:|---:|
| Cours d’eau | 62 | 62 |
| Digue | 1 | 1 |
| Stockage AH | 13 | 13 |
| Ouvrage AH | 6 | 6 |
| Site terrestre | 6 | 6 |
| Zone | 12 | 0 |
| Végétation | 0 | 12 |
| Tronçon, section AH, mobilier, cheminement | 0 | 0 |
| **Total** | **100** | **100** |

Le choix de famille suit le sens du libellé et le travail déclaré. Les quatre haies linéaires restent des végétaux. Les deux corridors deviennent, pour ce scénario, des emprises de voies d’entretien. Les quatre points d’observation sont représentés par leur signalétique. La décision de créer un nouvel objet porte sur dix lignes. Les quinze autres gardent leur UUID. Les 25 couples site/coordonnées ont été comparés individuellement à la version de départ. Les 25 géométries restent réparties en 17 MultiPolygon, 4 MultiLineString et 4 MultiPoint.

Les sept nouveaux tronçons utilisent sept portions successives du repère enregistré. Le découpage concerne uniquement les nouvelles formes fictives. L’escalier, l’échelle et la vanne se trouvent au milieu de leur tronçon respectif. Les UUID de ces scénarios sont fixes. Le choix des types physiques illustre le catalogue. Il ne constitue pas une qualification de terrain.

Les 100 UUID, les WKB propres et les attributs hors colonnes de reclassement ont la même empreinte SHA-256 avant et après dans le GeoPackage (`3341bf8d0ce2d854ddc622336602e309337cb4d98d7214509a97e5fc4f676e9f`). Les 12 liens remplacés figurent individuellement ci-dessus. L’archivage d’un désordre conserve ses enfants. Deux photos d’illustration utilisent des JPEG existants de `demo/photos/`. La troisième ligne conserve la clé explicite d’un fichier absent. Le circuit des prestations conserve ses 25 fiches illustrées localement, ses 25 fiches à références réseau et ses 50 fiches sans photo.

## Reconstruction et limites

Le point d’entrée `demo/data/importer_base_neuve.sh NOM_BASE` assemble les exports dans une transaction. La destination est une base nommée explicitement, accessible par socket Unix local et contrôlée avant création. Les catalogues sont chargés par le schéma. Les imports conservent les contrôles de clés et d’exclusivité. Pour les digues, le mécanisme existant de restauration des trois instantanés suspend seulement le trigger de préparation du repère dans sa transaction. Les trois supports restent déclarés non qualifiés. Le test compare les signatures et les coordonnées acceptées et vérifie la réactivation du trigger. L’axe hydrographique validé pour la section AH garde son orientation.

La démonstration concerne des données fictives. Les fichiers distants de prestations sont contrôlés par référence. Leur disponibilité sur le lecteur réseau n’a pas été testée. Le projet QGIS et le plugin attendent SIG-FUSION-10. La reprise des données réelles et l’adaptation éventuelle du migrateur relèvent de chantiers distincts.

## Contrôles de qualification

- **Sources spatiales.** Les deux GeoPackages modifiés passent les contrôles SQLite d’intégrité et de FK. Les générateurs reconstruisent leurs SQL depuis des copies des sources. Le test de topologie contrôle la contenance des 25 enfants dans leurs sites, la séparation des sous-emprises polygonales et l’absence de chevauchement surfacique avec les stockages.
- **Localisation effective.** L’audit en lecture seule retrouve 100 localisations cartographiques, dont 12 polygones multiples empruntés à l’enfant. Sur 88 formes propres, 86 se trouvent entre 0 et 10 m de leur patrimoine et deux entre 25 et 50 m. Le seuil de 25 m signale 32 ambiguïtés de proximité. Aucun cas ne franchit le seuil d’incohérence forte. Ces constats ne déclenchent aucun recalage.
- **Parents.** Les tests `PostgisPublic.test_cinq_parents` et `test_suppression_apres_reaffectation` ont réussi. Pour chacune des trois familles, exactement cinq des 32 masques ont été acceptés. Les autres parents du modèle restent disponibles aux futurs scénarios.
- **Référentiels.** Le contrôle dédié compare le classement, les codes et les UUID des types de prestations aux couches du GeoPackage, avec tests de nullabilité, de FK et de droits. Le test d’import compare les 298 valeurs des 22 catalogues au contrat v0.6.1.
- **Reproductibilité.** Deux installations indépendantes via le véritable importeur, avec PostGIS dans `public` et dans `extensions`, donnent 48 empreintes de table identiques. Le SHA-256 du relevé trié est `46d5461c10447a8fd4923f519292f303f73b0eb3f24d81382652856bca586133`. La comparaison inclut les identités, les champs métier et les EWKB. Elle exclut les auteurs et horodatages techniques susceptibles de varier à l’installation. Sur ces deux bases, chaque champ source des 100 prestations a également été comparé par UUID avec PostgreSQL, statut résolu par code et quantité lue en texte décimal.
- **Fonctionnement.** Les deux vues donnent une ligne par intervention. Les essais transactionnels vérifient le repli sur chacune des trois familles sans ajouter de prestation permanente au scénario. Les deux photos d’un même constat, les dates des clichés, la référence manquante et le maintien des trois photos après archivage sont contrôlés. Le banc vérifie également le refus d’une invocation sans nom de base et d’une réinstallation sur la destination occupée.
