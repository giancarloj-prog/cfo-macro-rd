import unittest
from scripts.update_news import parse_feed, build

FEED='''<rss><channel><item><title>Nuevo medicamento aprobado - Diario Libre</title><source url="https://www.diariolibre.com">Diario Libre</source><pubDate>Fri, 16 Oct 2026 01:00:00 GMT</pubDate><link>https://news.google.com/rss/articles/test</link></item></channel></rss>'''

class DailyNewsTests(unittest.TestCase):
    def test_date_uses_dominican_day(self):
        self.assertEqual(len(parse_feed(FEED,'rd','2026-10-15')),1)
        self.assertEqual(parse_feed(FEED,'rd','2026-10-16'),[])

    def test_untrusted_publisher_and_link_are_rejected(self):
        self.assertEqual(parse_feed(FEED.replace('www.diariolibre.com','diariolibre.com.evil.example'),'rd','2026-10-15'),[])
        self.assertEqual(parse_feed(FEED.replace('https://news.google.com/rss/articles/test','javascript:alert(1)'),'rd','2026-10-15'),[])

    def test_duplicate_regions_merge_one_headline(self):
        item=parse_feed(FEED,'rd','2026-10-15')[0]
        output=build('2026-10-15',{'rd':([item],None),'global':([dict(item,regions=['global'])],None)})
        self.assertEqual(len(output['items']),1)
        self.assertEqual(set(output['items'][0]['regions']),{'rd','global'})

    def test_new_day_clears_prior_items_even_when_fetch_fails(self):
        previous=build('2026-10-15',{'rd':(parse_feed(FEED,'rd','2026-10-15'),None)})
        output=build('2026-10-16',{'rd':([], 'Source offline')},previous)
        self.assertEqual(output['items'],[])
        self.assertFalse(output['source_health']['rd']['ok'])

    def test_same_day_failure_retains_prior_headlines(self):
        previous=build('2026-10-15',{'rd':(parse_feed(FEED,'rd','2026-10-15'),None)})
        output=build('2026-10-15',{'rd':([], 'Source offline')},previous)
        self.assertEqual(output['items'],previous['items'])

if __name__=='__main__':unittest.main()
