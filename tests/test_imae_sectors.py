import unittest
from scripts.update_imae import parse

class IMAETests(unittest.TestCase):
    def test_monthly(self):
        p,v,s=parse("El indicador mensual de actividad económica (IMAE) correspondiente a octubre de 2026 registró una variación interanual de 5.4 %. El comportamiento exhibido por la economía dominicana durante el mes de octubre de 2026 estuvo explicado por construcción (15.6 %), manufactura local (6.8 %), manufactura de zonas francas (2.6 %) y agropecuario (1.3 %). La minería mostró una variación negativa de 13.6 %. La actividad construcción registró avances.")
        self.assertEqual((p,v),("2026-10",5.4))
        self.assertEqual(s["Minería"],-13.6)
        self.assertEqual(s["Construcción"],15.6)
    def test_cumulative_only_rejected(self):
        with self.assertRaises(ValueError):
            parse("IMAE creció en enero-septiembre 2026. Construcción (8.2 %).")
