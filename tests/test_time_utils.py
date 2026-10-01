import unittest
from time_utils import canonical_sent_at, parse_message_datetime

class TimeUtilsTests(unittest.TestCase):
    def test_unix_seconds(self):
        self.assertEqual(canonical_sent_at(1790769600), "2026-09-30T12:00:00Z")

    def test_unix_milliseconds(self):
        self.assertEqual(canonical_sent_at(1790769600000), "2026-09-30T08:00:00Z")

    def test_iso_utc(self):
        self.assertEqual(canonical_sent_at("2026-09-30T08:00:00Z"), "2026-09-30T08:00:00Z")

    def test_invalid_returns_none_for_parser(self):
        self.assertIsNone(parse_message_datetime("legacy"))

if __name__ == "__main__":
    unittest.main()
