import unittest

from classifier import analyze, normalize_text


class ClassifierMarketV51Tests(unittest.TestCase):
    def test_normalization_digits_and_arabic_chars(self):
        self.assertEqual(normalize_text("نياز ۱۲۳٤ كالا"), "نیاز 1234 کالا")

    def test_arabic_decimal_and_thousands_separators(self):
        self.assertEqual(normalize_text("۱۲٫۵ و ۱٬۰۰۰"), "12.5 و 1,000")

    def test_zero_width_and_direction_marks(self):
        self.assertEqual(normalize_text("نیاز\u200cفوری\u200f پنل"), "نیاز فوری پنل")

    def test_inquiry_category(self):
        self.assertEqual(analyze("استعلام قیمت 20 عدد پنل")["category"], "inquiry_project")

    def test_buyer_category(self):
        self.assertEqual(analyze("نیاز فوری به 10 دستگاه اینورتر")["category"], "buyer_demand")

    def test_stock_beats_low_signal_collaboration_price(self):
        self.assertEqual(
            analyze("موجودی اینورتر گرووات 12 کیلووات قیمت همکاری")["category"],
            "stock_availability",
        )

    def test_supplier_category(self):
        self.assertEqual(analyze("فروشنده رسمی پنل خورشیدی")["category"], "supplier_seller")

    def test_brand_aliases_are_canonical(self):
        self.assertEqual(analyze("پنل ترینا و Growatt")["brands"], ["trina", "growatt"])

    def test_product_types(self):
        self.assertIn("connector", analyze("MC4 اصل موجود است")["product_types"])
        self.assertIn("battery", analyze("باتری LiFePO4 موجود است")["product_types"])

    def test_space_delimited_model(self):
        self.assertIn("SPF 6000 ES", analyze("Growatt SPF 6000 ES موجودی")["models"])

    def test_compact_suffix_model(self):
        self.assertIn("SPE 12000ES", analyze("Growatt SPE 12000ES")["models"])

    def test_hyphenated_model(self):
        self.assertIn("SE-F12", analyze("باتری Deye مدل SE-F12")["models"])

    def test_complex_model(self):
        self.assertIn("SUN-12K-SG04LP3", analyze("SUN-12K-SG04LP3 موجود است")["models"])

    def test_brand_plus_power_is_not_model(self):
        self.assertEqual(analyze("پنل Trina 720W")["models"], [])

    def test_power_with_persian_digits(self):
        result = analyze("پنل ۷۲۰ وات موجود است")
        self.assertIn("720 وات", result["power_values"])

    def test_energy_capacity(self):
        result = analyze("باتری 16kWh موجود است")
        self.assertIn("16kwh", [x.lower() for x in result["energy_values"]])

    def test_quantity_with_persian_digits(self):
        self.assertIn("30 عدد", analyze("نیاز فوری ۳۰ عدد پنل")["quantities"])

    def test_million_toman_price(self):
        self.assertEqual(
            analyze("قیمت ۱۲.۵ میلیون تومان")["price_values"],
            ["12.5 میلیون تومان"],
        )

    def test_plain_rial_price(self):
        self.assertEqual(
            analyze("قیمت 120,000,000 ریال")["price_values"],
            ["120,000,000 ریال"],
        )

    def test_khuzestan_city_expansion(self):
        self.assertIn("رامهرمز", analyze("موجودی کابل در رامهرمز")["locations"])

    def test_sample_message_stock(self):
        result = analyze("موجودی پنل Trina 720W تعداد 100 عدد آماده تحویل اهواز. تماس 09123456789")
        self.assertEqual(result["category"], "stock_availability")
        self.assertEqual(result["brands"], ["trina"])
        self.assertIn("720w", [x.lower().replace(" ", "") for x in result["power_values"]])
        self.assertIn("100 عدد", result["quantities"])
        self.assertIn("اهواز", result["locations"])

    def test_sample_message_inquiry(self):
        result = analyze("برای پروژه خوزستان استعلام قیمت اینورتر Growatt 20kW سه فاز داریم.")
        self.assertEqual(result["category"], "inquiry_project")
        self.assertEqual(result["brands"], ["growatt"])
        self.assertIn("inverter", result["product_types"])
        self.assertIn("خوزستان", result["locations"])


if __name__ == "__main__":
    unittest.main()
