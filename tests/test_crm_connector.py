import os
import tempfile
import unittest

import db
from crm_connector import build_lead_payload, queue_lead


class CRMConnectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = os.path.join(self.tmp.name, "crm-test.db")
        db.init_db()
        with db.connect() as con:
            self.message_id = con.execute(
                """
                INSERT INTO messages
                (external_id,chat_name,sender_name,sender_id,sender_username,sender_link,text,sent_at,category,brands,product_types,models,locations)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "42","بازار سولار","فروشنده","1001","seller","https://ble.ir/seller",
                    "موجودی اینورتر Deye 80kW","2026-10-01T10:00:00+00:00","stock_availability",
                    '["Deye"]','["inverter"]','["SUN-80K"]','["اهواز"]'
                ),
            ).lastrowid

    def tearDown(self):
        self.tmp.cleanup()

    def test_contract_contains_provenance_and_idempotency(self):
        with db.connect() as con:
            row = dict(con.execute("SELECT * FROM messages WHERE id=?", (self.message_id,)).fetchone())
        payload = build_lead_payload(row)
        self.assertEqual(payload["contract_version"], "satno.lead.v1")
        self.assertEqual(payload["source"], "bale-market")
        self.assertEqual(payload["brands"], ["Deye"])
        self.assertEqual(payload["sender"]["username"], "seller")
        self.assertEqual(len(payload["idempotency_key"]), 64)

    def test_queue_is_idempotent(self):
        first = queue_lead(self.message_id, "admin1")
        second = queue_lead(self.message_id, "admin1")
        self.assertEqual(first["id"], second["id"])
        with db.connect() as con:
            count = con.execute("SELECT COUNT(*) FROM crm_lead_outbox").fetchone()[0]
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
