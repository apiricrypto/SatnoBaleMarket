import unittest

from classifier import analyze, normalize_text


class ClassifierNormalizationTests(unittest.TestCase):
    def test_digits_and_arabic_chars_are_normalized(self):
        self.assertEqual(normalize_text("نياز‌ فوری ۱۲۳٤٥"), "نیاز فوری 12345")

    def test_normalization_preserves_market_classification(self):
        result = analyze("نياز‌ فوری به ۳ عدد پنل در اهواز")
        self.assertEqual(result["category"], "buyer_demand")
        self.assertIn("3 عدد", result["quantities"])
        self.assertIn("اهواز", result["locations"])


if __name__ == "__main__":
    unittest.main()
