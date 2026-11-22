# GEMAPI-App — plugin QGIS 0.8.4

L’assistant IA ajoute un assistant conversationnel Mistral à la création standard.
Le plugin utilise le schéma canonique actuel sans le modifier.
La validation Windows du plugin intégré reste à effectuer ; les validations Linux
avec PyQGIS ne suffisent pas à déclarer cette version compatible Windows.

La description est générée dans la même réponse que les champs structurés : seuls
les compléments métier utiles sont reformulés, sans répétitions ni faits inventés.
Elle reste modifiable dans le formulaire et la phrase source reste dans l’historique.
Une correction limitée à un champ conserve les observations déjà reconnues.

## Assistant IA

La commande discrète **Nouvelle prestation**, au bas de la conversation, abandonne
le brouillon courant sans effacer les échanges. **Alt+N** déclenche la même commande
dans l’assistant et dans le formulaire ouvert. Une seule confirmation protège les
informations non enregistrées ; le formulaire utilise sa confirmation habituelle.
Aucune confirmation pour un brouillon vide ou après une sauvegarde réussie.
La dictée et les requêtes sont interrompues, leurs réponses tardives ignorées.
Le nouveau brouillon ne reprend ni les anciens champs ni les corrections en cours.
Après sauvegarde du formulaire issu de l’IA, un brouillon vide est automatiquement
prêt pour la prochaine ouverture. L’assistant, la session PostgreSQL et les caches
restent en mémoire ; la conversation antérieure ne sert pas de contexte à Mistral.


Le bouton **Assistant IA**, entre Rapport et Aide dans le panneau d’accueil,
ouvre une conversation persistante en mémoire. Décrire en français la prestation,
répondre aux questions, choisir explicitement les homonymes ou correspondances
approximatives, puis ouvrir le formulaire prérempli. Vérifier ses champs et cliquer
sur **Enregistrer la prestation**. **Retour à l'assistant IA** restitue l'historique.
La fermeture de la fenêtre conserve aussi la conversation jusqu'au déchargement
du plugin ou à la fermeture de QGIS.

Le prototype accepte un seul ouvrage hydraulique (`ah_ouvrage`), stockage hydraulique
(`ah_stockage`) ou zone terrestre (`sites_zones`). La géométrie propre reste `NULL`.
Type, prestataire, technicien, statut et dates de début et de fin sont obligatoires.
Les UUID sont résolus localement dans PostgreSQL. Avant chaque message, les types
actifs et leurs catégories sont relus sur la connexion courante. Les noms complets
actifs des prestataires et techniciens, les statuts et les noms des trois familles
patrimoniales sont transmis intégralement, avec la famille et le parent AH ou site.
Aucun UUID, secret ou géométrie n'est transmis. Un seul appel Mistral effectue
l'extraction, la comparaison des noms et la description.

La priorité est exacte, puis normalisée (casse, accents, ponctuation), puis
phonétique par Mistral. Une valeur exacte ou normalisée unique prime toujours
sur une suggestion phonétique. Une correspondance phonétique complète et unique
peut être acceptée après contrôle Python des libellés réels, de la famille et du
contexte envoyé ; les approximations et ambiguïtés nécessitent un choix humain.
Python ne contient aucun moteur phonétique. Un changement de référentiel suspend
l'acceptation automatique de l'ancienne proposition.
Les espaces dans un nom ou autour d'un numéro ne créent pas une ambiguïté lorsque
la référence reste unique. Pour un patrimoine, une citation reformattée avec son
parent peut être vérifiée à partir des deux noms présents ensemble dans la demande,
y compris les liaisons « du Site » et « dans le Parc ». Un parent absent, une
référence contradictoire ou des homonymes non départagés demandent toujours un choix.

Les références incertaines ou manquantes et les dates à compléter apparaissent
dans un même panneau, avant le récapitulatif. Les candidats proposés par Mistral
arrivent en premier, puis les autres références actives restent disponibles.
Choisir les valeurs, saisir la date de fin vide si elle manque, puis cliquer sur
**Valider les corrections ensemble**. Cette validation est locale et atomique,
sans appel API ni écriture PostgreSQL. La date de fin n'est jamais copiée du début.
Le formulaire standard reste l'unique lieu de sauvegarde humaine.

Les bornes d'une période explicite, l'achèvement et la fin prévisionnelle sont
distingués dans le contrat JSON strict. Mistral fournit une citation `preuve_dates` ;
Python vérifie sa présence dans la demande et les dates de ses bornes avec le
parseur calendaire. La fin prévue d'un chantier Planifié ou En cours n'est pas
effacée. Les dates incertaines, contradictoires, absentes ou insuffisamment étayées
demandent une confirmation. Le statut Terminé seul ne prouve toujours aucune fin.
Si le modèle omet une date mais cite correctement une période explicite, ses bornes
vérifiées peuvent compléter le champ ; une borne contradictoire n'est jamais écrasée.

Une citation de nom invérifiable bloque uniquement sa référence, même si le
nom canonique proposé existe. Une reformulation patrimoniale vérifiée par le nom
et son parent n'impose pas de confirmation supplémentaire. Les autres champs indépendants restent disponibles.
Le récapitulatif indique le champ et la cause sans répéter la citation potentiellement
sensible ; `draft.reference_diagnostics` conserve en mémoire le champ, la source
et la cause pour diagnostic local. Ces diagnostics ne sont ni journalisés ni envoyés
au TTS. Un choix humain validé ou une nouvelle citation vérifiable lève le blocage.
La géométrie propre reste `NULL` dans le périmètre de l'assistant : un indicateur
Mistral sans demande explicite vérifiable n'est pas appliqué. Une demande réelle
de dessin reste bloquante jusqu'à renonciation explicite.

L'action principale cochable de la barre QGIS affiche ou masque l’interface du plugin ;
les quatre autres boutons de l'accueil conservent leurs fonctionnalités.

Les sorties du modèle sont des propositions validées localement ; l'assistant
n'effectue aucune écriture SQL. Un échec réseau conserve le brouillon et demande
de réessayer le message avant de permettre son ouverture.

L'API officielle utilise `mistral-small-latest` avec un schéma JSON strict,
sans SDK supplémentaire. Dans ce checkout, la clé se lit depuis
`MISTRAL_API_KEY.txt` à la racine (clé brute ou ligne `MISTRAL_API_KEY=…`). Après installation du ZIP, utiliser
**Fichier de clé Mistral…** pour sélectionner ce fichier privé hors du dossier
installé. Seul son chemin est enregistré dans le profil QGIS, sous
`gemapi_app/mistral_key_path`. Autre possibilité : définir
`GEMAPI_APP_MISTRAL_KEY_PATH` avant de lancer QGIS. Le choix du profil prend priorité
sur cette variable. La clé ne doit jamais être ajoutée au dépôt ni distribuée.
La construction utilise un manifeste explicite qui l'exclut du ZIP.

### Dictée Voxtral

Cliquer sur **🎙 Dicter** pour activer ponctuellement le microphone par défaut du
système. L'indicateur rouge affiche sa durée. **■ Arrêter et transcrire** envoie
l'audio à l'API officielle Voxtral (`voxtral-mini-transcribe-3`, langue `fr`).
**Annuler dictée** arrête la capture sans envoyer d'audio. La limite est 60 secondes ;
à cette limite, la capture s'arrête et la transcription démarre automatiquement.
Pendant l'envoi, **Interrompre Voxtral** annule la requête ; il ne peut pas retirer
les octets déjà transmis au service.

Le texte reconnu apparaît dans l'historique et dans la saisie modifiable. Corriger
les noms, puis cliquer sur **Envoyer** pour le soumettre à Mistral Small. Aucune
transcription n'est soumise automatiquement à l'extraction. Les textes déjà saisis
sont préservés. Le clavier et la dictée partagent le même brouillon et le même
historique. Les propositions structurées et les vérifications locales restent visibles. Les
commentaires libres du modèle ne sont pas affichés, afin qu'une fausse annonce de
sauvegarde ne puisse pas apparaître dans la conversation.

La capture utilise QtMultimedia Qt5 dans un thread Qt distinct, en WAV PCM signé
16 bits, de préférence mono 16 kHz (sinon un format matériel compatible entre
8 et 48 kHz, mono ou stéréo). Tout l'audio reste en mémoire ; aucun fichier audio
temporaire ou permanent n'est créé. Les buffers sont libérés après utilisation,
erreur ou annulation. QtMultimedia manque ou le microphone est inaccessible :
un message explicite permet de continuer au clavier, sans installer de bibliothèque
Python supplémentaire. Windows doit autoriser l'accès au microphone aux applications
de bureau ; Ubuntu doit disposer d'une entrée audio utilisable par QGIS.

`context_bias` contient au maximum 24 termes de 80 caractères : noms du brouillon,
quelques candidats déjà proposés et vocabulaire métier. Aucun catalogue entier
n'est envoyé à Voxtral. Les biais améliorent l'orthographe sans garantir les noms :
la correction et le choix prudent des références restent nécessaires.

Les délais maximaux sont 30 secondes pour Mistral Small et 60 secondes pour Voxtral ;
les deux appels HTTP Qt sont asynchrones. Les consultations PostgreSQL réutilisent
la connexion QGIS et restent synchrones, comme celles du formulaire standard.
Cette version ne comprend ni écoute permanente, ni WebSocket,
ni enregistrement de prestation par commande vocale.

### Réponses vocales facultatives

**Réponses vocales** est désactivé par défaut. L'activer mémorise le choix dans le
profil QGIS (`gemapi_app/spoken_responses`) et lit automatiquement les prochains
résultats vérifiés localement. L'affichage texte est conservé. La phrase indique
un champ manquant, un choix à confirmer ou un brouillon prêt à vérifier dans le
formulaire ; elle n'annonce jamais une sauvegarde. Elle ne lit ni JSON ni noms ou
messages libres de Mistral. Les corrections locales validées peuvent aussi être lues.

**Arrêter la lecture** interrompt la synthèse ou la lecture en cours. **Relire**
réutilise l'audio de la dernière phrase en mémoire s'il est disponible, sinon seul
le TTS est rappelé ; aucun nouvel appel Mistral Small. Activer l'option ne lance pas
de lecture rétroactive : utiliser Relire pour une réponse déjà affichée.

Le TTS utilise l'API officielle `/v1/audio/speech`, le modèle
`voxtral-mini-tts-3-0`, la voix française Marie (`voice_592`) et le format WAV.
La même configuration de clé Mistral est utilisée. Seule la phrase courte est
envoyée : aucun référentiel, nom du brouillon, UUID, chemin de fichier ou géométrie.
Limites : 360 caractères, requête de 30 secondes maximum, réponse JSON de 3 Mio,
WAV PCM 16 bits de 2 Mio et 30 secondes maximum. Les échanges réseau Qt sont
asynchrones et la sortie QtMultimedia est gérée dans un thread distinct.
Le WAV Base64 est contrôlé puis lu depuis un tampon mémoire, sans fichier audio
ni dépendance Python supplémentaire. L'audio de la dernière réponse est conservé
uniquement pour Relire, puis libéré au changement de demande, à une correction,
au nouveau brouillon, à la désactivation ou au masquage de l'assistant.

Toute nouvelle demande ou dictée interrompt l'ancienne réponse. Les réponses
tardives sont ignorées. Une panne réseau, une clé indisponible, QtMultimedia absent
ou une sortie audio non utilisable laissent le texte, les corrections et le
brouillon disponibles. Le formulaire habituel conserve sa validation humaine.

Le [compte rendu DYSTOPIC-02](../audits/DYSTOPIC-02.md) décrit la recette et ses limites.

Les sections AH constituent un septième rattachement direct, identifié par
`ah_sections.id`, avec géométrie propre obligatoire de l'intervention. Une digue
ou section AH admissible remplace le cours d'eau sur sa portion longitudinale.
Les libellés suivent `Cours d'eau (Patrimoine)`. Les stockages et ouvrages AH
restent des rattachements distincts. Une concurrence de supports ou une portion
partiellement couverte nécessite de préciser ou subdiviser l'intervention,
sans priorité arbitraire. Le formulaire conserve l'organisation de 0.7.29.

Plugin pour QGIS 3.44 (Windows et Linux). Il permet de créer une prestation
avec exactement un rattachement patrimonial. La géométrie propre est obligatoire
pour les cours d'eau, digues, sections AH et sites terrestres, facultative pour les stockages et ouvrages AH,
et interdite pour les zones terrestres, dont la géométrie sert de référence.
Il génère aussi
un rapport détaillé PDF A4 portrait portant uniquement sur les prestations.

Les rapports du parent AH incluent également les prestations directement rattachées
à un cours d’eau dont la géométrie propre intersecte exactement une section AH
conforme sur ce même cours d’eau qualifié. Cette reconnaissance ne modifie aucun
rattachement. Les rapports des stockages et ouvrages restent limités à leurs
prestations directes. Les groupes AH peuvent se recouvrir ; le total général
reste dédupliqué par UUID, sans ventilation des quantités. Les rapports affichent
les noms métier sans identifiants techniques. Le rattachement et les AH concernés
sont intégrés à la fiche détaillée, sans page supplémentaire de reconnaissance.
Les retours à la ligne suivent la largeur imprimée ; si nécessaire, le bloc
s’allonge sur la même page sans changer les dimensions ni le cadrage de la carte.
L’espace des photographies s’adapte en conservant leurs proportions.

## Installation et dépendances

Depuis la racine du dépôt, exécuter `python3 plugin/tools/build_plugin.py`, puis installer
`plugin/dist/gemapi-app-0.8.4.zip` dans **Extensions > Installer/Gérer les
extensions > Installer depuis un ZIP**. Le plugin n'ajoute aucune dépendance
Python externe : PyQGIS, Qt et la bibliothèque standard suffisent. Le script
contrôle les fonctions requises et vérifie que chaque fichier du ZIP correspond
aux sources, sans transformation de namespace.

Après installation, redémarrer QGIS et consulter **Vue > Panneaux > Messages du
journal**, rubrique **GEMAPI-App** : le plugin affiche sa version et le chemin
du fichier `plugin.py` réellement chargé. Sous Windows, vérifier le profil actif
dans `%APPDATA%\QGIS\QGIS3\profiles\` ; un ZIP présent dans `plugin/dist/` ne
met pas à jour automatiquement l'extension déjà installée.

Le moteur PDF utilise la plateforme Qt native sous Windows et `offscreen` sous
Linux. Il choisit une police réellement visible par son processus et écrit dans
le journal QGIS la liste des polices, la substitution effective et les caractères
non couverts si l'export échoue.

Dans le formulaire, les cours d'eau de même nom sont proposés ensemble lorsque
leurs tronçons se suivent par une extrémité sans jonction ambiguë. Les homonymes
séparés restent distincts. Un groupe sélectionne ses
UUID individuels ; un groupe partiellement associé à une prestation est signalé
« partiel » et reste partiel tant que l'utilisateur ne le sélectionne pas
explicitement. Les filtres et les rapports continuent à lire les associations
par UUID.

### Identité du plugin

Le ZIP installe uniquement `gemapi_app`, nommé **GEMAPI-App**, avec son
icône habituelle dans la barre partagée **SIG-Milieux**. L’assistant fait partie
de cette installation unique. Le ZIP s’appelle `gemapi-app-0.8.4.zip` et contient
`gemapi_app/`. Désactiver puis retirer l’ancien plugin `sig_prestations` lors de
cette première installation sous le nouveau nom ; les anciennes archives gardent
leur nom et leur contenu. Le chemin de clé existant est repris automatiquement. Désactiver puis retirer l’ancienne extension
expérimentale après avoir conservé son fichier de clé local. Un chemin de clé
expérimental encore valide est repris automatiquement dans le profil standard ;
s’il pointe vers un worktree retiré, choisir à nouveau le fichier privé conservé.
L’ancienne variable d’environnement de chemin reste reconnue pour la transition ;
la variable standard et le choix explicite du profil sont prioritaires.

Ouvrir le projet Démo ou CABBALR avec une seule connexion métier. Les couches
`milieux.prestations_carte` ou `milieux.prestations_fiches` servent d'ancrage à
la connexion ; la couche physique `prestations` n'est pas nécessaire. Les
référentiels sont lus dans PostgreSQL. Les sections AH sont interrogées par
un fournisseur temporaire, sans nouvelle couche permanente. Les couches
patrimoniales du projet restent utilisées pour la cartographie, la localisation
et l'accrochage. Les connexions et l'authentification sont gérées par QGIS ; aucun
identifiant ou secret Supabase n'est inclus.

## Gestion, création et édition

Depuis **Gérer les prestations**, rechercher une prestation pour ouvrir sa fiche
en édition ou choisir **Nouvelle prestation**. Les deux parcours utilisent le
même formulaire. Le champ Type ouvre les catégories, puis les types de la
catégorie choisie ; la flèche de retour revient aux catégories. Seul l’UUID du
type est enregistré. Le menu suit la largeur du champ aux deux niveaux ; les
libellés longs sont tronqués et restent lisibles en infobulle.
Les catégories, leur ordre et les rattachements des types
sont lus dans PostgreSQL (droit SELECT requis sur
`milieux.prestations_categorie`). Une catégorie vide reste consultable.
Un type inactif déjà enregistré reste affiché à l’ouverture de sa fiche. L'édition charge les champs, la géométrie, les photographies
et les rattachements réellement enregistrés pour l'UUID choisi.

La recherche UX-06 porte sur l'intitulé, le type, le prestataire, le statut,
le technicien et la date affichée. Une prestation sans intitulé reste
recherchable par ces autres valeurs et apparaît sous son type et sa date.
Les huit listes multisélection des années, statuts, techniciens, prestataires,
communes, stockages AH, ouvrages AH, cours d'eau et zones terrestres sont visibles dès
l’ouverture. Elles se répartissent sur trois, deux ou une colonne selon la
largeur ; le séparateur vertical ajuste la place laissée aux résultats. Les
grandes listes possèdent leur propre recherche ; **Réinitialiser** efface aussi
la recherche rapide. Plusieurs valeurs d'un même critère sont combinées par
OU, les critères distincts par ET. Une commune est déterminée par intersection avec la géométrie
propre. La proximité seule ne
crée aucun rattachement. Le filtre Années utilise l'intervalle début-fin pour
les prestations terminées et l'année de début pour les autres. Un croisement
impossible affiche zéro résultat.
Les filtres utilisent le même moteur SQL que le registre PDF et n'écrivent
rien dans PostgreSQL.

Pendant la session QGIS, les référentiels et options de filtre sont réutilisés
entre les fenêtres ; les objets patrimoniaux sont chargés seulement à l'ouverture
de leur famille. **Actualiser les données** dans la gestion relit les listes et
efface les critères si la connexion ou le projet a changé. Cette action permet
aussi de voir les modifications faites ailleurs. Une écriture du plugin invalide
les données de prestations concernées ; la fiche et ses associations sont
toujours relues dans PostgreSQL avant édition. Le cache disparaît au déchargement
du plugin et peut être désactivé au démarrage avec `SIG_PRESTATIONS_CACHE=0`.
`SIG_PRESTATIONS_PERF=1` ajoute les événements de cache au journal `SIG-PERF`.

L’accueil est un panneau enfant du canevas, sans fenêtre ni décoration système,
en une colonne à 10 px du coin supérieur droit. Les boutons de 31 px conservent
leur police, avec 4 px d’espacement et 6 px de marges. Le panneau suit le canevas
et laisse les interactions cartographiques libres en dehors de sa surface.
La gestion, le formulaire commun de création et d’édition et le rapport visent 1 000 × 800 px. Ces tailles sont limitées à
l’espace disponible de l’écran. Les trois boutons d’action du formulaire restent
sur une ligne ; le formulaire défile
verticalement sans déplacer ses boutons inférieurs.

Dans **Nouvelle prestation**, choisir le type, le prestataire, le statut et
les dates obligatoires ; l'intitulé reste facultatif. Dessiner
une géométrie sur la carte et/ou ajouter au moins un objet patrimonial. Un
clic gauche place un sommet ; un clic droit termine une ligne ou un polygone ;
**Échap** annule le dessin. Le formulaire réapparaît avec sa saisie intacte.
Une géométrie déjà validée peut être redessinée ou retirée. Le dessin reste
en mémoire jusqu'à l'enregistrement et est transformé en EPSG:3950. Pendant
la numérisation, le canevas affiche en rouge les sommets et le tracé jusqu'au
curseur : point de 4 mm, lignes et contours de 0,66 mm, avec un léger
remplissage pour le polygone. Ces repères temporaires disparaissent à la fin
du dessin ou à son annulation. L'outil utilise les paramètres d'accrochage
déjà définis dans le projet QGIS : couches, cibles et tolérance. Un carré
jaune signale une cible valide ; les coordonnées accrochées servent à la fois
au tracé et à la géométrie enregistrée. Lorsque l'accrochage est désactivé,
le curseur reste libre. Si l'action **Tracé** de QGIS est activée, deux points
accrochés à des lignes ou contours connectés suivent le plus court chemin
calculé par QGIS. Les sommets intermédiaires apparaissent dans
l'aperçu puis dans la géométrie ; à une intersection, vérifier le chemin rouge
avant de cliquer et placer un point intermédiaire pour guider le parcours.
Un chemin absent est refusé avec un message. Désactiver **Tracé** permet de
reprendre les segments droits, y compris pendant une capture. Le plugin ne
change aucun réglage d'accrochage ni
l'état de l'action **Tracé**.

La prestation et ses associations sont écrites par une seule instruction SQL
PostgreSQL atomique. Les UUID, valeurs par défaut et champs techniques sont
gérés par la base. Après succès, seules les couches concernées sont actualisées ;
le formulaire est masqué, la carte est centrée sur la géométrie effective de
`milieux.prestations_carte` et l’accueil compact réapparaît. Le plugin conserve
sa connexion et ses caches. Un clic sur Créer prépare immédiatement une nouvelle saisie. Les objets patrimoniaux
restent gérés dans les formulaires natifs QGIS. Dans la section
**Rattachements patrimoniaux**, choisir une famille, rechercher et sélectionner
un seul objet et l'ajouter à la liste retenue ou le retirer avant
l'enregistrement. **Distance** est initialement décoché et inactif sans référence,
avec un rayon de 500 m. Un dessin valide l'active automatiquement autour de la
géométrie complète ; un clic avec le bouton cartographique l'active autour d'un
point temporaire, sans modifier la géométrie propre. Les deux utilisent la même
recherche PostGIS et le même arbitrage hydrographique. Le dernier dessin ou clic
définit la référence ; un changement de rayon ou d'unité recalcule la liste.
Décocher Distance suspend la restriction et les requêtes spatiales. Les propositions
restent filtrées par texte et famille et ne créent aucun rattachement automatique.
Tous les cours d'eau portent désormais un nom métier obligatoire, non blanc.
Le catalogue général et la recherche Distance utilisent ces noms directement ;
aucun libellé de remplacement issu d'un UUID n'est produit. Le regroupement des
tronçons nommés et l'arbitrage digues/sections AH restent appliqués. Un catalogue
invalide doit être corrigé dans PostgreSQL, sans génération de nom automatique.
La contrainte et les transitions préparées sont décrites dans
[la procédure coordonnée](../cabbalr/sql/README.md#déploiement-coordonné-hydro).
Les opérations spécialisées de digues et sections AH conservent leurs exigences
de qualification.
Le point temporaire reste actif après la sortie de l'outil carte et disparaît
à la réinitialisation ou au chargement d'une autre fiche. L'abandon d'une saisie non enregistrée demande confirmation.
Après l'enregistrement, la géométrie est affichée par la couche PostgreSQL
déjà chargée dans QGIS, selon sa symbologie propre. Le plugin rafraîchit les
couches concernées de la même connexion, même si leur nom affiché a été
personnalisé ; il ne crée pas de couche pour cet affichage.

Les couches cartographiques de la démonstration lisent `milieux.prestations_carte`
(vue de consultation) : pour une zone, sa géométrie est utilisée exclusivement.
La numérisation est désactivée lorsqu'une zone est retenue. Une géométrie propre
déjà dessinée est conservée et bloque l'enregistrement avec un message : elle
doit être retirée explicitement. Les rapports détaillés et synthétiques affichent
les références ponctuelles, linéaires et surfaciques sans recopier leur géométrie.

En édition, les champs modifiés et les différences de rattachements sont
enregistrés atomiquement. Les autres champs, la géométrie inchangée et les
relations conservées ne sont pas réécrits. Une fiche devenue obsolète depuis
son ouverture est refusée sans écrasement ; **Recharger la fiche** permet de
relire l'état de la base après confirmation de l'abandon de la saisie locale.
**Annuler et revenir à la gestion** abandonne seulement les changements locaux.
Après enregistrement, le retour à la carte conserve les filtres de gestion.
Gérer les prestations permet de retrouver la liste ; sa mise à jour reste ciblée. L'édition requiert les droits SELECT et
UPDATE sur `milieux.prestations`, ainsi que les droits INSERT/DELETE nécessaires
sur les tables de rattachement modifiées. Aucune connexion Supabase distincte
n'est créée : le plugin utilise la connexion PostgreSQL chargée dans QGIS.

Le formulaire relit les associations SQL de chaque prestation à son ouverture.
Le jeu de démonstration contient 100 prestations, chacune liée à au moins un
objet d'une seule des cinq catégories patrimoniales.

## Rapports

Depuis l'accueil, **Créer un rapport** ouvre des listes à cases à cocher,
recherchables. Aucune sélection ne restreint le critère ; plusieurs valeurs
d'un critère sont combinées par OU, les critères distincts par ET. Les filtres
patrimoniaux retiennent les prestations directement liées aux objets choisis.
Chaque prestation est comptée une seule fois. Le nombre de prestations correspondant
aux filtres est affiché avant l'export ; un résultat vide ne peut pas être
exporté. **Générer le PDF** demande le chemin de sortie, puis affiche l'étape
en cours et le nombre de prestations mises en page. À la fin, **Rapport généré**
propose **Ouvrir le PDF** ou **Fermer**. Le rendu est effectué dans un processus
QGIS séparé pour laisser l'interface réactive pendant les cartes et l'écriture.
Le rapport détaillé utilise la mise en page portrait V04 : une fiche et une carte
Plan IGN Épuré par prestation, puis jusqu'à deux photographies réelles si
l'option est cochée. Sans photo disponible, il le signale explicitement.
L'export utilise 150 dpi, conserve le texte vectoriel et ne rasterise pas les
pages entières. Les descriptions ou légendes trop longues passent en page de suite.
Le choix **Synthétique A4 paysage** produit un tableau multiprestations sans
carte ni photo. Il reprend les filtres et propose jusqu'à trois niveaux ordonnés
parmi année de début, commune, type, technicien, prestataire et statut. Les
effectifs et totaux des groupes sont dédupliqués dans chaque groupe ; un objet
présent dans plusieurs communes peut figurer dans plusieurs groupes. Le total
général reste dédupliqué par UUID.
Le fichier choisi n'est remplacé qu'après réussite complète ; en cas d'échec,
le fichier partiel est supprimé. L'annulation en cours d'export n'est pas
proposée, car le rendu QGIS ne garantit pas une interruption propre.
Le processus PDF utilise automatiquement le Python de l'installation QGIS
active. Sous Windows, il reprend les chemins Python, Qt, GDAL et PROJ du
préfixe OSGeo4W ; sous Ubuntu, il utilise le Python PyQGIS courant. Aucun
réglage Python n'est demandé à l'utilisateur. `SIG_PRESTATIONS_PYTHON` reste
disponible pour un diagnostic ponctuel, sans être requis pour l'export.

Le statut est choisi dans le référentiel `milieux.statuts_prestations` :
`Planifié`, `En cours`, `Terminé`, `Annulé`. Seul `Terminé` signifie
« complétée » ; les trois autres statuts sont « non complétées ».
`date_fin` ne détermine jamais l'achèvement. Pour une prestation non complétée,
le filtre annuel utilise uniquement `date_debut`. Pour une prestation complétée,
il retient une année chevauchant l'intervalle début-fin, sans répartir les
travaux ou les mesures entre années.
Le regroupement annuel du registre utilise exclusivement l'année de début,
y compris lorsque la prestation terminée couvre plusieurs années : il ne
répartit ni travaux ni mesures entre années. Les dates réelles restent visibles.

La création demande une géométrie propre EPSG:3950 valide, un type, un prestataire, un statut, une date de début et
une date de fin (éventuellement prévisionnelle). L'intitulé, la quantité,
l'unité et la description sont facultatifs. Le champ Nature a été retiré du
formulaire. Les photographies restent facultatives ; au moins un rattachement
parmi les cinq catégories est obligatoire. L'édition des prestations enregistrées
réutilise ce même formulaire et ces mêmes validations.

La géométrie est saisie en premier. Pour créer une géométrie multipartie,
dessiner la première partie, choisir **Ajouter une partie**, puis **Terminer la
géométrie** après la dernière partie. Le clic droit termine la partie en cours
pour une ligne ou un polygone ; Échap annule cette partie. **Retirer la dernière
partie** permet de corriger une géométrie multipartie. Les associations
patrimoniales se choisissent ensuite, avant les informations métier et les
photographies. Le bouton d'enregistrement reste désactivé tant que la
géométrie est absente, invalide ou en construction, ou si aucun objet patrimonial
n'a été retenu.

Le plugin 0.7.14 s'utilise avec le schéma canonique actuel de `model/schema.sql`.

Les communes sont déduites par intersection de la géométrie propre ; elles ne sont pas une
clé étrangère de la prestation. Le technicien responsable est la clé obligatoire
`prestations.technicien_id` ; `modifie_par` est le compte PostgreSQL de la dernière
écriture, renseigné automatiquement. Les totaux portent seulement
sur les longueurs et surfaces des géométries propres EPSG:3950, séparément :
ce sont des sommes par prestation, sans déduction des recouvrements éventuels,
et non une emprise géographique unique.
Les mesures des objets liés restent des références patrimoniales individuelles,
jamais additionnées à l'emprise propre. La quantité
métier reste distincte. Les rattachements multiples AMB-01 et les communes
multiples sont signalés sans répartition arbitraire. Les fiches
individuelles sont hors de cette version. L'export n'écrit rien en base.

Le registre destiné aux décideurs affiche les dates, types, statuts,
techniciens, prestataires, communes, patrimoine et quantités ou mesures.
Le patrimoine présente les **cibles directes**. Les intitulés, codes internes et descriptions
personnalisées ne sont pas affichés dans le PDF ; ils restent disponibles
dans PostgreSQL et dans le formulaire QGIS. Trois sélecteurs facultatifs
permettent de regrouper le registre, dans l'ordre choisi, par année de début,
commune, type, technicien, prestataire ou statut. Un critère ne peut être
choisi deux fois. Les bandeaux des niveaux 1 et 2 et le titre du niveau 3
gardent la largeur entière de la page. La colonne Type, Technicien,
Prestataire ou Statut est masquée lorsque son critère est déjà déterminé par
un groupe ; les dates et les communes restent visibles.

Chaque groupe indique son effectif distinct et ses totaux de longueurs et
surfaces propres. Une prestation touchant plusieurs communes apparaît dans
plusieurs sections communales. Ces sous-totaux peuvent donc se recouvrir ;
le total général est calculé une seule fois par UUID et ne provient jamais
de leur addition. Aucune quantité n'est ventilée entre communes ou années.

## Vérification

Pour profiler une session, définir `SIG_PRESTATIONS_PERF=1` **avant** de démarrer
QGIS, puis lire la rubrique `SIG-PERF` du journal des messages. Redémarrer QGIS
sans cette variable pour désactiver les traces. Le protocole et les limites des
mesures sont à réaliser dans la session QGIS concernée, sur Linux et Windows
pour toute conclusion de performance multiplateforme.

Toutes les commandes ci-dessous sont lancées depuis la racine du dépôt.

`python3 plugin/tools/build_plugin.py` vérifie syntaxe, métadonnées, UI et produit le
ZIP dans `plugin/dist/`.
`QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover -s plugin/tests -p 'test_assistant*.py'`
couvre le brouillon et les échanges simulés sans API ni serveur PostgreSQL.
Le banc `test_assistant_linguistics.py` couvre séparément 34 variantes d'extraction
simulée et de résolution locale. Un essai API sans base ni écriture est disponible :
`/usr/bin/python3 plugin/tests/test_assistant_linguistics.py --live --limit 12`.
Il utilise le catalogue de test, sans interroger CABBALR.
La même commande avec `-p 'test_voice.py'` vérifie la capture simulée, le multipart
Voxtral, les erreurs, les échanges mixtes et l'annulation sans envoi. Elle couvre
aussi les requêtes TTS, le WAV Base64, la préférence, la relecture en mémoire,
les interruptions concurrentes et le nettoyage des threads et tampons audio.
`/usr/bin/python3 plugin/tests/test_voice_stability.py` lance quatre processus
PyQGIS isolés avec limites de temps : sessions répétées, destruction du propriétaire,
remplacement rapide des lectures et callbacks après fermeture. Le réseau et l'audio
sont simulés ; aucun appel payant ni accès aux bases métier. Un seul worker de lecture
reste actif par assistant, même pendant une annulation. Ces tests détectent des
défauts de cycle de vie sans prouver l'absence de tout plantage natif ; la recette
Windows reste nécessaire.
Avec des périphériques disponibles, `python3 plugin/tests/test_voice_stability.py --native`
teste explicitement 32 lectures locales interrompues, une fin normale et quatre
captures annulées, dans un processus isolé. Aucun audio n'est transmis. La destruction
des objets audio natifs précède la libération des tampons et l'arrêt de leur thread,
pour éviter une réentrance du backend audio pendant la destruction de son propriétaire.
`test_assistant_validation.py` conserve les huit phrases d'AI-VALIDATION-01 à
l'identique, simule les JSON et lit les référentiels Démo actuels en lecture seule.
La suite Qt vérifie aussi leur affichage, la conservation des dates et les choix
humains nécessaires. Ces résultats déterministes valident Python ; ils ne garantissent
pas que chaque réponse future du modèle linguistique sera correcte.
`QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_assistant_integration.py`
valide le ZIP avec une base PostGIS Docker neuve, les trois rattachements et
l'enregistrement standard déclenché explicitement par le test. La base est supprimée
à la fin. Ajouter `--live-mistral` uniquement pour un essai réel avec la clé locale
et les données fictives du scénario. Aucun de ces tests ne se connecte à Supabase.

`python3 -m unittest discover -s plugin/tests -p 'test_record.py'` et la même
commande avec `test_report_data.py` couvrent les validations et requêtes
pures ; `python3 plugin/tests/smoke_import.py` vérifie les
imports simulés. Avec Docker,
`python3 plugin/tests/test_postgres_integration.py` teste la création atomique
et les quatre statuts sur PostGIS éphémère. Avec le Python de QGIS 3.44
et `QT_QPA_PLATFORM=offscreen`, `python3 plugin/tests/test_qgis_runtime.py` vérifie
les parcours UI. `python3 plugin/tests/test_digitize_preview.py` vérifie le
rendu temporaire rouge sur un canevas QGIS, pour Point, Ligne et Polygone,
ainsi que le suivi du curseur et l'effacement des repères.
`python3 plugin/tests/test_digitize_snapping.py` vérifie avec QGIS hors écran
l'accrochage aux sommets et segments de couches de test, le choix des couches,
le mode désactivé, la transformation EPSG:3950 et la conservation des réglages.
Avec Docker et
QGIS hors écran, `python3 plugin/tests/test_saved_geometry_visibility.py`
vérifie séparément l'enregistrement d'un point et le rafraîchissement d'une
couche PostgreSQL existante dont le nom a été personnalisé, sans changer son
symbole. `python3 plugin/tests/test_report_worker.py` et
`python3 plugin/tests/test_report_dialog_export.py` couvrent le processus
d'export, l'interpréteur réellement lancé, la progression, l'arrêt et le
nettoyage après échec. `test_pdf_runtime.py` couvre la sélection du Python
QGIS sur Windows et Ubuntu sans recherche dans le `PATH`.
`python3 plugin/tests/test_management_integration.py` vérifie 105 cas métier de
recherche UX-06 et les temps de réponse avec 155 puis 605 prestations dans
PostGIS éphémère.
`QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_edit_integration.py`
vérifie l'édition réelle sur PostGIS éphémère : champs, dates, photos,
géométries, différences de rattachements, droits, rollback, conflits et
navigation Qt entre deux UUID. Il ne contacte pas la base Supabase.
Les suites d'intégration des rapports utilisent la Démo dans PostGIS jetable
et un rôle limité à `SELECT`. La suite SQL vérifie les regroupements, les
rattachements AH directs et indirects, les mesures et les filtres Qt. Elle
ajoute quatre prestations d'essai pour les tests de sélection. La suite PDF
rapide utilise la Démo seule pour vérifier une synthèse AH, une synthèse de
douze groupes et un rapport détaillé avec cartes et photos fictives.

```bash
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_report_integration.py --suite sql
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_report_integration.py --suite pdf
```

Lancer explicitement la recette longue pour les huit synthèses de 100
prestations et le rapport détaillé des six rattachements. Sous Linux, le
budget global de quatre minutes laisse une marge par rapport aux durées
mesurées. Le journal indique le début, le résultat et la durée de chaque
export. Les suites PDF nécessitent `pdfinfo` et `pdftotext` (Poppler) et
utilisent un fond mémoire et des fichiers temporaires sous `audits/`.

```bash
QT_QPA_PLATFORM=offscreen timeout --signal=INT --kill-after=15s 240s \
  /usr/bin/python3 plugin/tests/test_report_integration.py --suite long
```

`QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_many_maps.py`
vérifie 30 prestations avec cartes sans fond et photographies, la pagination
et le projet QGIS intact. Son option `SIG_PRESTATIONS_TEST_IGN=1` teste aussi
le fond IGN réel lorsque le service est disponible.

`python3 -m unittest discover -s plugin/tests -p 'test_package.py'` vérifie
l'intégrité, le contenu et la reproductibilité binaire du ZIP, puis charge
`classFactory` depuis le package extrait dans un profil de test, avec les
interfaces QGIS simulées puis les API QGIS disponibles.
`python3 plugin/tests/test_demo_import.py` exécute le véritable script
`demo/data/importer_base_neuve.sh` dans deux bases éphémères : PostGIS dans
`public`, puis dans `extensions`. Il vérifie le peuplement depuis
`model/schema.sql`. Les tests Docker utilisent PostgreSQL 16/PostGIS 3.4 ;
leurs conteneurs sont supprimés en fin d'exécution.

Les tests Qt/PDF et `test_report_maps.py` utilisent le Python de QGIS 3.44 avec
`QT_QPA_PLATFORM=offscreen`. Installer `pdftotext` (Poppler) pour exécuter aussi
les assertions sur le texte, les accents, les unités et la pagination du PDF.
Ces scripts d'intégration se lancent séparément des tests unitaires.

Validation 0.7.22 du 9 novembre 2026 sous Linux : Python 3.12.3,
QGIS 3.44.15, PostgreSQL 16/PostGIS 3.4 et `pdftotext` disponibles.

| Contrôle automatisé | Résultat |
| --- | --- |
| Suite complète (`plugin/tests/test_*.py` et `smoke_import.py`) | 52 scripts réussis, dont 110 cas `unittest` ; aucun module exclu |
| Formulaire courant (`locationGroup`) et parcours Qt | Réussi ; disposition actuelle, validation, création, consultation et édition |
| LOC-03 : Distance, références successives, rayon et géométrie conservée | 8 tests réussis ; 48 comparaisons point/ligne/polygone, également exécutées sur PostGIS local |
| GEOM-ZONES-01 : contraintes, vues, cartes et règles de rattachement | 33 validations du modèle réussies ; zones Point/LineString/Polygon, quantité et unité conservées |
| Construction, métadonnées, UI, ZIP reproductible et import extrait | Réussi |
| Installation Desktop dans un profil isolé, chargement et déchargement | Réussi avec QGIS 3.44.15 Linux ; aucune extension expérimentale |
| Création PostGIS et annulations atomiques | Réussi |
| Reconnaissance indirecte AH et rapports détaillés/synthétiques | Intersection exacte, références conformes, rapports enfants directs et global dédupliqué |
| Intégration PDF complète sur 104 prestations | Réussi : 77 pages avec photos, 14 compactes, 10 cartographiques, hiérarchies de 30 et 105 pages |
| Cartes avec photos, pagination et projet intact | Réussi, 30 prestations |
| Import complet de la démonstration, PostGIS dans `public` et `extensions` | Réussi, effectifs vérifiés dans les deux bases |
| Démonstration importée | 100 prestations, 100 rattachements ; 12 géométries propres NULL sur zone, 100 géométries cartographiques |
| Sections AH et qualification fictive documentée | 1 section conforme, 1 rivière qualifiée par convention DEMO-AH-01, 57 directions NULL |
| GPKG, SQL neuf et Supabase | 16 couches GPKG contrôlées ; 16 tables métier SQL/Supabase concordantes |

Les tests utilisent uniquement des données fictives et des bases jetables.
La variante facultative de 30 cartes avec `SIG_PRESTATIONS_TEST_IGN=1` n'a pas
été exécutée ; le scénario sans fond a réussi.
Supabase est comparé exclusivement en lecture seule ; aucune migration ou
synchronisation n'est réexécutée. Les fichiers CABBALR ne sont pas modifiés et
les modifications intentionnelles du projet QGIS sont conservées.

La validation Windows n'a pas été exécutée : aucun environnement Windows/QGIS
n'est disponible ici. Les vérifications interactives métier restent à faire,
avec un projet connecté : remplacement de l'ancienne extension, icône unique,
accueil, consultation et sélection patrimoniale, dessin Point/Ligne/Polygone
avec prévisualisation et accrochage au curseur, enregistrement et visibilité dans les couches
du projet, édition de deux fiches successives et rechargement après conflit,
effectif filtré sur grand jeu de données et choix du fichier
PDF. Les tests automatisés sans affichage ne remplacent pas cette recette.

## Ressources et sorties

`gemapi_app/assets/logo_cabbalr.webp` est le fichier institutionnel original,
conservé sans retouche. La constante `INSTITUTIONAL_LOGO` dans `report_pdf.py`
le référence. Le rapport 0.5.0 le place en haut à droite. L’icône de la barre
d’outils reste inchangée.

Les tests écrivent sous `../audits/pdf/`. Les archives `dist/`, les sorties
temporaires et les caches Python sont ignorés par Git. Le réglage PDF standard
à 100 dpi conserve le texte sélectionnable tout en réduisant la taille des
exports orthophoto observés lors des essais Linux ; la qualité doit être
vérifiée sous Windows avant diffusion générale. En utilisation QGIS,
l'utilisateur conserve le choix de la destination de son export PDF.

## Photographies (UX 0.5.0, phase A)

Le formulaire de création accepte deux références facultatives vers des images et
leurs commentaires. Placer les images dans `photos/` à côté du projet QGIS actif :
`monprojet/monprojet.qgz` et `monprojet/photos/`. La valeur enregistrée est
`photos/nom.jpg`, ou `photos/sous_dossier/nom.jpg`, avec des séparateurs `/`.
Le projet peut être déplacé avec son dossier `photos/` ; le formulaire et le
processus PDF résolvent les références depuis le dossier du QGZ, sans utiliser
le répertoire courant ni le dossier d'installation du plugin.

Les chemins absolus existants restent utilisables sur la machine où le fichier
existe. Un chemin absolu absent n'est pas remplacé par une photo de même nom.
Pour les anciennes références relatives sans préfixe `photos/`, le plugin conserve
la résolution depuis `SIG_PRESTATIONS_PHOTOS_DIR` lorsqu'il est configuré, ou
depuis le dossier `photos/` du projet sinon. Les nouvelles sélections dans le
dossier du projet sont toujours enregistrées au format `photos/...` ; une image
choisie ailleurs garde son chemin absolu. Le plugin ne copie aucun fichier.

## Carte du rapport détaillé

La carte obligatoire de 190 × 73 mm utilise le style officiel
[`epure.json`](https://data.geopf.fr/annexes/ressources/vectorTiles/styles/PLAN.IGN/epure.json)
et ses tuiles vectorielles.
Ces services et le style Épuré sont décrits dans la
[documentation Plan IGN](https://cartes.gouv.fr/aide/fr/partenaires/ign/representations-cartographiques-souveraines/plan-ign/plan-ign-web/)
et le [catalogue IGN](https://cartes.gouv.fr/).

Le cadrage d'une prestation sur site terrestre englobe le site et toutes les
composantes de la prestation, y compris celles situées hors du site. Les
prestations sur zone utilisent la géométrie de la zone pour la carte. Les
longueurs, surfaces et nombres de points cartographiés portent sur la géométrie
propre, sans découpe aux limites du patrimoine. La quantité déclarée reste distincte. L'emprise est calculée à partir
d'EPSG:3950, agrandie de 75 m, transformée en EPSG:2154 puis ajustée au rapport
largeur/hauteur sans rognage. Les géométries propres sont magenta, les
références patrimoniales orange. La source IGN figure sous chaque encart.

L'export crée sa propre mise en page et ses propres couches mémoire ; il ne
change ni les couches ni le fond du projet QGIS ouvert. Le fond nécessite un
accès aux services IGN pendant l'export. Si le service ne répond pas au début
de l'export, la carte est dessinée sans fond et porte un avertissement. Une
interruption après cette vérification peut laisser un fond incomplet ; vérifier
le PDF avant diffusion. Les cartes hors couverture IGN peuvent aussi être
blanches. Les photos absentes sont omises sans bloquer l'export.

Le stress test `QT_QPA_PLATFORM=offscreen python3 plugin/tests/test_many_maps.py`
exporte 30 prestations fictives avec photographies, Point, Ligne, Polygone,
axe nord-sud allongé et cas sans géométrie. Il simule l’indisponibilité du
fond et vérifie les légendes, la pagination et l’absence de modification du
projet. Avec `SIG_PRESTATIONS_TEST_IGN=1`, il teste aussi le processus d'export
avec le fond IGN réel ; sa disponibilité dépend du réseau.

Les suites d'intégration SQL et PDF sont décrites dans la section
[Vérification](#vérification). Les contrôles interactifs sous QGIS Windows
et Ubuntu restent nécessaires avant tout usage opérationnel.

### Validation automatisée UX 0.5.0

- 14 tests unitaires : créations, filtres, chemins photo, ZIP reproductible,
  cadrage, priorité de géométrie et indisponibilité des fonds.
- QGIS 3.44.15 sans affichage : formulaires, `classFactory`, numérisation,
  logo et sélection des fonds.
- PostgreSQL 16/PostGIS 3.4 temporaires : création atomique, colonnes photo,
  migration idempotente, filtres et associations cartographiques ; reconstruction
  complète de la démonstration avec PostGIS dans `public` et `extensions`.
- PDF de démonstration 0.5.0 : 3 prestations fictives et 5 pages avec logo,
  deux photos, une photo, Point, Ligne et Polygone sur Plan Épuré.
  Orthophotographies et référence patrimoniale sans géométrie propre ont été
  vérifiées dans des PDF de contrôle distincts. Les pages ont été rendues en
  PNG et inspectées.
- Stress test : 30 prestations, 30 pages avec fond simulé indisponible ;
  toutes les légendes et les numéros de pages sont présents, projet intact.

Ces contrôles automatisés ne remplacent pas la recette interactive Windows et
Ubuntu avec le projet de travail et les chemins de photos de l'organisation.

## Sections hydrographiques AH

Dans le projet courant, ouvrir la fiche native d'un AH depuis sa table
attributaire, dont la colonne **Actions** donne accès aux deux commandes. Le bloc **Sections hydrographiques** contient les références
acceptées et les actions **Créer une section manuelle…** et **Rechercher des sections proposées…**. Les fractions,
la longueur figée, l'état et la dernière validation se consultent dans l'éditeur
relationnel natif ; son bouton de zoom localise les sections sur l'axe.

La recherche ouvre une couche mémoire et une table attributaire QGIS natives.
Chaque ligne propose les actions **Localiser**, **Accepter…** et **Refuser**.
L'acceptation ouvre une confirmation distincte ; fermer ou annuler n'écrit rien.
Refuser retire uniquement la proposition temporaire. Les références enregistrées
sont consultables dans **Sections hydrographiques AH** ; leurs actions permettent
de modifier/revalider les fractions ou de supprimer explicitement le référencement.
Le cours d'eau et les fractions sont choisis manuellement, puis prévisualisés
avant confirmation explicite. Les propositions d'intersection sont facultatives.
Un AH sans stockage est autorisé ; la section peut dépasser son emprise.
Seuls les changements hydrographiques rendent la référence périmée.

**Enregistrer la référence sur le serveur** est une opération atomique autonome.
Elle est définitive après confirmation, indépendamment de la fermeture de la
fiche AH : elle ne fait pas partie du buffer d'édition du parent. Pour éviter
leur mélange, les actions d'écriture refusent de s'exécuter pendant toute session
d'édition PostgreSQL de la même connexion. Elles ne valident ni n'annulent les
modifications d'autres couches. Un refus SQL ne laisse aucune écriture partielle.
La signature et la révision protègent contre une proposition ou une fiche périmée.

Les contrôles serveur restent l'autorité. Les actions n'accordent aucun droit,
ne modifient aucune direction, et ne fournissent jamais de géométrie à INSERT
ou UPDATE. Les propositions sont cyan discontinues ; les références sont vertes,
rouges discontinues ou orange pointillées selon leur conformité, sans décalage.
Les propositions temporaires disparaissent au déchargement du plugin.

La démonstration permanente comporte une qualification conventionnelle fictive
du Ruisseau du Pré Neuf et une section acceptée sur RC du Pré des Saules
(DEMO-AH-01). Les 57 autres directions restent NULL. Il ne s'agit pas d'une
observation de terrain ; la convention et les exemples de rapports sont décrits
dans `demo/README.md`. Les tests complets utilisent PostGIS jetable.
La validation Windows de 0.7.26 reste à effectuer ; les essais réalisés ici sont Linux.

### Tests de reconnaissance indirecte AH

`QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_report_ah_integration.py`
crée son propre conteneur PostGIS 16/3.4, installe le schéma canonique et utilise
17 prestations entièrement inventées. Il contrôle les six types géométriques
autorisés, les contacts ponctuels, les identités des cours d’eau, les preuves par
section, les filtres, les références périmées, les droits SELECT et les totaux.
Ajouter `REPORT_AH_PDFS=1` produit les comparaisons détaillées et synthétiques dans
`audits/report_ah_02/`, avec fond local vide pour éviter tout service externe.
La comparaison « avant » sélectionne seulement les prestations directes du même
jeu courant ; elle ne reconstruit aucun ancien schéma.

Les contrôles REPORT-AH-02 vérifient aussi l’absence d’identifiants dans les PDF,
une fiche par prestation et le retour à la ligne pour deux AH aux noms longs.
Les noms homonymes restent des groupes distincts grâce à leurs clés internes.

## Gestion des digues

Le menu **GEMAPI-App → Créer une digue…** ouvre la saisie du nom,
de l'identifiant externe, du commentaire, du cours d'eau, de la rive et des
fractions. Choisir un support qualifié, **Prévisualiser sur la carte**, puis
**Confirmer et enregistrer**. Le serveur crée la digue et son repère dans la
même transaction ; une digue sans repère valide est refusée.

La colonne **Actions** et la fiche de `digues_carte` proposent **Modifier le
repère…**, **Revalider le repère…** et **Supprimer la digue…**. Modifier permet
également de corriger les attributs métier de la digue. Revalider conserve le
support, la rive et les fractions affichés et demande l'examen du nouveau tracé.
Chaque validation conserve les UUID et augmente la révision exactement de 1.
Un cours d'eau modifié doit avoir été explicitement qualifié avant revalidation.
La géométrie demeure calculée et figée côté serveur.

Aucun crayon d'édition n'est nécessaire. Les actions refusent une session
PostgreSQL en cours sur la même connexion ; annuler ne modifie rien. Le compte
Patrimoine est requis pour écrire ; Lecture et Prestations peuvent consulter et
prévisualiser. La suppression demande confirmation et refuse toute prestation
rattachée, sans la supprimer. Les fiches ou prévisualisations périmées sont
refusées : recharger et réexaminer le tracé avant de confirmer.

Ces opérations nécessitent le schéma QGIS-EDIT-02. Le plugin signale clairement
une base non mise à jour ; il n'exécute aucune migration automatique. Les bases
Supabase existantes doivent faire l'objet d'une transition autorisée séparément.

Recette locale sur PostGIS jetable et les deux projets :
`QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_digues_edit.py`.
La recette Windows reste requise avant diffusion générale.
