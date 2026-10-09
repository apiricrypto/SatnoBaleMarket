import unittest

from search_utils import message_search_score, normalize_search_text


class UserFriendlySearchTests(unittest.TestCase):
    def test_pasted_exact_product_title_matches_across_persian_variants(self):
        row = {
            "text": "موجودی اینورتر هیبریدی سه‌فاز Deye مدل SUN-80K-SG02HP3",
            "models": '["SUN-80K-SG02HP3"]',
            "brands": '["deye"]',
            "product_types": '["inverter"]',
            "locations": '["اهواز"]',
            "power_values": '["80 kw"]',
            "energy_values": "[]",
            "price_values": "[]",
            "currency_values": "[]",
            "sender_username": "",
            "sender_name": "",
            "chat_name": "بازار سولار",
            "category": "stock_availability",
        }
        query = "اینورتر هیبریدی سه فاز Deye مدل SUN 80K SG02HP3"
        self.assertGreater(message_search_score(row, query), 0)

    def test_arabic_persian_characters_and_digits_normalize(self):
        self.assertEqual(
            normalize_search_text("اينورتر ۸۰-كيلووات"),
            normalize_search_text("اینورتر 80 کیلووات"),
        )

    def test_unrelated_query_does_not_match(self):
        row = {
            "text": "فروش پنل خورشیدی ترینا 620 وات",
            "models": "",
            "brands": '["trina"]',
            "product_types": '["panel"]',
            "locations": "",
            "power_values": '["620 w"]',
            "energy_values": "",
            "price_values": "",
            "currency_values": "",
            "sender_username": "",
            "sender_name": "",
            "chat_name": "",
            "category": "supplier_seller",
        }
        self.assertEqual(message_search_score(row, "باتری لیتیوم 16 کیلووات ساعت"), 0)


if __name__ == "__main__":
    unittest.main()
