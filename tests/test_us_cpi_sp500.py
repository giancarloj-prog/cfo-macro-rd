import unittest
from unittest.mock import patch,Mock
from bs4 import BeautifulSoup
from scripts import update_usa as u

class USAAdditionsTests(unittest.TestCase):
    def test_cpi_uses_general_yoy_not_monthly_or_core(self):
        soup=BeautifulSoup('CONSUMER PRICE INDEX - SEPTEMBER 2026 The CPI-U increased 0.6 percent. Over the last 12 months, the all items index increased 3.7 percent before seasonal adjustment. All items less food and energy rose 2.6 percent.','html.parser')
        with patch.object(u,'page',return_value=soup):x=u.inflation_us()
        self.assertEqual((x['value'],x['period'],x['unit']),(3.7,'2026-09','percent'))

    def test_negative_inflation(self):
        soup=BeautifulSoup('CONSUMER PRICE INDEX - MAY 2026 Over the last 12 months, the all items index decreased 0.4 percent.','html.parser')
        with patch.object(u,'page',return_value=soup):self.assertEqual(u.inflation_us()['value'],-.4)

    def test_sp500_comma_and_observation_date(self):
        soup=BeautifulSoup('S&amp;P 500 Observations 2026-10-15: 7,744.06 Updated: Oct 16, 2026','html.parser')
        with patch.object(u,'page',return_value=soup):x=u.sp500()
        self.assertEqual((x['value'],x['period'],x['unit']),(7744.06,'2026-10-15','index_points'))

    def test_sp500_missing_observation_is_rejected(self):
        with patch.object(u,'page',return_value=BeautifulSoup('Updated: Oct 16, 2026','html.parser')):
            with self.assertRaises(ValueError):u.sp500()

if __name__=='__main__':unittest.main()
