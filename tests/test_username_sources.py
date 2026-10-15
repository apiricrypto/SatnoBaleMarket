import os
import tempfile
import unittest

import db
from username_sources import (
    canonical_username, enqueue_username, list_username_queue,
    accept_verified_resolution, remove_username,
)
from source_registry import list_sources


class UsernameSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_path = db.DB_PATH
        db.DB_PATH = os.path.join(self.temp.name, "username.db")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.old_path
        self.temp.cleanup()

    def test_public_username_formats(self):
        for value in ("@PartoNorPars", "https://ble.ir/partonorpars", "partonorpars"):
            self.assertEqual(canonical_username(value), "partonorpars")
        for bad in ("https://evil.com/partonorpars", "abc/other", "a", "123456"):
            with self.assertRaises(ValueError):
                canonical_username(bad)

    def test_queue_is_not_sync_registry(self):
        out = enqueue_username("@partonorpars", "Parto Noor Pars")
        self.assertEqual(out["status"], "pending")
        self.assertEqual(list_sources(), [])
        self.assertEqual(len(list_username_queue()), 1)

    def test_username_mismatch_must_not_register_peer(self):
        enqueue_username("partonorpars")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            accept_verified_resolution("partonorpars", "unrelated", 2, 123, "Wrong")
        self.assertEqual(list_sources(), [])

    def test_verified_username_promotes_exact_peer(self):
        enqueue_username("partonorpars", score=80)
        out = accept_verified_resolution("partonorpars", "@partonorpars", 2, 1234, "Parto")
        self.assertEqual(out["status"], "verified")
        self.assertEqual(list_sources()[0]["peer_id"], "1234")
        self.assertEqual(list_sources()[0]["score"], 80)
        remove_username("partonorpars")
        self.assertEqual(list_username_queue(), [])


if __name__ == "__main__":
    unittest.main()
