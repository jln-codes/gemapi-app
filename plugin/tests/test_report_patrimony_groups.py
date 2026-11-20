"""Native grouping controls and report grouping share the current contract."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from qgis.core import QgsApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gemapi_app.report_dialog import ReportDialog
from gemapi_app.report_data import PATRIMONY_GROUPS, normalized_filters
from gemapi_app.report_synthetic_portrait import terminal_groups


class PatrimonyGroupingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication.instance() or QgsApplication([], True)
        cls.app.initQgis()

    def test_menu_selection_hierarchy_and_report_kind_roundtrip(self):
        iface = type('Interface', (), {'mainWindow': lambda self: None})()
        with patch.object(ReportDialog, '_load_options'):
            dialog = ReportDialog(iface)
        dialog.reportKindCombo.setCurrentIndex(dialog.reportKindCombo.findData('synthetic'))
        for family in sorted(PATRIMONY_GROUPS):
            for combo in reversed(dialog.group_combos):
                combo.setCurrentIndex(0)
            first, second, third = dialog.group_combos
            first.setCurrentIndex(first.findData(family))
            self.assertEqual(dialog.filters()['groups'], (family,))
            second.setCurrentIndex(second.findData('year'))
            third.setCurrentIndex(third.findData('type'))
            self.assertEqual(dialog.filters()['groups'], (family, 'year', 'type'))
            dialog.reportKindCombo.setCurrentIndex(dialog.reportKindCombo.findData('detailed'))
            dialog.reportKindCombo.setCurrentIndex(dialog.reportKindCombo.findData('synthetic'))
            self.assertEqual(dialog.filters()['groups'], (family, 'year', 'type'))
            third.setCurrentIndex(third.findData(next(x for x in PATRIMONY_GROUPS if x != family)))
            self.assertIsNone(third.currentData())
        dialog.close()

    def test_all_families_group_by_uuid_and_reject_mixed_patrimonies(self):
        for family in PATRIMONY_GROUPS:
            rows = [dict(id=str(i), date_debut='2026-01-01', type='Travaux',
                         own_length=None, own_area=None,
                         parents=[dict(kind=family, id=str(i), nom='Même nom')])
                    for i in (1, 2)]
            groups = terminal_groups(rows + [rows[0]], {'groups': (family, 'year', 'type')})
            self.assertEqual(len(groups), 2)
            self.assertEqual(sum(len(items) for _, items in groups), 2)
            for other in PATRIMONY_GROUPS - {family}:
                with self.assertRaises(ValueError):
                    normalized_filters({'groups': (family, other)})


if __name__ == '__main__':
    unittest.main()
