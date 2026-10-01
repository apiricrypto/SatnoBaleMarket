import unittest
from search_utils import normalize_search_text, query_terms, message_search_score

class SearchUtilsTests(unittest.TestCase):
    def test_multi_term_query_is_and_groups(self):
        groups=query_terms("باتری 15 گرووات")
        self.assertEqual(groups[0], ["باتری"])
        self.assertEqual(groups[1], ["15"])
        self.assertIn("growatt", groups[2])
        self.assertIn("گرووات", groups[2])

    def test_persian_digits_normalize(self):
        self.assertEqual(normalize_search_text("باتری ۱۵"), "باتری 15")

    def test_arabic_letters_normalize(self):
        self.assertEqual(normalize_search_text("باتري"), "باتری")


    def test_structured_fields_rank_higher(self):
        structured = {
            "models": '["SUN-80K-SG02HP3"]',
            "brands": '["Deye"]',
            "product_types": '["inverter"]',
            "locations": '["Ahvaz"]',
            "text": "موجودی جدید رسید",
        }
        text_only = {
            "models": "[]",
            "brands": "[]",
            "product_types": "[]",
            "locations": "[]",
            "text": "فروش اینورتر Deye مدل SUN-80K-SG02HP3",
        }
        self.assertGreater(
            message_search_score(structured, "Deye SUN-80K-SG02HP3"),
            message_search_score(text_only, "Deye SUN-80K-SG02HP3"),
        )

    def test_all_query_terms_must_match(self):
        row = {"brands": '["Growatt"]', "text": "اینورتر موجود است"}
        self.assertEqual(message_search_score(row, "Growatt باتری"), 0)

if __name__ == "__main__":
    unittest.main()
