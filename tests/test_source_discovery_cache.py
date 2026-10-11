import os
import tempfile
import unittest
from types import SimpleNamespace

import db
from sync_bale import cache_dialog_candidate


class SourceDiscoveryCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = os.path.join(self.tmp.name, "source-cache-test.db")
        db.init_db()

    def tearDown(self):
        self.tmp.cleanup()

    def test_dialog_candidate_is_cached_and_refreshed(self):
        dialog = SimpleNamespace(
            title="پرتو نور پارس",
            peer=SimpleNamespace(type=2, id=987654),
        )
        cache_dialog_candidate(dialog)
        with db.connect() as con:
            row = con.execute(
                "SELECT * FROM source_discovery_cache WHERE peer_type=? AND peer_id=?",
                ("2", "987654"),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "پرتو نور پارس")

        dialog.title = "پرتو نور پارس - بازار"
        cache_dialog_candidate(dialog)
        with db.connect() as con:
            row = con.execute(
                "SELECT * FROM source_discovery_cache WHERE peer_type=? AND peer_id=?",
                ("2", "987654"),
            ).fetchone()
        self.assertEqual(row["title"], "پرتو نور پارس - بازار")


if __name__ == "__main__":
    unittest.main()
