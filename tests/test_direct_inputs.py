from datetime import date
from pathlib import Path
import sys
import unittest
from openpyxl import Workbook
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_inputs import parse_bls,parse_worldbank,changes

class DirectInputTests(unittest.TestCase):
    def test_bls_exact_series_months_revisions_and_missing_data(self):
        payload={'status':'REQUEST_SUCCEEDED','Results':{'series':[{'seriesID':'WPU0662','data':[
            {'year':'2026','period':'M09','value':'278.148'},
            {'year':'2026','period':'M08','value':'283.037'},
            {'year':'2026','period':'M07','value':'-'},
            {'year':'2026','period':'M13','value':'999'},
            {'year':'2026','period':'M11','value':'999'}]}]}}
        h=parse_bls(payload,'WPU0662',date(2026,10,19))
        self.assertEqual(h[-1],{'period':'2026-09','value':278.148})
        self.assertEqual(len(h),2)
        self.assertIsNone(changes(h)['yoy'])
        with self.assertRaises(ValueError):parse_bls(payload,'OTHER')

    def workbook(self):
        w=Workbook();s=w.active;s.title='Monthly Prices'
        s.append(['Updated on October 02, 2026'])
        s.append([None,'Sugar, world','Aluminum'])
        s.append([None,'($/kg)','($/mt)'])
        s.append(['2025M09',.5,3000])
        s.append(['2026M08',.38,3251])
        s.append(['2026M09',.41,3283])
        s.append(['2026M11',99,9999])
        return w

    def test_worldbank_headers_and_units_not_fixed_column_positions(self):
        h=parse_worldbank(self.workbook(),date(2026,10,19))
        self.assertEqual(h['aluminum'][-1],{'period':'2026-09','value':3283})
        self.assertAlmostEqual(h['sugar'][-1]['value'],.41*100*.45359237,places=5)
        self.assertAlmostEqual(changes(h['sugar'])['yoy'],-18)
        self.assertEqual(len(h['sugar']),3)

    def test_worldbank_unknown_unit_rejected(self):
        w=self.workbook();w['Monthly Prices']['B3']='cents/lb'
        with self.assertRaises(ValueError):parse_worldbank(w)
