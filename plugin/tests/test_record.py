"""Pure Python checks for creation validation and one-statement SQL."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.record import build_insert, validate  # noqa: E402


PRESTATAIRE = "11111111-1111-1111-1111-111111111111"
OBJECT = "22222222-2222-2222-2222-222222222222"
TYPE = "33333333-3333-3333-3333-333333333333"
STATUT = "44444444-4444-4444-4444-444444444444"
TECHNICIEN = "55555555-5555-5555-5555-555555555555"
REQUIRED = {"type_prestation_id": TYPE, "prestataire_id": PRESTATAIRE,
            "statut_id": STATUT, "technicien_id": TECHNICIEN,
            "date_debut": "2026-10-29",
            "date_fin": "2026-10-30"}


class RecordTests(unittest.TestCase):
    def test_seventh_direct_attachment_requires_own_geometry(self):
        links = [("ah_sections", OBJECT)]
        with self.assertRaisesRegex(ValueError, "géométrie propre"):
            validate(REQUIRED, links)
        values = {**REQUIRED, "position": "Berge", "rive": "Gauche"}
        query = build_insert(values, links, "POINT(0 0)")
        self.assertIn("ah_section_id", query)
        self.assertEqual(query.count(OBJECT), 1)
        for other in ("cours_eau", "digues", "ah_stockage", "ah_ouvrage", "sites_terrestres", "sites_zones"):
            with self.subTest(other=other), self.assertRaises(ValueError):
                validate(values, links + [(other, OBJECT)], "POINT(0 0)")

    def test_required_fields_and_association(self):
        for values, links in (({}, []), ({"intitule": "Travaux"}, [("ah_stockage", OBJECT)]),
                              (REQUIRED, [])):
            with self.assertRaises(ValueError):
                validate(values, links)

    def test_date_order_and_quantity(self):
        values = {**REQUIRED, "date_fin": "2026-10-28"}
        with self.assertRaisesRegex(ValueError, "date de fin"):
            validate(values, [("ah_stockage", OBJECT)], "POINT(0 0)")
        values["date_fin"] = ""
        values["quantite"] = "NaN"
        with self.assertRaisesRegex(ValueError, "obligatoires"):
            validate(values, [("ah_stockage", OBJECT)], "POINT(0 0)")

    def test_single_statement_and_escaped_text(self):
        values = {**REQUIRED, "intitule": "L'étang", "quantite": "12,5"}
        sql = build_insert(values, [("ah_stockage", OBJECT), ("ah_stockage", OBJECT)],
                           "POINT(0 0)")
        self.assertEqual(sql.count("INSERT INTO"), 1)
        self.assertEqual(sql.count("22222222-2222-2222-2222-222222222222"), 1)
        self.assertIn("L''étang", sql)
        self.assertIn("E'12.5'::numeric", sql)
        self.assertEqual(sql.count(";"), 1)  # Séparateur EWKT, aucune autre commande SQL.
        self.assertTrue(sql.startswith("WITH "))

    def test_rejects_unknown_category_and_nul(self):
        values = dict(REQUIRED)
        with self.assertRaises(ValueError):
            build_insert(values, [("inconnue", OBJECT)], "POINT(0 0)")
        values["description"] = "abc\x00def"
        with self.assertRaises(ValueError):
            build_insert(values, [("ah_stockage", OBJECT)], "POINT(0 0)")

    def test_all_six_attachment_mappings(self):
        values = dict(REQUIRED)
        for category, foreign_key in (
            ("ah_stockage", "ah_stockage_id"),
            ("ah_ouvrage", "ah_ouvrage_id"),
            ("cours_eau", "cours_eau_id"),
            ("digues", "digue_id"),
            ("sites_terrestres", "site_terrestre_id"),
            ("sites_zones", "site_zone_id"),
        ):
            sql = build_insert(values, [(category, OBJECT)],
                               None if category == "sites_zones" else "POINT(0 0)")
            self.assertIn(foreign_key, sql)
            self.assertEqual(sql.count("INSERT INTO"), 1)

    def test_category_and_position_rules(self):
        with self.assertRaisesRegex(ValueError, "Une seule catégorie"):
            build_insert(REQUIRED, [("cours_eau", OBJECT), ("ah_stockage", OBJECT)], "POINT(0 0)")
        with self.assertRaisesRegex(ValueError, "nécessite un cours d'eau"):
            build_insert({**REQUIRED, "position": "Berge"},
                         [("ah_stockage", OBJECT)], "POINT(0 0)")
        with self.assertRaisesRegex(ValueError, "Position inconnue"):
            build_insert({**REQUIRED, "position": "Amont"}, [], "POINT(0 0)")
        sql = build_insert({**REQUIRED, "position": "Crête"},
                           [("cours_eau", OBJECT)], "POINT(0 0)")
        self.assertIn("E'Crête'", sql)

    def test_single_patrimony_including_zones(self):
        second = "66666666-6666-6666-6666-666666666666"
        for family in ("cours_eau", "digues", "ah_stockage", "ah_ouvrage", "sites_zones"):
            with self.subTest(family=family), self.assertRaisesRegex(ValueError, "seul"):
                validate(REQUIRED, [(family, OBJECT), (family, second)],
                         None if family == "sites_zones" else "POINT(0 0)")

    def test_zone_uses_only_reference_geometry(self):
        self.assertIn("NULL", build_insert(REQUIRED, [("sites_zones", OBJECT)]))
        for geometry in ("POINT(0 0)", "LINESTRING(0 0,1 1)",
                         "POLYGON((0 0,1 0,1 1,0 0))", "MULTIPOINT((0 0),(1 1))"):
            with self.subTest(geometry=geometry), self.assertRaisesRegex(ValueError, "Supprimez-la explicitement"):
                build_insert(REQUIRED, [("sites_zones", OBJECT)], geometry)

    def test_rattachement_obligatoire_et_geometrie(self):
        values = dict(REQUIRED)
        point = "Point (700000 6600000)"
        with self.assertRaisesRegex(ValueError, "rattachement patrimonial"):
            build_insert(values, [], point)
        mixed = build_insert(values, [("ah_stockage", OBJECT)], point)
        self.assertIn("SRID=3950;Point (700000 6600000)", mixed)
        self.assertEqual(mixed.count("INSERT INTO"), 1)
        self.assertIn("NULL", build_insert(values, [("ah_stockage", OBJECT)]))
        with self.assertRaisesRegex(ValueError, "géométrie propre"):
            build_insert(values, [("cours_eau", OBJECT)])


if __name__ == "__main__":
    unittest.main()
