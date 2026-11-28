"""Reproducible, independent longitudinal selection cases in EPSG:3950."""

import sys
import unittest
from pathlib import Path

from qgis.core import QgsGeometry

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.patrimony_spatial import (ProjectionSettings, candidate_query,
                                              projected_fraction, resolve_watercourse)


RIVER = "MULTILINESTRING((0 0,1000 0))"
ONE = (("d1", 0.2, 0.4, True),)
TWO = ONE + (("d2", 0.6, 0.8, True),)


def resolve(wkt, levees=ONE, river=RIVER, settings=ProjectionSettings()):
    return resolve_watercourse(QgsGeometry.fromWkt(wkt), river, levees, settings)


class LongitudinalTests(unittest.TestCase):
    def test_point_projection_fraction(self):
        line = QgsGeometry.fromWkt("LINESTRING(0 0,1000 0)")
        point = QgsGeometry.fromWkt("POINT(300 80)")
        self.assertAlmostEqual(projected_fraction(line, point), 0.3)

    def test_independent_expected_cases(self):
        cases = (
            ("point sur section", "POINT(300 80)", ONE, (False, {"d1"})),
            ("point hors système", "POINT(100 80)", ONE, (True, set())),
            ("point proche limite", "POINT(199.5 80)", ONE, (True, {"d1"})),
            ("ligne parallèle", "LINESTRING(260 80,340 80)", ONE, (False, {"d1"})),
            ("ligne à cheval", "LINESTRING(150 80,250 80)", ONE, (True, {"d1"})),
            ("lignes disjointes", "MULTILINESTRING((250 80,300 80),(500 80,550 80))", ONE,
             (True, {"d1"})),
            ("polygone décalé", "POLYGON((260 60,340 60,340 120,260 120,260 60))", ONE,
             (False, {"d1"})),
            ("polygone à cheval", "POLYGON((170 60,230 60,230 120,170 120,170 60))", ONE,
             (True, {"d1"})),
            ("deux rives", "POLYGON((260 -100,340 -100,340 100,260 100,260 -100))", ONE,
             (False, {"d1"})),
            ("multipolygone disjoint", "MULTIPOLYGON(((260 60,300 60,300 90,260 90,260 60)),"
             "((500 60,540 60,540 90,500 90,500 60)))", ONE, (True, {"d1"})),
            ("méandre rapproché", "POINT(300 50)", ONE, (True, {"d1"})),
            ("plusieurs systèmes", "POINT(300 80)",
             (("d1", 0.2, 0.4, True), ("d2", 0.2, 0.4, True)), (False, {"d1", "d2"})),
            ("grand polygone", "POLYGON((0 0,10000 0,10000 10000,0 10000,0 0))", ONE,
             (True, {"d1"})),
            ("concave", "POLYGON((250 40,550 40,550 50,350 50,350 100,250 100,250 40))", ONE,
             (True, {"d1"})),
            ("trou", "POLYGON((180 40,420 40,420 120,180 120,180 40),"
             "(220 60,380 60,380 100,220 100,220 60))", ONE, (True, {"d1"})),
        )
        ambiguities = 0
        for name, wkt, levees, expected in cases:
            with self.subTest(name=name):
                river = "MULTILINESTRING((0 0,500 0,500 100,0 100))" if name == "méandre rapproché" else RIVER
                visible, candidates, ambiguous = resolve(wkt, levees, river)
                ambiguities += int(ambiguous)
                self.assertEqual((visible, candidates), expected)
        print(f"15 scénarios : 0 faux masquage, 0 candidat superflu, {ambiguities} ambiguïtés")

    def test_nearby_distinct_rivers_are_independent(self):
        first = resolve("POINT(300 50)")
        second = resolve("POINT(300 50)", (), "MULTILINESTRING((0 100,1000 100))")
        self.assertEqual(first[:2], (False, {"d1"}))
        self.assertEqual(second[:2], (True, set()))

    def test_very_detailed_geometry_falls_back_without_masking(self):
        vertices = ",".join(f"{250 + index / 100} {80 + index % 2}"
                            for index in range(6001))
        visible, levees, ambiguous = resolve(f"LINESTRING({vertices})")
        self.assertEqual((visible, levees, ambiguous), (True, {"d1"}, True))

    def test_ambiguous_data_and_thresholds_never_hide_river(self):
        self.assertEqual(resolve("POINT(300 80)", (("d1", 0.2, 0.4, False),))[:2],
                         (True, {"d1"}))
        self.assertEqual(resolve("POINT(300 80)", ONE, settings=ProjectionSettings(max_samples=1))[:2],
                         (False, {"d1"}))
        self.assertEqual(resolve("LINESTRING(260 80,340 80)", ONE,
                                 settings=ProjectionSettings(max_samples=1))[:2],
                         (True, {"d1"}))
        for options in ({"sample_step_m": 0}, {"boundary_tolerance_m": -1},
                        {"max_samples": 0}):
            with self.assertRaises(ValueError):
                ProjectionSettings(**options)

    def test_indexed_prefilter_covers_all_families(self):
        query = candidate_query("POINT(300 80)", 500)
        self.assertEqual(query.count("ST_DWithin("), 9)
        self.assertIn("gemapi.digues_reperes", query)
        self.assertIn("gemapi.ah_stockage", query)
        self.assertIn("gemapi.vegetation", query)
        self.assertIn("ST_GeomFromText(E'POINT(300 80)',3950)", query)
        with self.assertRaises(ValueError):
            candidate_query("POINT(0 0)", -1)

    def test_ah_sections_have_equal_priority_and_distinct_identity(self):
        first = (("ah_sections", "section-1"), .2, .4, True)
        second = (("ah_sections", "section-2"), .6, .8, True)
        self.assertEqual(resolve("POINT(300 80)", (first,))[:2],
                         (False, {("ah_sections", "section-1")}))
        self.assertEqual(resolve("POINT(700 80)", (first, second))[:2],
                         (False, {("ah_sections", "section-2")}))
        self.assertEqual(resolve("LINESTRING(250 80,750 80)", (first, second)),
                         (True, {("ah_sections", "section-1"), ("ah_sections", "section-2")}, True))
        concurrent = (("digues", "levee-1"), .2, .4, True)
        self.assertEqual(resolve("POINT(300 80)", (first, concurrent)),
                         (False, {("ah_sections", "section-1"), ("digues", "levee-1")}, True))

    def test_ah_line_polygon_boundaries_and_meanders(self):
        section = ((("ah_sections", "section-1"), .2, .4, True),)
        cases = (
            ("POINT(198 0)", (True, set())),
            ("POINT(200 0)", (True, {("ah_sections", "section-1")})),
            ("LINESTRING(260 80,340 80)", (False, {("ah_sections", "section-1")})),
            ("POLYGON((260 60,340 60,340 120,260 120,260 60))", (False, {("ah_sections", "section-1")})),
            ("POLYGON((170 60,230 60,230 120,170 120,170 60))", (True, {("ah_sections", "section-1")})),
        )
        for geometry, expected in cases:
            with self.subTest(geometry=geometry):
                self.assertEqual(resolve(geometry, section)[:2], expected)
        self.assertEqual(resolve("POINT(300 50)", section,
                                 "MULTILINESTRING((0 0,500 0,500 100,0 100))"),
                         (True, {("ah_sections", "section-1")}, True))


if __name__ == "__main__":
    unittest.main()
