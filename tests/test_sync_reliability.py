import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

import db
import sync_bale
from sync_guard import SyncAlreadyRunning, SyncFileLock


class SyncReliabilityTests(unittest.TestCase):
    def test_second_lock_is_rejected_and_released(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "sync.lock")
            with SyncFileLock(path):
                with self.assertRaises(SyncAlreadyRunning):
                    with SyncFileLock(path):
                        pass
            with SyncFileLock(path):
                pass

    def test_failed_run_is_closed_on_exception(self):
        with tempfile.TemporaryDirectory() as temp:
            old_db = db.DB_PATH
            db.DB_PATH = os.path.join(temp, "test.db")
            lock_path = os.path.join(temp, "test.lock")
            try:
                with patch.dict(os.environ, {"DATABASE_PATH": db.DB_PATH, "BALE_SYNC_LOCK_FILE": lock_path}):
                    with patch.object(sync_bale, "_sync_once", side_effect=RuntimeError("simulated failure")):
                        with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                            asyncio.run(sync_bale.main())
                with db.connect() as con:
                    run = con.execute(
                        "SELECT status,finished_at,error_code FROM sync_runs ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                self.assertEqual(run["status"], "failed")
                self.assertIsNotNone(run["finished_at"])
                self.assertEqual(run["error_code"], "RuntimeError")
            finally:
                db.DB_PATH = old_db


if __name__ == "__main__":
    unittest.main()
