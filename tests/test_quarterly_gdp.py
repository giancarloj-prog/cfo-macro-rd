import unittest
from unittest.mock import patch
from scripts import update_gdp as g

class Sheet:
    def __init__(self,rows):self.rows=rows
    def iter_rows(self,values_only=False):return iter(self.rows)

def workbook(n=10):
    periods=[f'{2024+i//4}-Q{i%4+1}' for i in range(n)]
    years=[2024+i//4 if i%4==0 else None for i in range(n)]
    quarters=[['E-M','A-J','J-S','O-D'][i%4] for i in range(n)]
    values={'Producto Interno Bruto':[100+i*2 for i in range(n)],'Construcción':[90+i*3+(i%4)*2 for i in range(n)]}
    index=[['INDICE DE VOLUMEN POR ACTIVIDAD ECONOMICA']+years,[None]+quarters,[None]*(n+1)]
    rates=[['TASAS DE CRECIMIENTO POR ACTIVIDAD ECONOMICA']+years,[None]+quarters,[None]*(n+1)]
    accum=[['TASAS DE CRECIMIENTO POR ACTIVIDAD ECONOMICA']+years,[None]+quarters,[None]*(n+1)]
    for name,v in values.items():
        index.append([name]+v)
        rates.append([name]+[None if i<4 else (v[i]/v[i-4]-1)*100 for i in range(n)])
        totals=[]
        for i in range(n):
            start=i//4*4
            totals.append(None if i<4 else (sum(v[start:i+1])/sum(v[start-4:i-3])-1)*100)
        accum.append([name]+totals)
    return {'PIBK_Trim':Sheet(index+rates),'PIBK_Trim_Acum':Sheet(accum)},values

class QuarterlyGDPTests(unittest.TestCase):
    def parse(self,wb):
        with patch.object(g,'PRINCIPAL',['Producto Interno Bruto','Construcción']):return g.parse_workbook(wb)

    def test_last_four_quarters_and_rolling_growth(self):
        wb,values=workbook();d=self.parse(wb)
        self.assertEqual(d['periods'],['2025-Q3','2025-Q4','2026-Q1','2026-Q2'])
        construction=next(x for x in d['series'] if x['id']=='construccion');v=values['Construcción']
        self.assertAlmostEqual(construction['rolling_12m_yoy'],(sum(v[-4:])/sum(v[-8:-4])-1)*100)
        self.assertAlmostEqual(construction['ytd_yoy'],(sum(v[8:10])/sum(v[4:6])-1)*100)

    def test_new_quarter_moves_window(self):
        wb,_=workbook(11);d=self.parse(wb)
        self.assertEqual(d['periods'],['2025-Q4','2026-Q1','2026-Q2','2026-Q3'])
        self.assertEqual(d['ytd_period']['through_quarter'],3)

    def test_rejects_inconsistent_official_rate(self):
        wb,_=workbook();wb['PIBK_Trim'].rows[-1][-1]+=1
        with self.assertRaisesRegex(ValueError,'No concuerda la tasa oficial'):self.parse(wb)

    def test_missing_sector_is_not_silently_dropped(self):
        wb,_=workbook()
        with patch.object(g,'PRINCIPAL',['Producto Interno Bruto','Construcción','Salud']):
            with self.assertRaisesRegex(ValueError,'Faltan actividades'):g.parse_workbook(wb)

if __name__=='__main__':unittest.main()
