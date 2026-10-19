import unittest
from scripts.update_economy_news import parse_feed,build

FEED='''<rss><channel><item><title>Banco Central evalúa inflación dominicana - Diario Libre</title><source url="https://www.diariolibre.com">Diario Libre</source><pubDate>Mon, 19 Oct 2026 01:00:00 GMT</pubDate><link>https://news.google.com/rss/articles/test</link></item></channel></rss>'''

class EconomyNewsTests(unittest.TestCase):
    def test_rd_date_boundary(self):
        self.assertEqual(len(parse_feed(FEED,'2026-10-18')),1)
        self.assertEqual(parse_feed(FEED,'2026-10-19'),[])

    def test_publisher_and_link_validation(self):
        self.assertEqual(parse_feed(FEED.replace('www.diariolibre.com','diariolibre.com.evil.test'),'2026-10-18'),[])
        self.assertEqual(parse_feed(FEED.replace('https://news.google.com/rss/articles/test','javascript:alert(1)'),'2026-10-18'),[])

    def test_economist_search_does_not_claim_byline(self):
        x=parse_feed(FEED,'2026-10-18',economist='andy')[0]
        self.assertEqual(x['economist_match'],'search')
        self.assertEqual(x['economists'],['andy'])
        self.assertNotIn('author',x)
        self.assertEqual(parse_feed(FEED.replace('Banco Central evalúa inflación dominicana','Andy Dauhajre juega tenis'),'2026-10-18',economist='andy'),[])

    def test_economist_alias_and_topic_tags(self):
        x=parse_feed(FEED.replace('Banco Central evalúa inflación dominicana','Juan Ariel Jimenez analiza el ITBIS y la economía'),'2026-10-18')[0]
        self.assertIn('juan_ariel',x['economists'])
        self.assertIn('dgii',x['topics'])

    def test_dedup_merge_topics_and_keep_same_day_discoveries(self):
        a=parse_feed(FEED,'2026-10-18',topic='bcrd')[0]
        b=parse_feed(FEED,'2026-10-18',economist='andy')[0]
        first=build('2026-10-18',{'bcrd':([a],None),'economist_andy':([b],None)})
        self.assertEqual(len(first['items']),1)
        self.assertEqual(first['items'][0]['economists'],['andy'])
        second=build('2026-10-18',{'bcrd':([],None)},first)
        self.assertEqual(len(second['items']),1)
        next_day=build('2026-10-19',{'bcrd':([], 'offline')},first)
        self.assertEqual(next_day['items'],[])
        self.assertFalse(next_day['source_health']['bcrd']['ok'])
