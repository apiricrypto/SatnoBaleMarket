import unittest

from display_utils import format_tehran_jalali, gregorian_to_jalali, jalali_to_gregorian, normalize_datetime_filter


class DisplayUtilsTests(unittest.TestCase):
    def test_known_jalali_date(self):
        self.assertEqual(gregorian_to_jalali(2026, 9, 30), (1405, 7, 8))

    def test_utc_is_displayed_in_tehran_time(self):
        self.assertEqual(format_tehran_jalali("2026-09-30T08:00:00Z"), "1405/07/08 11:30")

    def test_plain_datetime_is_preserved_as_local_clock(self):
        self.assertEqual(format_tehran_jalali("2026-09-30T12:45:00"), "1405/07/08 12:45")

    def test_invalid_value_falls_back(self):
        self.assertEqual(format_tehran_jalali("legacy-date"), "legacy-date")

    def test_date_filter_expands_day_bounds(self):
        self.assertEqual(normalize_datetime_filter("2026-09-30"), "2026-09-29T20:30:00")
        self.assertEqual(normalize_datetime_filter("2026-09-30", end=True), "2026-09-30T20:29:59")

    def test_jalali_filter_converts_to_gregorian(self):
        self.assertEqual(jalali_to_gregorian(1405, 7, 8), (2026, 9, 30))
        self.assertEqual(normalize_datetime_filter("۱۴۰۵/۰۷/۰۸"), "2026-09-29T20:30:00")
        self.assertEqual(normalize_datetime_filter("1405/07/08", end=True), "2026-09-30T20:29:59")


if __name__ == "__main__":
    unittest.main()
