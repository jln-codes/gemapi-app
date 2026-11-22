"""DYSTOPIC-02 language bench: simulated extraction and independent local resolution.

Ordinary tests never call an API or a database. Optional real extraction only:
    /usr/bin/python3 plugin/tests/test_assistant_linguistics.py --live --limit 12
The live mode sends the bench's explicit test catalogue, never reads CABBALR and
never opens a form or writes a prestation. UUIDs below are fictitious test IDs.
"""

import argparse
import copy
import json
from pathlib import Path
import sys
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.assistant import (Draft, ENDPOINT, normalized, parse_date, parse_response,
                                     read_api_key, request_payload)
from test_assistant import proposal, response, uid

CATALOG = {
    'type_prestation': [(uid(101), 'Débroussaillage', 'Entretien mécanique'),
                        (uid(102), 'Fauche', 'Entretien mécanique'),
                        (uid(103), 'Élagage', 'Entretien manuel')],
    'prestataire': [(uid(201), 'Noeux Environnement', ''), (uid(202), 'Veolia', '')],
    'technicien': [(uid(301), 'Benoît Quentin', ''), (uid(302), 'Pierre Martin', '')],
    'statut': [(uid(401), 'Terminé', ''), (uid(402), 'En cours', ''), (uid(403), 'Planifié', '')],
    'patrimoine': [(uid(501), 'Talus ZEC Ourton', 'AH de test'),
                   (uid(502), 'Stockage Démo', 'AH de test'), (uid(503), 'Zone Démo', 'Site de test')],
}
CATALOG['patrimoines'] = {'ah_ouvrage': [CATALOG['patrimoine'][0]],
                           'ah_stockage': [CATALOG['patrimoine'][1]],
                           'sites_zones': [CATALOG['patrimoine'][2]]}

BASE = {'famille': 'ah_ouvrage', 'patrimoine': 'Talus ZEC Ourton', 'type_prestation': 'Débroussaillage',
        'prestataire': 'Noeux Environnement', 'technicien': 'Benoît Quentin', 'statut': 'Terminé',
        'date_debut': '2026-11-11'}
CONTEXT = {key: value for key, value in BASE.items() if key != 'type_prestation'}
REPORTED_EXCHANGE = (
    "Je veux créer une intervention de débroussaillage sur l'ouvrage hydraulique Talus ZEC Ourton. "
    "C'était le 11 novembre 2026, l'entreprise Noeux Environnement est intervenue et le suivi "
    "était assuré par Benoît Quentin. Le chantier est terminé.")


def case(name, text, fields, *, prior=None, local_type=None, expected_type='Débroussaillage',
         pending=None, absent=None, ready=False, catalog=None):
    return dict(name=name, text=text, fields={'date_fin': None, **fields}, prior=prior or {},
                local_type=local_type, expected_type=expected_type, pending=pending,
                absent=absent, ready=ready, catalog=catalog or CATALOG)


HOMONYMS = copy.deepcopy(CATALOG)
HOMONYMS['type_prestation'].append((uid(104), 'Débroussaillage', 'Autre catégorie'))
OBJECT_HOMONYMS = copy.deepcopy(CATALOG)
OBJECT_HOMONYMS['patrimoine'].append((uid(504), 'Talus ZEC Ourton', 'Autre AH de test'))
CASES = [
    case('cabbalr_reported', REPORTED_EXCHANGE, BASE, local_type='intervention de débroussaillage'),
    case('prestation', 'Créer une prestation de débroussaillage sur Talus ZEC Ourton.',
         {'type_prestation': 'Débroussaillage', 'patrimoine': 'Talus ZEC Ourton'}, prior=CONTEXT,
         local_type='prestation de débroussaillage'),
    case('fragmented', 'Une intervention sur Talus ZEC Ourton. Débroussaillage.',
         {'type_prestation': 'Débroussaillage', 'patrimoine': 'Talus ZEC Ourton'}, prior=CONTEXT),
    case('travaux_pronoun', 'Veolia a réalisé des travaux de débroussaillage sur cet ouvrage.',
         {'type_prestation': 'Débroussaillage', 'prestataire': 'Veolia'}, prior=CONTEXT,
         local_type='travaux de débroussaillage'),
    case('chantier', 'Le chantier de débroussaillage est terminé.',
         {'type_prestation': 'Débroussaillage', 'statut': 'Terminé'}, prior=CONTEXT,
         local_type='chantier de débroussaillage'),
    case('fauche', 'Des travaux de fauche sur Talus ZEC Ourton.',
         {'type_prestation': 'Fauche'}, prior=CONTEXT, local_type='travaux de fauche', expected_type='Fauche'),
    case('elagage', "Une prestation d'élagage sur cet ouvrage.",
         {'type_prestation': 'Élagage'}, prior=CONTEXT, local_type="prestation d'élagage", expected_type='Élagage'),
    case('spoken_month_year', REPORTED_EXCHANGE.replace('11 novembre 2026', 'onze novembre deux mille vingt-six'), BASE),
    case('numeric_date', REPORTED_EXCHANGE.replace('11 novembre 2026', '11/11/2026'), BASE),
    case('spoken_numeric_date', REPORTED_EXCHANGE.replace('11 novembre 2026', 'onze zéro neuf 2026'),
         {**BASE, 'date_debut': '2026-09-11'}),
    case('ah_ouvrage', REPORTED_EXCHANGE.replace('ouvrage hydraulique', 'AH ouvrage'), BASE),
    case('a_h_ouvrage', REPORTED_EXCHANGE.replace('ouvrage hydraulique', 'A H ouvrage'), BASE),
    case('provider_first', "Noeux Environnement est intervenue le 11 novembre 2026. Benoît Quentin assurait "
         "le suivi. Débroussaillage terminé sur l'ouvrage hydraulique Talus ZEC Ourton.", BASE),
    case('date_first', "Le 11 novembre 2026, sur l'ouvrage hydraulique Talus ZEC Ourton : suivi Benoît Quentin, "
         "entreprise Noeux Environnement. Travaux de débroussaillage terminés.", BASE,
         local_type='travaux de débroussaillage terminés'),
    case('telegraphic', "Talus ZEC Ourton, ouvrage hydraulique. Débroussaillage. Noeux Environnement. "
         "Benoît Quentin. Terminé. Début 11/11/2026.", BASE),
    case('no_accents', REPORTED_EXCHANGE.replace('débroussaillage', 'debroussaillage').replace('Benoît', 'Benoit'), BASE),
    case('ligature', REPORTED_EXCHANGE.replace('Noeux', 'Nœux'), BASE),
    case('uppercase', REPORTED_EXCHANGE.upper(), BASE, local_type='INTERVENTION DE DÉBROUSSAILLAGE'),
    case('punctuation', 'Une intervention : débroussaillage !', {'type_prestation': 'Débroussaillage'},
         prior=CONTEXT, local_type='une intervention : débroussaillage !'),
    case('stockage', 'Une prestation de fauche sur le stockage hydraulique Stockage Démo.',
         {'type_prestation': 'Fauche', 'famille': 'ah_stockage', 'patrimoine': 'Stockage Démo'},
         prior=CONTEXT, local_type='prestation de fauche', expected_type='Fauche'),
    case('zone', "Travaux d'élagage sur la zone terrestre Zone Démo.",
         {'type_prestation': 'Élagage', 'famille': 'sites_zones', 'patrimoine': 'Zone Démo'},
         prior=CONTEXT, local_type="travaux d'élagage", expected_type='Élagage'),
    case('unknown_type', 'Créer une intervention de traitement par laser sur cet ouvrage.',
         {'type_prestation': 'traitement par laser'}, prior=CONTEXT, expected_type=None, absent='type_prestation'),
    case('unknown_provider', "L'entreprise était Entreprise Introuvable.",
         {'prestataire': 'Entreprise Introuvable'}, prior=BASE, absent='prestataire'),
    case('unknown_object', "L'ouvrage hydraulique était Ouvrage Introuvable.",
         {'famille': 'ah_ouvrage', 'patrimoine': 'Ouvrage Introuvable'}, prior=BASE, absent='patrimoine'),
    case('two_types', "Créer un chantier de débroussaillage et élagage sur cet ouvrage.",
         {'type_prestation': 'Débroussaillage et Élagage'}, prior=CONTEXT,
         local_type='chantier de débroussaillage et élagage', expected_type=None, pending='type_prestation'),
    case('type_homonyms', 'Créer une prestation de débroussaillage sur cet ouvrage.',
         {'type_prestation': 'Débroussaillage', 'categorie': None}, prior=CONTEXT,
         expected_type=None, pending='type_prestation', catalog=HOMONYMS),
    case('object_homonyms', "Débroussaillage sur l'ouvrage hydraulique Talus ZEC Ourton.",
         {'type_prestation': 'Débroussaillage', 'famille': 'ah_ouvrage', 'patrimoine': 'Talus ZEC Ourton'},
         prior=CONTEXT, pending='patrimoine', catalog=OBJECT_HOMONYMS),
    case('technician_correction', 'Non, le suivi était assuré par Pierre Martin.',
         {'technicien': 'Pierre Martin'}, prior=BASE),
    case('provider_correction', "Correction : l'entreprise était Veolia.", {'prestataire': 'Veolia'}, prior=BASE),
    case('same_day_reply', 'Le même jour.', {'date_fin': 'MEME_JOUR'}, prior=BASE, ready=True),
    case('spoken_end_date', 'La date de fin est le douze novembre deux mille vingt-six.',
         {'date_fin': '2026-11-12'}, prior=BASE, ready=True),
    case('ambiguous_date', REPORTED_EXCHANGE.replace('11 novembre 2026', '11 ou 12 novembre 2026'),
         {**BASE, 'date_debut': None}),
    case('missing_year', REPORTED_EXCHANGE.replace('11 novembre 2026', '11 novembre'), {**BASE, 'date_debut': None}),
    case('ordinal_date', REPORTED_EXCHANGE.replace('11 novembre 2026', 'premier février deux mille vingt-six'),
         {**BASE, 'date_debut': '2026-02-01'}),
]


DESCRIPTION_CASES = [
    case('description_riche', REPORTED_EXCHANGE +
         " Euh, près de la buse en rive droite, au pied du mur. Les ronces bloquaient l'accès. "
         "L'accès était impraticable pour l'engin. Les déchets ont été évacués.",
         {**BASE, 'description': "Près de la buse, en rive droite au pied du mur. Les ronces bloquaient "
          "l'accès, impraticable pour l'engin. Les déchets ont été évacués."}),
    case('description_desordonnee', "Au pied du mur, des déchets évacués. Noeux Environnement est intervenue. "
         "Benoît Quentin assurait le suivi. Sur l'ouvrage hydraulique Talus ZEC Ourton, "
         "le 11 novembre 2026, chantier de débroussaillage terminé. Accès difficile à la buse.",
         {**BASE, 'description': "Déchets évacués au pied du mur. Accès difficile à la buse."}),
    case('description_repetitions', REPORTED_EXCHANGE +
         " Bon alors voilà, accès difficile près de la buse. Euh, accès difficile près de la buse, "
         "je répète, accès difficile près de la buse. Voilà merci.",
         {**BASE, 'description': "Accès difficile près de la buse."}),
    case('description_champs_seuls', REPORTED_EXCHANGE, {**BASE, 'description': ''}),
]


def description_errors(item, extracted):
    description = extracted.get('description')
    if not isinstance(description, str):
        return ['description_absente']
    if item['name'] == 'description_champs_seuls':
        return [] if not description.strip() else ['description_non_vide']
    text = normalized(description)
    forbidden = ('talus', 'ourton', 'noeux', 'benoit', 'quentin', '2026', 'novembre',
                 'debroussaillage', 'termine', 'manuellement', 'securise')
    errors = ['description_redondante_ou_inventee'] if any(word in text for word in forbidden) else []
    required = {'description_riche': ('buse', 'rive droite', 'mur', 'ronces', 'engin', 'dechets', 'evacu'),
                'description_desordonnee': ('mur', 'dechets', 'evacu', 'acces', 'buse'),
                'description_repetitions': ('acces', 'difficile', 'buse')}[item['name']]
    if not all(word in text for word in required):
        errors.append('description_faits_perdus')
    if len(description) > (110 if item['name'] == 'description_repetitions' else 400):
        errors.append('description_trop_longue')
    if any(word in text.split() for word in ('euh', 'merci', 'voila', 'repete')):
        errors.append('description_conversationnelle')
    return errors


# Exact test catalogues, no database access and no local phonetic engine.
NAMES_TEXT = REPORTED_EXCHANGE.replace('Benoît Quentin', 'Benoît Cantin').replace(
    'Talus ZEC Ourton', 'Talus ZEC Hurton')
NAMES_FIELDS = {**BASE, 'patrimoine': 'Talus ZEC Ourton — AH de test'}
NAMES_MATCHES = {
    'technicien': {'source': 'Benoît Cantin', 'nature': 'phonetique_complete', 'candidats': ['Benoît Quentin']},
    'prestataire': {'source': 'Noeux Environnement', 'nature': 'exacte', 'candidats': ['Noeux Environnement']},
    'patrimoine': {'source': 'Talus ZEC Hurton', 'nature': 'phonetique_complete',
                   'candidats': ['Talus ZEC Ourton — AH de test']}}


def name_case(name, text, fields=None, matches=None, catalog=None, pending=()):
    metadata = copy.deepcopy(NAMES_MATCHES)
    metadata.update(matches or {})
    catalog = copy.deepcopy(catalog or CATALOG)
    family = (fields or {}).get('famille', BASE['famille'])
    catalog['patrimoine'] = catalog['patrimoines'][family]
    item = case(name, text, {**NAMES_FIELDS, **(fields or {}), 'correspondances': metadata}, catalog=catalog)
    item['name_pending'] = pending
    return item


NAME_CASES = [name_case('voix_noms_complets_uniques', NAMES_TEXT)]
exact_catalog = copy.deepcopy(CATALOG)
exact_catalog['technicien'].append((uid(304), 'Benoît Cantin', ''))
NAME_CASES.append(name_case('priorite_exacte', NAMES_TEXT,
    {'technicien': 'Benoît Cantin'},
    {'technicien': {'source': 'Benoît Cantin', 'nature': 'exacte', 'candidats': ['Benoît Cantin']}}, exact_catalog))
NAME_CASES.append(name_case('priorite_normalisee', NAMES_TEXT.replace('Benoît Cantin', 'BENOIT QUENTIN'),
    matches={'technicien': {'source': 'BENOIT QUENTIN', 'nature': 'exacte', 'candidats': ['Benoît Quentin']}}))
ambiguous_catalog = copy.deepcopy(CATALOG)
ambiguous_catalog['technicien'].append((uid(305), 'Benoît Quantin', ''))
NAME_CASES.append(name_case('homophones_techniciens', NAMES_TEXT, {'technicien': 'Benoît Cantin'},
    {'technicien': {'source': 'Benoît Cantin', 'nature': 'ambigue',
                    'candidats': ['Benoît Quentin', 'Benoît Quantin']}}, ambiguous_catalog, ('technicien',)))
NAME_CASES.append(name_case('prenom_seul', NAMES_TEXT.replace('Benoît Cantin', 'Benoît'), {'technicien': 'Benoît'},
    {'technicien': {'source': 'Benoît', 'nature': 'approximative', 'candidats': ['Benoît Quentin']}}, pending=('technicien',)))
stock_catalog = copy.deepcopy(CATALOG)
stock_catalog['patrimoine'] = [(uid(506), 'Bassin Ourton', 'AH de test')]
stock_catalog['patrimoines']['ah_stockage'] = stock_catalog['patrimoine']
NAME_CASES.append(name_case('stockage_ah_parent', NAMES_TEXT.replace('ouvrage hydraulique Talus ZEC Hurton',
    'stockage hydraulique Bassin Hurton'), {'famille': 'ah_stockage', 'patrimoine': 'Bassin Ourton — AH de test'},
    {'patrimoine': {'source': 'Bassin Hurton', 'nature': 'phonetique_complete',
                    'candidats': ['Bassin Ourton — AH de test']}}, stock_catalog))
zone_catalog = copy.deepcopy(CATALOG)
zone_catalog['patrimoine'] = [(uid(507), 'Prairie Ourton', 'Site Nord'), (uid(508), 'Prairie Ourton', 'Site Sud')]
zone_catalog['patrimoines']['sites_zones'] = zone_catalog['patrimoine']
NAME_CASES.append(name_case('zone_site_parent', NAMES_TEXT.replace('ouvrage hydraulique Talus ZEC Hurton',
    'zone terrestre Prairie Hurton du site Site Nord'), {'famille': 'sites_zones', 'patrimoine': 'Prairie Ourton — Site Nord'},
    {'patrimoine': {'source': 'Prairie Hurton', 'nature': 'phonetique_complete',
                    'candidats': ['Prairie Ourton — Site Nord']}}, zone_catalog))
parent_catalog = copy.deepcopy(CATALOG)
parent_catalog['patrimoine'] = [CATALOG['patrimoine'][0], (uid(509), 'Talus ZEC Ourton', 'AH du Sud')]
parent_catalog['patrimoines']['ah_ouvrage'] = parent_catalog['patrimoine']
NAME_CASES.append(name_case('patrimoine_parent_non_precise', NAMES_TEXT, {'patrimoine': 'Talus ZEC Hurton'},
    {'patrimoine': {'source': 'Talus ZEC Hurton', 'nature': 'ambigue',
                    'candidats': ['Talus ZEC Ourton — AH de test', 'Talus ZEC Ourton — AH du Sud']}},
    parent_catalog, ('patrimoine',)))

company_catalog = copy.deepcopy(CATALOG)
company_catalog['prestataire'].append((uid(210), "Eaux d'Artois", ''))
NAME_CASES.append(name_case('raison_sociale_phonetique_complete', NAMES_TEXT.replace('Noeux Environnement', "Ô d'Artois"),
    {'prestataire': "Eaux d'Artois"},
    {'prestataire': {'source': "Ô d'Artois", 'nature': 'phonetique_complete', 'candidats': ["Eaux d'Artois"]}}, company_catalog))
NAME_CASES.append(name_case('raison_sociale_approximative', NAMES_TEXT.replace('Noeux Environnement', 'Véollia'),
    {'prestataire': 'Veolia'}, {'prestataire': {'source': 'Véollia', 'nature': 'approximative', 'candidats': ['Veolia']}},
    pending=('prestataire',)))


def name_errors(item, extracted):
    errors = []
    expected = item['fields']['correspondances']
    matches = extracted.get('correspondances') or {}
    for field, match in expected.items():
        actual = matches.get(field)
        if not actual or actual['nature'] != match['nature']:
            errors.append('nature_' + field)
    draft = Draft()
    context = json.loads(request_payload(draft, item['text'], item['catalog'])['messages'][1]['content'])['referentiels']
    try:
        draft.apply(extracted, user_message=item['text'], reference_context=context)
        resolved = draft.resolve(item['catalog'])
    except ValueError:
        return errors + ['validation_locale']
    for field in expected:
        if field in item['name_pending']:
            if field in resolved['verified'] or not resolved['pending'].get(field):
                errors.append('clarification_' + field)
        elif field not in resolved['verified']:
            errors.append('resolution_' + field)
    return errors


def draft_for(item):
    draft = Draft()
    draft.apply(proposal(**item['prior']))
    return draft


def extraction_errors(item, extracted):
    errors = []
    for key, expected in item['fields'].items():
        actual = extracted.get(key)
        if key in item.get('name_pending', ()) or key == 'correspondances':
            continue
        if key == 'patrimoine' and any(normalized(actual) == normalized(row[1] + ' — ' + row[2]) and
                normalized(expected) == normalized(row[1]) for row in item['catalog'].get('patrimoine', [])):
            continue
        if key == 'description':
            continue  # Semantic criteria below accept equivalent factual reformulations.
        if key == 'type_prestation' and item['name'] == 'two_types':
            if not actual or not all(normalized(label) in normalized(actual) for label in ('Débroussaillage', 'Élagage')):
                errors.append(key)
        elif expected is None:
            if actual is not None:
                errors.append(key)
        elif key.startswith('date_') and expected != 'MEME_JOUR':
            try:
                if parse_date(actual) != expected:
                    errors.append(key)
            except (ValueError, TypeError):
                errors.append(key)
        elif key == 'type_prestation':
            if actual != expected:
                errors.append(key)
        elif key == 'date_fin' and expected == 'MEME_JOUR':
            if actual not in ('MEME_JOUR', item['prior']['date_debut']):
                errors.append(key)
        elif normalized(actual) != normalized(expected):
            errors.append(key)
    return errors


class LinguisticBenchTests(unittest.TestCase):
    def test_simulated_extraction_protocol_independent_of_resolution(self):
        self.assertGreaterEqual(len(CASES), 25)
        for item in CASES:
            with self.subTest(case=item['name']):
                draft = draft_for(item)
                payload = request_payload(draft, item['text'], item['catalog'])
                context = json.loads(payload['messages'][1]['content'])
                self.assertEqual(context['demande'], item['text'])
                self.assertEqual([row['libelle'] for row in context['referentiels']['types_prestations']],
                                 [row[1] for row in item['catalog']['type_prestation']])
                extracted = parse_response(response(**item['fields']))  # Simulated API, no semantic claim.
                self.assertEqual(extraction_errors(item, extracted), [])

    def test_local_resolution_of_all_variants_including_imperfect_extraction(self):
        for item in CASES:
            with self.subTest(case=item['name']):
                draft = draft_for(item)
                patch = dict(item['fields'])
                if item['local_type']:
                    patch['type_prestation'] = item['local_type']
                draft.apply(proposal(**patch), user_message=item['text'])
                result = draft.resolve(item['catalog'])
                if item['expected_type']:
                    self.assertEqual(result['verified']['type_prestation'][1], item['expected_type'])
                else:
                    self.assertNotIn('type_prestation', result['verified'])
                if item['pending']:
                    self.assertGreaterEqual(len(result['pending'][item['pending']]), 2)
                if item['absent']:
                    self.assertNotIn(item['absent'], result['verified'])
                self.assertEqual(result['values'] is not None, item['ready'])
                if not item['ready']:
                    self.assertTrue(any('date de fin' in issue for issue in result['issues']))
                if item['fields'].get('date_debut'):
                    self.assertEqual(draft.names['date_debut'], item['fields']['date_debut'])
                if item['name'].endswith('_correction'):
                    self.assertEqual(draft.names['patrimoine'], BASE['patrimoine'])
                    self.assertEqual(draft.names['date_debut'], BASE['date_debut'])


class DescriptionTests(unittest.TestCase):
    def test_same_structured_response_and_local_draft_for_rich_or_empty_description(self):
        for item in DESCRIPTION_CASES:
            with self.subTest(case=item['name']):
                payload = request_payload(Draft(), item['text'], CATALOG)
                self.assertEqual(len(payload['messages']), 2)
                self.assertIn('description', payload['response_format']['json_schema']['schema']['required'])
                extracted = parse_response(response(**item['fields']))
                self.assertEqual(description_errors(item, extracted), [])
                draft = Draft()
                draft.apply(extracted, user_message=item['text'])
                draft.apply(proposal(date_fin='MEME_JOUR'), user_message='Le même jour.')
                result = draft.resolve(CATALOG)
                self.assertEqual(result['values']['description'], item['fields']['description'])
                self.assertEqual(result['values']['type_prestation_id'], uid(101))

    def test_structured_correction_preserves_description_and_explicit_replacement_or_clear(self):
        draft = Draft()
        draft.apply(proposal(**DESCRIPTION_CASES[0]['fields']), user_message=DESCRIPTION_CASES[0]['text'])
        before = draft.names['description']
        draft.apply(parse_response(response(technicien='Pierre Martin', description=None)),
                    user_message='Non, le technicien était Pierre Martin.')
        self.assertEqual(draft.names['description'], before)
        draft.apply(parse_response(response(description='Accès difficile en rive gauche.')),
                    user_message='Correction : accès difficile en rive gauche seulement.')
        self.assertEqual(draft.names['description'], 'Accès difficile en rive gauche.')
        draft.apply(parse_response(response(description='')), user_message='Efface la description.')
        self.assertEqual(draft.names['description'], '')


class ProperNameTests(unittest.TestCase):
    def resolve_name(self, text, fields, catalog):
        draft = Draft()
        context = json.loads(request_payload(draft, text, catalog)['messages'][1]['content'])['referentiels']
        draft.apply(proposal(**fields), user_message=text, reference_context=context)
        return draft.resolve(catalog)

    def test_first_name_only_remains_pending_even_if_model_claims_complete(self):
        item = NAME_CASES[4]  # Existing first-name-only fixture.
        fields = copy.deepcopy(item['fields'])
        fields['correspondances']['technicien']['nature'] = 'phonetique_complete'
        result = self.resolve_name(item['text'], fields, item['catalog'])
        self.assertNotIn('technicien', result['verified'])

    def test_compact_spelling_collisions_never_select_first_candidate(self):
        catalog = copy.deepcopy(CATALOG)
        catalog['technicien'].append((uid(310), 'BenoîtQuentin', ''))
        text = NAMES_TEXT.replace('Benoît Cantin', 'Benoît Quen tin')
        fields = {**NAMES_FIELDS, 'correspondances':copy.deepcopy(NAMES_MATCHES)}
        fields['correspondances']['technicien']['source'] = 'Benoît Quen tin'
        result = self.resolve_name(text, fields, catalog)
        self.assertNotIn('technicien', result['verified'])
        self.assertEqual({r[0] for r in result['pending']['technicien']}, {uid(301),uid(310)})

    def test_singular_plural_company_needs_model_evidence_not_local_stemming(self):
        # Fictional unit fixture: no nominative exception in production Python.
        catalog = copy.deepcopy(CATALOG)
        catalog['prestataire'].append((uid(211), 'Jardins et Rivières', ''))
        text = NAMES_TEXT.replace('Noeux Environnement', 'Jardin et rivière')
        fields = {**NAMES_FIELDS, 'prestataire':'Jardins et Rivières',
                  'correspondances':copy.deepcopy(NAMES_MATCHES)}
        fields['correspondances']['prestataire'] = {'source':'Jardin et rivière',
            'nature':'phonetique_complete','candidats':['Jardins et Rivières']}
        result = self.resolve_name(text, fields, catalog)
        self.assertEqual(result['verified']['prestataire'][0],uid(211))
        fields['correspondances']['prestataire']['nature']='approximative'
        self.assertNotIn('prestataire',self.resolve_name(text, fields, catalog)['verified'])

    def test_simulated_mistral_classification_and_python_resolution_for_all_cases(self):
        for item in NAME_CASES:
            with self.subTest(case=item['name']):
                extracted = parse_response(response(**item['fields']))
                self.assertEqual(extraction_errors(item, extracted), [])
                self.assertEqual(name_errors(item, extracted), [])


def live_bench(limit, descriptions=False, names=False):
    key = read_api_key()
    outcomes = []
    for item in (NAME_CASES if names else DESCRIPTION_CASES if descriptions else CASES)[:limit or None]:
        payload = request_payload(draft_for(item), item['text'], item['catalog'])
        request = Request(ENDPOINT, json.dumps(payload).encode('utf-8'),
                          {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
        try:
            with urlopen(request, timeout=30) as reply:
                extracted = parse_response(reply.read(1024 * 1024))
            errors = extraction_errors(item, extracted)
            if names:
                errors.extend(name_errors(item, extracted))
            if descriptions:
                errors.extend(description_errors(item, extracted))
            outcome = {'case': item['name'], 'ok': not errors, 'champs_a_verifier': errors,
                       'valeurs_a_verifier': {key: extracted.get(key) for key in errors}}
            if names and errors:
                outcome['correspondances'] = extracted.get('correspondances')
                outcome['propositions'] = {key: extracted.get(key) for key in ('technicien', 'prestataire', 'patrimoine', 'famille')}
        except HTTPError as error:
            outcome = {'case': item['name'], 'ok': False, 'http': error.code}
        except (URLError, TimeoutError, ValueError):
            outcome = {'case': item['name'], 'ok': False, 'erreur': 'Réseau, délai ou réponse invalide'}
        outcomes.append(outcome)
        print(json.dumps(outcome, ensure_ascii=False), flush=True)
    print(json.dumps({'api_reelle': True, 'reussis': sum(row['ok'] for row in outcomes),
                      'total': len(outcomes), 'base_interrogee': False, 'ecriture': False}), flush=True)
    return all(row['ok'] for row in outcomes)


if __name__ == '__main__':
    if '--live' in sys.argv:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--live', action='store_true')
        parser.add_argument('--descriptions', action='store_true', help='Banc de description complémentaire DYSTOPIC-03')
        parser.add_argument('--names', action='store_true', help='Noms propres : Mistral puis vérification Python')
        parser.add_argument('--limit', type=int, default=0, help='0 = tout le banc')
        args = parser.parse_args()
        if args.limit < 0:
            parser.error('--limit doit être positif')
        raise SystemExit(0 if live_bench(args.limit, args.descriptions, args.names) else 1)
    unittest.main()
