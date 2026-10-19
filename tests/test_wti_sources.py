import unittest
from unittest.mock import patch
from datetime import date
from bs4 import BeautifulSoup
from scripts import update_usa as u

class WTISourcesTests(unittest.TestCase):
    def soup(self, label='2026 Oct-12 to Oct-16'):
        return BeautifulSoup('<h1>Cushing, OK WTI Spot Price FOB (Dollars per Barrel)</h1><table><tr><td>'+label+'</td><td>98.73</td><td>100.86</td><td>101.91</td><td></td><td>NA</td></tr></table>','html.parser')

    def test_missing_days_not_carried_forward(self):
        x=u.parse_wti_eia(self.soup(),today=date(2026,10,19))
        self.assertEqual((x['period'],x['value']),('2026-10-14',101.91))

    def test_week_crossing_year_and_future_prices(self):
        x=u.parse_wti_eia(self.soup('2025 Dec-29 to Jan- 2'),today=date(2025,12,30))
        self.assertEqual((x['period'],x['value']),('2025-12-30',100.86))

    def test_eia_success_does_not_query_fred(self):
        with patch.object(u,'page',return_value=self.soup()),patch.object(u,'commodity') as fallback:
            self.assertEqual(u.wti()['source'],'EIA · fuente directa')
            fallback.assert_not_called()

    def test_fred_backup_and_both_sources_fail(self):
        with patch.object(u,'page',side_effect=ValueError('unavailable')),patch.object(u,'commodity',return_value={'period':'2026-10-14','value':101.91}) as fallback:
            self.assertIn('fallback_note',u.wti())
            fallback.assert_called_once_with('wti')
        with patch.object(u,'page',side_effect=ValueError('unavailable')),patch.object(u,'commodity',side_effect=ValueError('unavailable')):
            with self.assertRaises(ValueError):u.wti()

    def test_older_eia_uses_backup_instead_of_regression(self):
        with patch.object(u,'page',return_value=self.soup()),patch.object(u,'commodity',return_value={'period':'2026-10-16','value':103}):
            self.assertEqual(u.wti({'period':'2026-10-15'})['period'],'2026-10-16')
