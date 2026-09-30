import unittest
from source_discovery import score_source,is_market_source

class SourceDiscoveryTests(unittest.TestCase):
    def test_title_match_scores_high(self):
        score,_=score_source("بازار پنل خورشیدی",[])
        self.assertGreaterEqual(score,4)

    def test_content_discovers_generic_title(self):
        texts=["موجودی اینورتر Growatt 10kw","قیمت باتری لیتیوم امروز"]
        self.assertTrue(is_market_source("بازار برق ایران",texts))

    def test_unrelated_source_stays_out(self):
        self.assertFalse(is_market_source("گفتگوی عمومی",["سلام دوستان","جلسه فردا ساعت ده"]))

if __name__=="__main__":
    unittest.main()
