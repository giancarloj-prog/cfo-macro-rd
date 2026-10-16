import unittest
from unittest.mock import patch,Mock
from datetime import datetime,timezone
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
        with patch.object(u,'page',return_value=BeautifulSoup('Updated: Oct 16, 2026','html.parser')),patch.object(u,'sp500_yahoo',side_effect=ValueError('Unavailable')):
            with self.assertRaises(ValueError):u.sp500()

    def test_cpi_api_skips_unpublished_months_and_annual_average(self):
        r=Mock();r.json.return_value={'status':'REQUEST_SUCCEEDED','Results':{'series':[{'seriesID':'CUUR0000SA0','data':[{'year':'2026','period':'M10','value':'-'},{'year':'2026','period':'M13','value':'9999'},{'year':'2026','period':'M09','value':'103.7'},{'year':'2025','period':'M09','value':'100'}]}]}}
        with patch.object(u,'page',side_effect=ValueError('Unavailable')),patch.object(u.requests,'get',return_value=r):x=u.inflation_us()
        self.assertEqual((x['value'],x['period']),(3.7,'2026-09'))

    def test_fallback_discards_current_intraday_candle(self):
        ts=lambda date:int(datetime.fromisoformat(date).timestamp())
        response=Mock();response.json.return_value={'chart':{'result':[{'meta':{'symbol':'^GSPC','currentTradingPeriod':{'regular':{'end':ts('2026-10-16T20:00:00+00:00')}}},'timestamp':[ts('2026-10-15T13:30:00+00:00'),ts('2026-10-16T13:30:00+00:00')],'indicators':{'quote':[{'close':[7744.06005859375,7747.20]}]}}]}}
        with patch.object(u.requests,'get',return_value=response):
            during=u.sp500_yahoo(datetime(2026,10,16,15,tzinfo=timezone.utc))
            after=u.sp500_yahoo(datetime(2026,10,16,21,tzinfo=timezone.utc))
        self.assertEqual((during['value'],during['period']),(7744.06,'2026-10-15'))
        self.assertEqual((after['value'],after['period']),(7747.2,'2026-10-16'))

if __name__=='__main__':unittest.main()
