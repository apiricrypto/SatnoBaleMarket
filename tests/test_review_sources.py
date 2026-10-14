import os
import tempfile
import unittest

import db
from lead_review import save_review
from source_registry import add_source, delete_source, delete_sources_bulk, list_sources, update_source


class ReviewAndSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = os.path.join(self.tmp.name, "ops-test.db")
        db.init_db()
        with db.connect() as con:
            self.message_id = con.execute(
                "INSERT INTO messages(text,category) VALUES(?,?)",
                ("استعلام اینورتر 80 کیلووات", "inquiry_project"),
            ).lastrowid

    def tearDown(self):
        self.tmp.cleanup()

    def test_review_requires_paired_estimate(self):
        with self.assertRaisesRegex(ValueError, "set together"):
            save_review(
                self.message_id,
                "sales1",
                {"review_status": "selected", "estimated_amount": 1000},
            )

    def test_review_persists_auditable_selection(self):
        row = save_review(
            self.message_id,
            "sales1",
            {
                "review_status": "selected",
                "reviewed_category": "inquiry_project",
                "product": "inverter",
                "brand": "deye",
                "estimated_amount": 1000000,
                "estimated_currency": "IRR",
                "priority": "high",
            },
        )
        self.assertEqual(row["review_status"], "selected")
        self.assertEqual(row["reviewed_by"], "sales1")
        self.assertTrue(row["reviewed_at"])
        self.assertEqual(row["estimated_currency"], "IRR")

    def test_manual_source_add_edit_delete(self):
        row = add_source(2, 12345, "بازار تست", score=10, matched_terms="solar", enabled=True)
        self.assertEqual(row["source_key"], "bale:2:12345")
        self.assertEqual(len(list_sources()), 1)

        edited = update_source(
            row["source_key"],
            title="بازار تست ویرایش شده",
            score=20,
            matched_terms="solar,pv",
            enabled=False,
        )
        self.assertEqual(edited["score"], 20)
        self.assertEqual(edited["enabled"], 0)

        with db.connect() as con:
            con.execute(
                "INSERT INTO sync_state(source_key,cursor) VALUES(?,?)",
                (row["source_key"], "cursor-1"),
            )
        delete_source(row["source_key"])
        self.assertEqual(list_sources(), [])
        with db.connect() as con:
            self.assertIsNone(
                con.execute(
                    "SELECT 1 FROM sync_state WHERE source_key=?",
                    (row["source_key"],),
                ).fetchone()
            )

    def test_bulk_delete_is_exact_and_preserves_messages(self):
        a = add_source(2, 101, "remove A")
        b = add_source(2, 102, "remove B")
        keep = add_source(2, 103, "keep")
        with db.connect() as con:
            for key in (a["source_key"], b["source_key"], keep["source_key"]):
                con.execute("INSERT INTO sync_state(source_key,cursor) VALUES (?,?)", (key, "cursor"))
        result = delete_sources_bulk([
            {"peer_type": 2, "peer_id": 101},
            {"peer_type": 2, "peer_id": 102},
        ])
        self.assertEqual(result["deleted"], 2)
        self.assertEqual([row["source_key"] for row in list_sources()], [keep["source_key"]])
        with db.connect() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM messages").fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT count(*) FROM sync_state").fetchone()[0], 1)

    def test_bulk_delete_rolls_back_if_any_source_missing(self):
        add_source(2, 201, "preserve")
        with self.assertRaisesRegex(ValueError, "source not found"):
            delete_sources_bulk([
                {"peer_type": 2, "peer_id": 201},
                {"peer_type": 2, "peer_id": 999},
            ])
        self.assertEqual(len(list_sources()), 1)

    def test_bulk_delete_rejects_duplicates_and_empty(self):
        add_source(2, 301, "preserve")
        for items in ([], [
            {"peer_type": 2, "peer_id": 301},
            {"peer_type": 2, "peer_id": 301},
        ]):
            with self.assertRaises(ValueError):
                delete_sources_bulk(items)
        self.assertEqual(len(list_sources()), 1)

    def test_duplicate_source_is_rejected(self):
        add_source(2, 555, "A")
        with self.assertRaisesRegex(ValueError, "already exists"):
            add_source(2, 555, "B")


if __name__ == "__main__":
    unittest.main()
