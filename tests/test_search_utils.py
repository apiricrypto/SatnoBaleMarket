import unittest
from search_utils import normalize_search_text, query_terms

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

if __name__ == "__main__":
    unittest.main()
