# DYSTOPIC-01 — Assistant de création et dictée Voxtral

Recette initiale. La livraison courante et les évolutions linguistiques/interface
sont décrites dans [DYSTOPIC-02](DYSTOPIC-02.md).

Version expérimentale : **Prestations Dystopic ☣ 0.8.0**, QGIS 3.44.
Développement réalisé uniquement dans le worktree `sig-prestations-dystopic`, sur
`dystopic`. Aucun changement de schéma, aucune migration et aucune écriture sur
Supabase. Les données de `cabbalr/` et les projets QGZ n'ont pas été modifiés.

## Architecture retenue

Trois modules complètent le plugin existant, sans SDK Mistral ni dépendance Python
supplémentaire :

- `assistant.py` : requête structurée Mistral Small, lecture de la clé, brouillon
  en mémoire, validation stricte des propositions et résolution locale des noms.
- `assistant_dialog.py` : conversation PyQt persistante, saisie, dictée, relecture,
  questions, récapitulatif et choix des candidats. Les appels HTTP sont asynchrones,
  avec un gestionnaire réseau Qt privé pour ne pas faire entrer les en-têtes
  d'authentification dans le journal réseau global de QGIS.
- `voice.py` : capture QtMultimedia dans un thread Qt, WAV en mémoire, préparation
  multipart Voxtral, vocabulaire contextuel borné et traitement des erreurs.

Mistral Small utilise `mistral-small-latest`, l'API officielle
`/v1/chat/completions` et `response_format=json_schema`. Le modèle propose un
patch de noms et de champs, jamais des UUID ou du SQL. Les champs inconnus, les
UUID produits par le modèle et les structures invalides sont rejetés. Un patch
invalide ne modifie pas le brouillon. Les dates françaises avec année sont
normalisées ; « le même jour » reprend uniquement une date de début déjà connue.
Aucune date de fin n'est déduite d'un statut Terminé.

La résolution utilise la connexion PostgreSQL de `SessionData` et exclusivement
des requêtes SELECT à identifiants fixes. Les noms sont normalisés sans casse ni
accents. Une correspondance exacte unique peut être retenue automatiquement ;
les homonymes, sous-chaînes et correspondances approximatives exigent un choix
humain. Les types sont lus avec leur catégorie, les références inactives sont
exclues. Le parent AH/site et l'UUID distinguent les candidats homonymes.

Le modèle ne reçoit que le nouveau message et les noms/champs du brouillon.
Les UUID, géométries et catalogues restent locaux. Les consultations PostgreSQL
restent synchrones, conformément au fonctionnement actuel du formulaire : ce
prototype est dimensionné pour les catalogues de démonstration.

`CreationDialog.load_draft(values, associations)` constitue l'interface interne
de préremplissage. Elle exige un formulaire neuf, relit les références actives et
l'objet, vérifie les limites de dates du formulaire et applique `record.validate`.
Seul un objet `ah_ouvrage`, `ah_stockage` ou `sites_zones` est accepté. La capture
de géométrie est désactivée pour le brouillon Dystopic ; un garde supplémentaire
avant sauvegarde exige ce périmètre et une géométrie propre NULL.

**`record.py` et ses contraintes sont inchangés.** Ouvrir un brouillon n'appelle
ni `_save`, ni `build_insert`, ni une écriture SQL. Le bouton standard Enregistrer
conserve son traitement et les droits PostgreSQL habituels. Le contrôle INSERT
est revérifié à l'ouverture du formulaire depuis l'assistant.

## Parcours utilisateur

1. Ouvrir l'accueil, puis **☣ Assistant IA — Dystopic** sous les quatre boutons.
2. Saisir la demande en français ou utiliser **🎙 Dicter**.
3. Pour une dictée, arrêter pour transcrire avec Voxtral, ou annuler sans envoyer.
4. Lire la transcription, la corriger dans la saisie puis cliquer **Envoyer**.
   Voxtral ne déclenche jamais automatiquement Mistral Small.
5. Lire la proposition Mistral et la vérification locale : champs reconnus,
   informations manquantes, références introuvables et candidats à choisir.
6. Compléter les dates ou corriger un champ au clavier ou par une nouvelle dictée.
7. Ouvrir le formulaire lorsque le brouillon est complet, vérifier, modifier et
   enregistrer explicitement. Le formulaire peut aussi être fermé sans sauvegarde.
8. **Retour à l'assistant IA** restitue le même historique et le même brouillon.

Les interventions utilisateur et assistant ont des couleurs et auteurs distincts.
Le défilement suit les nouveaux messages ; les échanges précédents restent
accessibles. Fermer la fenêtre conserve son état jusqu'au déchargement du plugin
ou à la fermeture de QGIS. Une future restitution sonore pourrait lire les
réponses existantes sans remplacer cet historique textuel.

## Dictée Voxtral

- Endpoint : `POST https://api.mistral.ai/v1/audio/transcriptions`.
- Modèle : `voxtral-mini-transcribe-3` ; langue : `fr`.
- Authentification : même fichier de clé que Mistral Small.
- QtMultimedia Qt5 : PCM signé 16 bits little endian, préférence mono 16 kHz,
  repli matériel contrôlé entre 8 et 48 kHz, mono ou stéréo.
- Accès au périphérique, capture et préparation WAV dans un thread Qt distinct.
  Les appels réseau Voxtral restent asynchrones dans la fenêtre.
- Limite de capture : 60 secondes. À la limite, arrêt et transcription automatiques.
- Annulation pendant la capture : destruction des données sans appel HTTP.
  Interruption pendant l'envoi : abandon de la requête ; les octets déjà transmis
  ne peuvent pas être retirés du service.
- Audio uniquement en mémoire : aucun fichier temporaire audio n'est créé.
  Les buffers sont libérés après utilisation, erreur ou annulation.
- Audio trop court, vide ou silencieux rejeté avant envoi ; une transcription vide
  n'est pas ajoutée au brouillon.
- `context_bias` : au plus 24 entrées de 80 caractères, issues des noms du brouillon,
  de trois candidats maximum par champ et de termes métier. Aucune requête n'envoie
  un catalogue complet pour alimenter ce vocabulaire.
- Erreurs explicites : QtMultimedia indisponible, microphone absent/inaccessible,
  autorisations système, audio non accepté, clé invalide, accès Voxtral interdit,
  crédit/quota insuffisant, délai dépassé et réseau interrompu.
- Délais : 30 secondes pour Mistral Small, 60 secondes pour Voxtral. Les erreurs
  préservent la conversation et permettent de poursuivre au clavier.

Pas de WebSocket, d'écoute permanente, de synthèse vocale des réponses ni de
commande vocale d'enregistrement d'une prestation.

## Clé et distribution

Le fichier local peut contenir la clé brute ou une ligne `MISTRAL_API_KEY=…`, avec
ou sans guillemets. Son contenu n'est ni affiché ni journalisé. Résolution :

1. Chemin choisi dans **Fichier de clé Mistral…**, stocké seul dans le profil QGIS
   (`sig_prestations_dystopic/mistral_key_path`).
2. Sinon variable `DYSTOPIC_MISTRAL_KEY_PATH`.
3. Sinon `MISTRAL_API_KEY.txt` à la racine du checkout, calculée depuis le module,
   indépendamment du répertoire de travail.

Après installation hors dépôt, choisir explicitement le fichier privé local. Ne
pas le placer dans le dossier distribué du plugin. La modification préexistante
de `.gitignore` qui ignore cette clé est conservée et exclue du commit DYSTOPIC.

Construction : `python3 plugin/tools/build_plugin.py`.
Archive : `audits/dist/sig_prestations_dystopic-0.8.0.zip`.
Le manifeste explicite exclut clés, identifiants, tests, données, rapports et audio.
La construction est déterministe et vérifie le contenu de chaque membre.

Le package installé `sig_prestations_dystopic` est distinct de `sig_prestations`.
La construction remplace de façon contrôlée le préfixe absolu `sig_prestations.`
dans les fichiers Python/UI. Cela isole le widget Qt promu, le processus PDF et les
commandes d'actions, sans modifier ces mécanismes métier. Le nom, le SVG Biohazard,
le menu et la barre d'outils sont distincts. Les actions déjà présentes dans un
projet QGIS conservent leur plugin d'origine.

## Tests et résultats

Environnement vérifié : Ubuntu, QGIS **3.44.15**, Qt **5.15.13**, PyQt **5.15.10**.

| Vérification | Résultat |
| --- | --- |
| Brouillon et réponses Mistral simulées | 15 tests réussis |
| Conversation et formulaire réels PyQGIS, transport simulé | 6 tests réussis |
| Capture et API Voxtral simulées, relecture, échanges mixtes | 15 tests réussis |
| Validations existantes `record.py` | 10 tests réussis |
| Accueil et cinquième bouton | 1 test réussi |
| Packaging, imports, installation parallèle et contenu sans clé | 1 test réussi |
| Installation neuve du schéma canonique dans PostGIS jetable | Réussie |
| ZIP installé + Mistral réel, date manquante, complément, formulaire et retour | Réussi |
| Enregistrement standard explicite pour les trois familles dans la base jetable | Réussi, géométries propres NULL |
| Projet QGZ Démo avec ses accès locaux, références réelles et préremplissage | Réussi en lecture seule, sans appel Enregistrer |
| Référentiels Démo et CABBALR par accès connecté en lecture seule | Disponibles, aucune modification |
| Capture réelle du microphone local | Réussie, 2,3 s, mono 16 kHz, aucun fichier ou envoi pour cet essai de capture |
| API Voxtral réelle sur parole française synthétique | Réussie ; résultat détaillé ci-dessous |
| Microphone local → API Voxtral réelle, sans phrase contrôlée | Capture de 2,65 s ; réponse sans texte exploitable, erreur traitée et clavier préservé |
| Windows | Non testé : validation obligatoire restante |

Les tests couvrent notamment : extraction simulée d'une phrase complète, dates
françaises, date de fin manquante et « le même jour », correction du technicien,
référence introuvable, homonymes, faute approchante, quatre familles exclues,
plusieurs objets, UUID inventés, géométrie demandée, absence d'écriture avant
validation, clé absente et formats de clé, réponse tronquée, erreurs/timeout,
annulation de capture y compris signal audio tardif, relecture avant extraction,
alternance texte/voix, libération des buffers et réactivité du thread principal.

Le test d'archive installe également un faux plugin stable qui lève une erreur
s'il est importé par Dystopic. L'import expérimental et le chargement de son
widget personnalisé Qt réussissent malgré cette présence. Le ZIP est vérifié
contre le manifeste, les sources transformées et la valeur de la clé locale,
sans afficher cette valeur.

### Recette réelle des noms propres

Un signal de parole française synthétique a été produit uniquement pour la
recette locale, sans ajout de dépendance au plugin ni conservation de l'audio.
Il a été envoyé à l'API Voxtral réelle avec le vocabulaire du brouillon.
Les termes « débroussaillage », « ouvrage hydraulique », « Veolia » et
« Jean Dubois » ont été reconnus. « Rivière du Buissons » a été transcrit
« rivière du Buisson » : le `s` final manque. Le test du résolveur vérifie que
cette variante exige un choix humain, même avec un candidat unique.

Un second essai a relié directement le microphone local à Voxtral sur 2,65 s.
Sans phrase dictée de façon contrôlée, la réponse ne contenait pas de texte
exploitable : le message prévu pour un audio vide/inaudible a été affiché, sans
appel Mistral Small ni conservation d'audio.

Cet essai de reconnaissance des noms sur parole synthétique est distinct du test
du microphone. Il ne constitue pas une recette de dictée humaine en
conditions de terrain. La transcription est restée visible et modifiable,
sans appel automatique à Mistral Small.

### Commandes reproductibles

```bash
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover -s plugin/tests -p 'test_assistant*.py'
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover -s plugin/tests -p 'test_voice.py'
/usr/bin/python3 -m unittest discover -s plugin/tests -p 'test_record.py'
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover -s plugin/tests -p 'test_home_layout.py'
QT_QPA_PLATFORM=offscreen /usr/bin/python3 -m unittest discover -s plugin/tests -p 'test_package.py'
/usr/bin/python3 plugin/tools/build_plugin.py
QT_QPA_PLATFORM=offscreen /usr/bin/python3 plugin/tests/test_assistant_integration.py
```

Le dernier test exige Docker et l'image `postgis/postgis:16-3.4`. Il crée puis
supprime une base jetable. Ajouter `--live-mistral` pour remplacer les réponses
simulées par l'API réelle sur le scénario fictif ; une clé locale est nécessaire.
Les tests automatisés ordinaires ne nécessitent ni API ni Supabase. Sur Windows,
utiliser le Python fourni avec QGIS et adapter la syntaxe des variables d'environnement.

## Lancement dans QGIS

1. Construire le ZIP puis, dans QGIS 3.44, utiliser **Extensions > Installer/Gérer
   les extensions > Installer depuis un ZIP**.
2. Installer `audits/dist/sig_prestations_dystopic-0.8.0.zip` et activer
   **Prestations Dystopic ☣**. Le plugin stable peut rester installé.
3. Ouvrir `demo/prestations_demo.qgz` et authentifier sa connexion PostgreSQL
   habituelle. Une seule connexion métier de prestations doit être active.
4. Ouvrir l'emblème Biohazard, puis l'assistant. Sélectionner le fichier privé de
   clé si le plugin est installé hors du dépôt.
5. Pour la voix, sélectionner l'entrée microphone par défaut dans le système et
   autoriser QGIS à enregistrer. Dicter, arrêter, corriger puis envoyer.
6. Employer des noms réellement présents dans la base : l'exemple « Veolia /
   Jean Dubois / Rivière du Buissons » sert à la recette jetable et n'est pas
   nécessairement présent dans les référentiels du projet Démo.
7. Compléter les champs, confirmer les candidats puis vérifier le formulaire.
   Seul son bouton Enregistrer sauvegarde la prestation.

Les registres `DEMO_IDENTIFIANTS.local.txt` et `CABBALR_IDENTIFIANTS.local.txt`
ont été retrouvés dans le worktree voisin `sig-prestations`, lus sans divulguer
leurs mots de passe et laissés à leur emplacement. Aucun identifiant PostgreSQL
n'est livré dans le ZIP. Aucune donnée CABBALR n'a servi à fabriquer une fixture
ou un enregistrement audio.

## Fichiers modifiés

- `plugin/sig_prestations/assistant.py`, `assistant_dialog.py`, `voice.py` : modules ajoutés.
- `plugin/sig_prestations/creation.py`, `plugin.py`, `home.ui`, `window_geometry.py` : intégration.
- `plugin/sig_prestations/metadata.txt`, `icons/dystopic.svg`, `help.md` : identité et aide.
- `plugin/tools/build_plugin.py` : distribution expérimentale séparée.
- `plugin/tests/test_assistant.py`, `test_assistant_qgis.py`, `test_assistant_integration.py`,
  `test_voice.py` : tests ajoutés.
- `plugin/tests/test_home_layout.py`, `test_package.py`, `smoke_import.py` : tests adaptés.
- `README.md`, `plugin/README.md` : installation et usage actualisés.
- `audits/DYSTOPIC-01.md` : présent livrable.

## Limites et prochaines étapes

- Recette Windows obligatoire avant toute annonce de compatibilité Windows ou
  diffusion générale : installation parallèle, autorisations microphone,
  périphériques, annulation, appels TLS et fermeture/déchargement du plugin.
- Recette humaine au microphone avec les accents, bruits et noms patrimoniaux
  réellement employés. Le contexte Voxtral n'élimine pas les erreurs orthographiques.
- Capture fondée sur QtMultimedia Qt5, vérifié dans le QGIS Linux installé.
  Une installation sans ce module conserve le clavier avec un message explicite.
  Aucune compatibilité Qt6 n'est annoncée.
- Périphérique d'entrée par défaut du système ; pas de sélecteur de matériel dans
  le prototype. Audio conservé uniquement pour la requête, sans réécoute locale.
- La détection locale de silence est un seuil simple, pas un système de détection
  de parole. Les enregistrements bruités doivent être relus, voire redictés.
- L'état est perdu au déchargement du plugin. Il n'existe pas de nouvelle table
  d'historique, ni de mécanisme de conversation permanente.
- Réévaluer les consultations synchrones si les catalogues deviennent volumineux.
- Une éventuelle synthèse vocale devra conserver les réponses visibles et ne
  jamais introduire de commande de sauvegarde automatique. Elle reste hors périmètre.

## Documentation officielle consultée

- [Mistral — sorties structurées](https://docs.mistral.ai/inference/conversations/structured-output/custom).
- [Mistral — transcription de fichiers](https://docs.mistral.ai/studio/audio/speech-to-text/transcribe-files).
- [Mistral — contexte et vocabulaire](https://docs.mistral.ai/studio/audio/speech-to-text/bias-context-and-vocabulary).
