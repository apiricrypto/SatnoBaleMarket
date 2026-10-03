import unittest

from sync_bale import classify_sync_health


class SyncHealthTests(unittest.TestCase):
    def test_zero_dialogs_with_active_sources_is_degraded(self):
        status, code, detail = classify_sync_health(0, 48, 0)
        self.assertEqual(status, "degraded")
        self.assertEqual(code, "bale_no_dialogs")
        self.assertIn("zero dialogs", detail)

    def test_dialogs_without_matching_sources_is_degraded(self):
        status, code, detail = classify_sync_health(12, 48, 0)
        self.assertEqual(status, "degraded")
        self.assertEqual(code, "bale_no_source_matches")
        self.assertIn("none matched", detail)

    def test_normal_sync_health_is_ok(self):
        self.assertEqual(classify_sync_health(12, 48, 5), ("ok", None, None))

    def test_empty_fresh_registry_is_not_false_alarm(self):
        self.assertEqual(classify_sync_health(0, 0, 0), ("ok", None, None))


if __name__ == "__main__":
    unittest.main()
