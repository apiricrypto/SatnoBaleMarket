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

    def test_successful_run_finalizes_timestamp(self):
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as temp:
            old_db = db.DB_PATH
            db.DB_PATH = os.path.join(temp, "ok.db")
            try:
                db.init_db()
                with db.connect() as con:
                    run_id = con.execute(
                        "INSERT INTO sync_runs(started_at) VALUES(?)",
                        ("2026-10-15T00:00:00Z",),
                    ).lastrowid
                # A successful worker requires a time formatter in its own scope.
                # Its outer caller's imports do not supply this global.
                with patch.object(sync_bale, "BaleClient") as mock_client:
                    async def enter():
                        class EmptyClient:
                            async def get_messages(self, *args, **kwargs):
                                return []
                        return EmptyClient()
                    mock_client.return_value.__aenter__.side_effect = enter
                    mock_client.return_value.__aexit__.return_value = False
                    with patch.dict(os.environ, {"BALE_TOKEN": "test-only"}):
                        asyncio.run(sync_bale._sync_once(run_id))
                with db.connect() as con:
                    row = con.execute(
                        "SELECT status,finished_at FROM sync_runs WHERE id=?", (run_id,)
                    ).fetchone()
                self.assertEqual(row["status"], "degraded")
                self.assertIsNotNone(row["finished_at"])
            finally:
                db.DB_PATH = old_db

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
