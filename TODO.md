# TODO — SIG-Prestations

## Stabilisation avant démonstration
- [ ] **Gel fonctionnel** : aucun nouveau chantier ; corriger uniquement les anomalies bloquantes.
- [ ] Corriger `digitize.py` : `CaptureTool` reçoit encore des événements après destruction de `_snap_marker` (`AttributeError: NoneType.hide`) ; tester fin, annulation et retour à l'outil QGIS précédent.
- [ ] Vérifier le plugin installé, les projets Démo/CABBALR après migration et l'activation du QGZ CABBALR **sans filtre des cours d'eau anonymes**.

## Après démonstration
- [ ] **NULLABLE** — AH ouvrage ne devrait pas etre nullable. verifier autres. ah_section geometrie devrait etre facultatif
- [ ] **PERF-QGIS-09C** — Retirer `prestations_fiches` des deux QGZ après remplacement des relations et navigations nécessaires ; conserver la vue SQL ; mesurer le gain.
- [ ] **DIGITIZE-TRACE-01** — Ajouter le *tracé automatique* QGIS (reprise des sommets intermédiaires), distinct de l'accrochage qui fonctionne déjà.
- [ ] **AH** — Ajouter « Créer une section AH… » dans **Extensions > Prestations DMNR**, sur le modèle de « Créer une digue… » ; réutiliser les contrôles de validation existants.
- [ ] **Gestionnaire** — Ajouter un filtre spatial autour d'un point cliqué sur la carte, combiné par **ET** aux filtres métier existants et facilement réinitialisable.
- [ ] **Carte → plugin** — Étudier un outil d'identification en un clic ouvrant directement la prestation dans le plugin ; gérer les superpositions et le profil Lecture. Conserver l'action « Modifier cette prestation » existante.
- [ ] **PDF / fonds IGN** — Profiler les rapports longs et les erreurs IGN Épuré intermittentes ; comparer IGN classique/Épuré/orthophoto à paramètres égaux avant tout changement de fond par défaut.
- [ ] **Référentiels** — Autoriser le profil Patrimoine à gérer les cinq référentiels métier, avec chargement à la demande ; communes réservées à l'administration SIG.
- [ ] **Rationalisation QGIS** — Étudier les autres couches non spatiales et réaliser le benchmark final après simplification.
- [ ] **Compatibilité (en dernier)** — Qualifier plugin, QGZ, capture et PDF sous QGIS **3.44 APT natif**, **3.40 Docker** et **3.34 Docker**, puis compléter la recette Windows ; viser un seul ZIP.
