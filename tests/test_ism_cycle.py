import unittest
from unittest.mock import Mock, patch
from scripts import update_usa as usa
from scripts import update_economic_cycle as cycle


class SourceRegressionTests(unittest.TestCase):
    def test_utf8_wire_release_survives_incorrect_http_encoding(self):
        html = '''<html><head><meta charset="utf-8"></head><body>
        <h1>Manufacturing PMI® at 54.5%; September 2026 ISM® Manufacturing PMI® Report</h1>
        News provided by Institute for Supply Management</body></html>'''
        response = Mock(content=html.encode('utf-8'), text=html.encode('utf-8').decode('latin-1'),
                        url='https://www.prnewswire.com/news-releases/report.html')
        original_page = usa.page
        def fetch(url):
            if url.startswith(usa.ISM):
                raise ValueError('Interactive access required')
            return original_page(url)
        with patch.object(usa.requests, 'get', return_value=response), patch.object(usa, 'page', side_effect=fetch):
            result = usa.pmi('manufacturing', {'url': response.url})
        self.assertEqual((result['value'], result['period']), (54.5, '2026-09'))

    def test_flat_leading_index_and_changed_other_indexes(self):
        html = '''Latest Press Release Updated: Thursday, October 22, 2026
        The Conference Board Leading Economic Index® (LEI) for the US was unchanged in September 2026 at 99.6 (2016=100), after a decline of 0.1% in August.
        The Conference Board Coincident Economic Index® (CEI) for the US increased by 0.3% in September 2026 to 115.3.
        The Conference Board Lagging Economic Index® (LAG) for the US increased by 0.5% in September 2026 to 121.1.'''
        found, published, _, _ = cycle.parse(html)
        self.assertEqual(published, '2026-10-22')
        self.assertEqual((found['leading']['value'], found['leading']['mom'], found['leading']['period']), (99.6, 0.0, '2026-09'))
        self.assertEqual(found['coincident']['mom'], 0.3)
        self.assertEqual(found['lagging']['mom'], 0.5)

    def test_flat_index_requires_month_and_level(self):
        found, _, _, _ = cycle.parse('Latest Press Release Updated: Thursday, October 22, 2026 The Conference Board Leading Economic Index® (LEI) for the US was flat.')
        self.assertEqual(found, {})
