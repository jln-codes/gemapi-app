# Contrat de migration SIRS → GEMAPI-App-SIRS

Version documentaire v0.5 — SIG-FUSION-05. Base v0.4 : `1246f650ace55cc171ea0941ce07f915932b013a`.

Ce contrat décrit une **future** adaptation du migrateur. Aucun SQL, GPKG, jeu opérationnel, `model.json` ou code de migration n'est modifié. La projection cible est `schema_development_v0.5.mmd`. Les ambiguïtés doivent produire un diagnostic nominatif d'objet (UUID, table/colonne, valeurs sources, cause, décision attendue), sans publication d'objet partiellement converti. Le support de diagnostic d'une exécution ne constitue ni une table d'archive métier ni un nouveau journal permanent.

## Règles communes d'import

Conserver l'UUID quand l'identité ne change pas. Toute collision doit comparer provenance et identité métier : ne jamais écraser, réattribuer aléatoirement un UUID ni fusionner sur le nom ou la proximité. Une correspondance approuvée peut être utilisée ; plusieurs correspondances restent un échec. Vérifier parents et référentiels avant insertion. Les données non convertibles restent dans leurs sources non modifiées jusqu'à décision ; elles ne sont pas considérées comme migrées. Les pertes non explicitement autorisées interdisent la suppression des sources. Une conversion doit être déterministe et réexécutable sans doublon, à données et décisions identiques.

## 1. Zones CABBALR → cheminements

1. **Source** : `cabbalr/gpkg/sites_zones.gpkg:sites_zones`, `cabbalr/data/sites_zones.gpkg` et SQL dérivés. 41 UUID, 41 MultiLineString valides/non vides, 2D, EPSG:3950. Il n'existe pas de production sites_zones à préserver selon la décision métier.
2. **Destination** : `public.cheminements`, parent `site_terrestre_id` ; suppression de `milieux.sites_zones` et des FK zone des prestations/désordres, sans table générique de remplacement.
3. **Conversion** : id → id ; site_terrestre_id (ou sites_terrestres_id dans la source brute) → site_terrestre_id ; nom → designation ; geom → geometry **à coordonnées identiques**. Troncon_id et ah_ouvrage_id restent NULL. Escalier → ESC proposé ; sentiers → AUT proposé, en conservant leur appellation exacte. La sélection de type doit être validée, pas devinée. Le même UUID peut remplacer site_zone_id par cheminement_id dans les objets référents après validation de la correspondance.
4. **Échec** : parent manquant/inconnu, UUID conflictuel, désignation vide, géométrie invalide/vide/SRID inconnu. Un objet nommé « Grillage » parmi les 41 nécessite une qualification explicite avant attribution de son type de cheminement ; aucun basculement silencieux vers mobilier. Le GPKG séparé de six polygones n'est pas une correspondance prouvée et ne doit pas être fusionné avec les 41 lignes.
5. **Information** : aucun attribut métier réel à perdre silencieusement. type/type_site, niveau, longueur déclarée, entretien, gestionnaire et surface_ha n'ont pas tous de colonne dédiée cible : les préserver dans un commentaire déterministe à clés nommées, sans réinterpréter longueur/surface comme mesure calculée. Conserver l'ordre des clés et distinguer NULL et vide. Un commentaire existant est conservé avant ce complément. Dates métier absentes → NULL. Création et dernière écriture suivent la règle 3, jamais une date inventée.
6. **Tests futurs** : égalité des 41 UUID, parents et coordonnées ; aller-retour des attributs dans le commentaire ; type explicitement validé ; unicité des cibles ; pas de perte des prestations/désordres liés ; comptes d'import et absence de table/FK zone. Aucune transformation LineString/Polygon forcée. Si autre SRID connu, ST_Transform contrôlé ; jamais ST_SetSRID pour maquiller des coordonnées.

## 2. Démo et fichiers opérationnels de sites

1. **Source** : les 25 zones fictives du GPKG démo et leurs générateurs/SQL ; 17 MultiPolygon, 4 MultiPoint, 4 MultiLineString.
2. **Destination** : scénarios fictifs explicitement répartis entre site direct, végétation, mobilier et cheminements.
3. **Conversion** : pas de conversion globale en végétation ou cheminements. Définir une matrice de scénarios reproductible ; réutiliser un UUID uniquement si l'objet garde son identité. Adapter les prestations pour la cible retenue et les géométries effectives. Ne jamais utiliser les données réelles CABBALR comme fixtures.
4. **Échec** : classification non validée, parents absents, changement d'identité masqué par un UUID conservé.
5. **Information** : adaptation de données fictives autorisée à une étape future ; aucune suppression maintenant. La décision de suppression de famille ne justifie pas de retirer la démo entière.
6. **Tests futurs** : génération déterministe, installation neuve sur modèle cible, égalité des bilans et mesures attendus, aucune ancienne zone active ; adapter toutes les dépendances nommées dans `SIG-FUSION-05-audit.md`.

## 3. Auteurs informatiques, création et dates métier

1. **Source** : created_by, edited_by, métadonnées historiques SIRS et dates métier ; champs actuels du socle.
2. **Destination** : cree_le, modifie_par et date_modification sur chaque table métier ; aucun contact importé pour l'auteur informatique.
3. **Conversion** : nouvelle insertion → date réelle d'import informatique clock_timestamp() et compte réel session_user ; modification → compte et date de cette écriture, sans changer cree_le. Lorsqu'une date de création informatique fiable et de même sens est déjà connue, sa reprise doit être explicitement validée avant import ; ne pas confondre date métier et création de ligne.
4. **Échec** : horodatage illisible, fuseau inconnu ou sens ambigu ; ne pas remplacer par une date métier ou par un auteur supposé.
5. **Information** : suppression des identités informatiques SIRS décidée ; consigner leur présence et la règle de non-reprise, sans les faire passer pour le dernier auteur GEMAPI. Dates métier et contenu utiles préservés ; métadonnées non résolues signalées.
6. **Tests futurs** : DEFAULT serveur, immuabilité de cree_le, stamp de dernière écriture, fuseaux et reprises déterministes ; refus d'une mise à jour de création. Ne pas importer attribution_contact ni les FK created_by/edited_by.

## 4. Observateur et photographe

1. **Source** : observations.observateur_id et photos.photographe_id vers public.contacts.
2. **Destination** : observateur TEXT et photographe TEXT facultatifs, sans FK ni registre de contacts. Techniciens, prestataires et comptes PostgreSQL restent des concepts distincts.
3. **Conversion** : recopier une mention nominative attestée par le contact source, avec une convention de présentation stable documentée. Ne pas déduire la personne du compte informatique. Une correspondance vers un technicien/prestataire n'est utilisée que si elle est explicitement validée pour le rôle concerné ; elle ne modifie pas ces colonnes en FK.
4. **Échec** : contact introuvable, libellé absent ou plusieurs identités possibles. Signaler UUID et contexte, ne pas insérer une attribution inventée. Les homonymes ne prouvent jamais une identité.
5. **Information** : la relation au registre contacts disparaît du modèle ; préserver l'attribution documentaire lorsqu'elle est connue. L'abandon de métadonnées métier additionnelles des contacts n'est pas globalement autorisé : relever les pertes et demander une décision avant suppression de source.
6. **Tests futurs** : personnes non techniciennes admissibles, accents et noms identiques conservés sans fusion, aucune FK contacts, aucune attribution remplie avec session_user par défaut.

## 5. Parents exclusifs des ouvrages hydrauliques

1. **Source** : troncon_id, amenagement_hydraulique_id, zone_stockage_id ; éventuels objets multi-parents ou orphelins.
2. **Destination** : troncon_id, ah_ouvrage_id, ah_stockage_id mutuellement exclusifs.
3. **Conversion** : résoudre chaque identité avec une correspondance métier approuvée ; n'insérer qu'au plus un parent. Le contrat v0.5 est `num_nonnulls(...) <= 1`. Proposer séparément `=1` pour une cible finale obligatoire : décision non acquise sur les situations sans parent.
4. **Échec** : plusieurs parents, absence de correspondance, AH parent global correspondant à plusieurs ouvrages. Zéro parent est permis provisoirement par la projection mais doit être diagnostiqué avant publication d'un lot d'import ; le lot ne peut être annoncé complet tant que le sort de ces objets n'est pas décidé.
5. **Information** : ne pas choisir un parent au hasard, fabriquer un parent ni supprimer une référence concurrente silencieusement. Les UUID d'ouvrages sont conservés.
6. **Tests futurs** : matrice des huit combinaisons de parents ; seuls zéro et un parent passent le CHECK v0.5 ; conflits et orphelins apparaissent au diagnostic, aucun appariement par nom/proximité.

## 6. Repérage SIRS et abscisses géométriques

1. **Source** : systèmes, bornes, PR, offsets, sens et positions SIRS, parfois sans XY ; troncons.systeme_reperage_defaut_id.
2. **Destination** : geometry propre et geometry_reperage distinctes ; calculs PostGIS à la demande, sans table de système ou bornage intermédiaire.
3. **Conversion** : conserver un XY attesté après contrôle du SRID. Sur un axe orienté, simple, non vide et de longueur positive, fraction connue f → ST_LineInterpolatePoint ; distance d depuis une origine attestée → f=d/longueur. Contrôler unité, sens, domaine et tolérance. ST_LineLocatePoint projette un XY sur l'axe mais ne prouve pas sa justesse métier. Les deux extrémités ne donnent pas automatiquement un axe droit si un tracé courbe est inconnu.
4. **Échec** : seul PR sans calibration, borne absente, axe manquant, sens inconnu, multi-parties ambiguës, position hors intervalle, décalage excessif. Diagnostic non convertible ; pas de point inventé, interpolation arbitraire ni géométrie reconstruite sur simple proximité.
5. **Information** : les mécanismes de repérage SIRS ne sont pas repris. Leur suppression de structure est décidée ; la perte d'une localisation métier non convertible ne l'est pas. Conserver la source jusqu'à décision et tracer le diagnostic. digues_reperes et ah_sections du socle sont préservés.
6. **Tests futurs** : extrémités 0/1, inversion d'axe, axes nuls/vides, SRID, sens, longueurs métriques, XY absent et offsets ambigus ; aucune nouvelle FK vers bornes ou systèmes.

## 7. Convergence des observations vers troncon_id

1. **Source** : troncon_id, berge_id et structure_digue_id, avec discriminants composites historiques.
2. **Destination** : une FK simple troncon_id vers public.troncons(id), tous types physiques autorisés.
3. **Conversion** : après résolution explicite des identités, former l'ensemble des UUID non NULL. Un UUID distinct → troncon_id. Plusieurs pointeurs identiques → un pointeur, avec diagnostic de doublon. Aucun UUID → examiner les autres cibles autorisées. Supprimer les discriminants BERGE et true des observations seulement.
4. **Échec** : plusieurs UUID distincts ou coexistence avec une autre cible métier. Aucun écrasement même si géométries ou noms sont proches.
5. **Information** : qualification du type portée par le tronçon ; pas de fusion d'objets ni modification de ses supports. Les rôles historiques des pointeurs restent dans le diagnostic de conversion si nécessaire, pas comme plusieurs cibles actives.
6. **Tests futurs** : toutes combinaisons NULL/égales/distinctes ; 13 cibles en exclusivité ; FK et UUID ; absence des anciennes colonnes/discriminants et préservation des supports internes.

## 8. Cibles d'observation et constats datés

1. **Source** : toute observation, avec sa date et ses cibles SIRS.
2. **Destination** : exactement une des 13 cibles du Mermaid, date_observation NOT NULL ; conservation de l'UUID, désignation, évolution, suite, urgence, valid, version et nombre_desordres.
3. **Conversion** : reprendre date et contenu attestés. AH/stockage nécessitent la correspondance de la règle 11. Site direct possible avec ou sans enfants. Une observation ordinaire n'exige aucun désordre. Les visites successives restent des observations distinctes, jamais agrégées automatiquement.
4. **Échec** : cible hors périmètre (réseaux, voirie, profils, organes, prestations, etc.), zéro ou plusieurs cibles, date absente. Diagnostiquer l'observation et ses photos comme ensemble non convertible, sans la recaser arbitrairement sur un parent ni utiliser la date d'import.
5. **Information** : suppression des colonnes hors périmètre décidée, suppression silencieuse du contenu des constats non autorisée. Urgence et nombre_desordres ne reçoivent aucune nouvelle règle de calcul automatique.
6. **Tests futurs** : les 13 cibles isolées passent ; toutes paires et zéro échouent ; sites sans enfant admis ; dates absentes rejetées ; aucune création de désordre implicite.

## 9. Désordres persistants et archivage

1. **Source** : désordre SIRS V2, observations successives, date_fin et photos.
2. **Destination** : même UUID de désordre, mêmes UUID d'observations et photos ; `date_fin` seule détermine actif/archivé.
3. **Conversion** : date_fin NULL → actif ; non NULL → archivé. Reprendre la date sans inventer un événement ou statut. Le lien observation → désordre reste 1:N ; aucun déplacement automatique vers le patrimoine direct.
4. **Échec** : dates illisibles, observation sans désordre correspondant, identité en conflit. Diagnostiquer ; ne pas supprimer les enfants pour résoudre une FK.
5. **Information** : aucun contenu de suivi perdu du fait de l'archivage. Urgence d'observation ≠ statut du désordre. Pas de table d'archive, statut ou enum ajouté.
6. **Tests futurs** : archivage conserve tous les enfants et fichiers ; réouverture par date_fin NULL si autorisée ultérieurement ; observation directe sans désordre valide ; associations techniques distinctes des cibles directes.

## 10. Photographies patrimoniales et de prestations

1. **Source** : photos SIRS avec observation, géométrie, repérage et attribution ; photo_1/photo_2 des prestations.
2. **Destination** : photos enfant obligatoire d'une observation datée, sans géométrie, position, borne, PR ou cote_id. Les photos des prestations restent directes.
3. **Conversion** : préserver id, observation_id, date_photo attestée, designation, commentaire, storage_key, valid et version. Photographe selon règle 4. La localisation est celle de la cible de l'observation ; pour un désordre sans géométrie, localisation indisponible, pas de point synthétique. Un cliché documentaire sans anomalie reste un constat ; s'il manque une observation, sa création future exige une date et une cible attestées, sinon diagnostic.
4. **Échec** : observation absente/non convertible, fichier non accessible ou clé en collision, plusieurs fichiers sous une même identité. La date de photo n'est pas automatiquement une date de visite ; une correspondance ne peut être créée sans validation.
5. **Information** : abandon de la localisation propre de photo explicitement décidé, y compris cote_id. Présenter au diagnostic toute divergence entre emplacement source et cible ; ne pas reporter ces coordonnées sur le patrimoine. Conserver le fichier et son UUID. Aucune table commune de photos illimitées créée pour les prestations.
6. **Tests futurs** : aucune colonne géométrique ou de repérage dans photos ; aucune photo patrimoniale sans observation ; storage_key unique si renseignée ; photos de prestations sans observation intermédiaire ; conservation des enfants lors d'archivage.

## 11. Identités AH, stockages et structures

1. **Source** : public.amenagements_hydrauliques, public.zones_stockage et leurs structures.
2. **Destination** : pour observations et ouvrages hydrauliques, ah_ouvrage_id/ah_stockage_id internes ; pour structures AH, cibles internes seulement **proposées**, deux FK externes conservées en v0.5.
3. **Conversion** : une table de correspondance d'import approuvée associe source, UUID, famille et destination. Aucun rapprochement sur nom, ordre ou seule géométrie. Un AH global n'est pas un ouvrage linéaire constitutif. Un ancien stockage doit correspondre au contrat Polygon et au stockage unique par AH du socle, sans regroupement automatique.
4. **Échec** : absence, multiplicité ou conflit de correspondance ; ancien stockage sans parent, plusieurs stockages sources pour le même AH, géométrie incompatible. Aucun UUID inventé ni découpage automatique de structures.
5. **Information** : conserver identité, géométrie et couches des structures individualisées ; ne pas les absorber dans nature/matériau d'un tronçon. Le modèle n'est pas autonome tant que ces deux FK externes et le support hydrographique subsistent.
6. **Tests futurs** : correspondances bijectives quand l'identité est la même ; traitement explicite des cardinalités différentes ; compatibilité des géométries ; aucune FK vers AH global pour observations/ouvrages hydrauliques ; statu quo des structures tant que non arbitré.

## 12. Objets liés, référentiels et attributs non repris

1. **Source** : objets liés vers familles absentes ; référentiels et attributs SIRS déjà écartés par v0.1 à v0.4.
2. **Destination** : six cibles internes d'objets liés et 22 référentiels v0.5. digue_id technique → milieux.digues sur correspondance explicite. Les trois associations désordre/équipement ou ouvrage conservées ne sont pas remplacées par de nouveaux N:N.
3. **Conversion** : retirer les termes voirie/réseaux/télécom de la contrainte d'objet lié ; conserver exactement une des six cibles restantes. Pour les catalogues, préserver les codes déjà retenus ; les quatre types mobilier ajoutés en v0.4 restent BAR/POR/BOR/OBS. Échelles, piézomètres, repères et stations suivent les correspondances d'équipements décidées en v0.2. Urgences v0.2 : RefUrgence:2 rejoint RefUrgence:1 (Faible), sans nouvelle classification.
4. **Échec** : ligne liée devenue sans cible, cible inconnue, code absent du référentiel, plusieurs objets candidats. Diagnostic, pas de table fictive. Les types Gabarit, Parking, Grille avaloir et Bouchure ne sont pas ajoutés automatiquement.
5. **Information** : suppression des familles/colonnes projetées ne vaut pas acceptation de toute perte métier source. Signaler notamment les mesures de tronçons et caractéristiques hydrauliques retirées en v0.4, les spécialités de cheminements/végétation non reprises et les relations externes non convertibles. Conserver les valeurs originales dans la source tant que leur sort n'est pas validé. La désignation remplace libelle : reprendre si destination vide, garder si égal, conflit bloquant sinon.
6. **Tests futurs** : catalogue exact, références résolues, aucun code écrasé, contrainte de six cibles, qualification des pertes et intégrité UUID. valid/version et classifications de prestations conservés ; aucune suppression automatique.

## Limites et suite

Ce contrat ne choisit ni A ni B pour les supports. L'audit recommande d'instruire B sans l'appliquer. Les trois FK externes, les orphelins d'ouvrages hydrauliques, la classification du Grillage CABBALR, les scénarios fictifs et la validation des correspondances d'AH restent ouverts. La future implémentation doit adapter les fonctions, vues et triggers listés dans l'audit, puis valider une installation neuve et QGIS sous Windows. Les contrôles documentaires v0.5 ne prouvent aucun comportement applicatif ou résultat de migration.
