from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from input_catalog import catalogue
from update_inputs import changes, matches_active, merge_series, parse_fred_csv, parse_gscpi, parse_shortages


class InputSignalTests(unittest.TestCase):
    def test_missing_comparable_month_is_not_replaced_with_nearest_observation(self):
        rows = [{'period': '2025-09', 'value': 100}, {'period': '2026-06', 'value': 110}, {'period': '2026-08', 'value': 120}, {'period': '2026-09', 'value': 132}]
        self.assertEqual(changes(rows), {'mom': 10.0, 'qoq': 20.0, 'yoy': 32.0})
        self.assertIsNone(changes([rows[0], rows[-1]])['mom'])

    def test_csv_rejects_wrong_series_and_ignores_future_or_missing_observation(self):
        text = 'observation_date,TEST\n2026-07-01,100\n2026-08-01,.\n2026-09-01,110\n2026-11-01,999\n'
        rows = parse_fred_csv(text, 'TEST', date(2026, 10, 16))
        self.assertEqual([x['period'] for x in rows], ['2026-07', '2026-09'])
        self.assertIsNone(changes(rows)['mom'])
        with self.assertRaises(ValueError):
            parse_fred_csv(text, 'OTHER')
        with self.assertRaises(ValueError):
            parse_fred_csv('observation_date,TEST\n2026-09-01,nan\n', 'TEST')

    def test_gscpi_uses_latest_available_vintage_and_retains_negative_values(self):
        text = 'Date,Sep-26,Oct-26,Nov-26\n31-Aug-2026,1.1,-0.5,9\n30-Sep-2026,,0.2,9\n31-Oct-2026,,,9\n,,,\n'
        rows = parse_gscpi(text, date(2026, 10, 16))
        self.assertEqual(rows, [{'period': '2026-08', 'value': -0.5}, {'period': '2026-09', 'value': 0.2}])

    def test_failed_check_does_not_redate_cached_prices(self):
        old = {'value': 100, 'period': '2026-08', 'verified_at': 'old'}
        series, health = merge_series({'ethanol': old}, {'ethanol': (None, 'failure')}, 'new')
        self.assertEqual(series['ethanol']['verified_at'], 'old')
        self.assertFalse(health['ethanol']['ok'])

    def test_salt_and_combination_mismatches_do_not_create_false_shortages(self):
        actives = {x['name']: x for x in catalogue()['actives']}
        combo = {'generic_name': 'Sacubitril and Valsartan Tablets'}
        self.assertFalse(matches_active(combo, actives['Valsartán']))
        self.assertTrue(matches_active(combo, actives['Sacubitril / valsartán']))
        self.assertFalse(matches_active({'generic_name': 'Fosfomycin Tromethamine'}, actives['Fosfomicina cálcica']))

    def test_only_current_fda_presentations_count_not_resolved(self):
        rows = [
            {'generic_name': 'Valsartan Tablets', 'status': 'Resolved', 'presentation': '100 mg'},
            {'generic_name': 'Valsartan Tablets', 'status': 'Current', 'presentation': '200 mg', 'availability': 'Available', 'company_name': 'Public FDA entity'},
            {'generic_name': 'Sacubitril and Valsartan Tablets', 'status': 'Current', 'presentation': 'combo'},
        ]
        results = {x['name']: x for x in parse_shortages(rows, catalogue())}
        self.assertEqual(results['Valsartán']['count'], 1)
        self.assertEqual(results['Valsartán']['presentations'][0]['availability'], 'Available')
        self.assertEqual(results['Sacubitril / valsartán']['count'], 1)


if __name__ == '__main__':
    unittest.main()
