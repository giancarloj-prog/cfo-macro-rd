import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup
from scripts import update_usa as u

class PublicMarketTests(unittest.TestCase):
    def test_energy_keeps_observation_date_and_unit(self):
        soup=BeautifulSoup('Observations 2026-10-14: 4.844 Updated: Oct 15, 2026','html.parser')
        with patch.object(u,'page',return_value=soup):
            x=u.commodity('diesel')
        self.assertEqual((x['value'],x['period'],x['unit']),(4.844,'2026-10-14','usd_gallon'))

    def test_remittances_uses_accumulated_yoy(self):
        content='Entre enero y septiembre de 2026, las remesas recibidas alcanzaron la cifra de US$9,489.8 millones, lo que refleja un aumento de US$577.0 millones, un 6.5 %, respecto al mismo periodo del año 2025. En septiembre crecieron 8.2 %.'
        x=u.parse_remittances(content,'https://www.bancentral.gov.do/')
        self.assertEqual((x['value'],x['period'],x['yoy']),(9489.8,'2026-09',6.5))
        with self.assertRaises(ValueError):
            u.parse_remittances(content.replace('2025','2024'),'https://www.bancentral.gov.do/')

    def test_missing_price_is_not_zero(self):
        with patch.object(u,'page',return_value=BeautifulSoup('Observations 2026-10-14: .','html.parser')):
            with self.assertRaises(ValueError):u.commodity('gasoline')
