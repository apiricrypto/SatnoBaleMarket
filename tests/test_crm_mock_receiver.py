import json
import os
import tempfile
import threading
import unittest

import db
import tools.mock_crm_receiver as mock_receiver
from crm_connector import queue_lead, send_outbox_item
from lead_review import save_review


class MockCRMReceiverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = os.path.join(self.tmp.name, "mock-receiver.db")
        db.init_db()
        self.token = "m" * 48
        mock_receiver.TOKEN = self.token
        mock_receiver._records.clear()
        mock_receiver._next_id = 1000
        self.server = mock_receiver.ThreadingHTTPServer(("127.0.0.1", 0), mock_receiver.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.old_url = os.environ.get("SATNO_CRM_LEAD_URL")
        self.old_token = os.environ.get("SATNO_BALE_MARKET_INGEST_TOKEN")
        os.environ["SATNO_CRM_LEAD_URL"] = (
            f"http://127.0.0.1:{self.server.server_port}/functions/v1/ingest_leads"
        )
        os.environ["SATNO_BALE_MARKET_INGEST_TOKEN"] = self.token

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.old_url is None:
            os.environ.pop("SATNO_CRM_LEAD_URL", None)
        else:
            os.environ["SATNO_CRM_LEAD_URL"] = self.old_url
        if self.old_token is None:
            os.environ.pop("SATNO_BALE_MARKET_INGEST_TOKEN", None)
        else:
            os.environ["SATNO_BALE_MARKET_INGEST_TOKEN"] = self.old_token
        self.tmp.cleanup()

    def _seed_selected(self):
        with db.connect() as con:
            message_id = con.execute(
                """INSERT INTO messages
                   (external_id,chat_name,sender_name,text,sent_at,category,brands,product_types)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    "mock-1",
                    "بازار تست",
                    "تأمین‌کننده تست",
                    "موجودی آزمایشی اینورتر",
                    "2026-10-06T10:00:00Z",
                    "stock_availability",
                    '["deye"]',
                    '["inverter"]',
                ),
            ).lastrowid
        save_review(
            message_id,
            "tester",
            {
                "review_status": "selected",
                "reviewed_category": "stock_availability",
                "product": "inverter",
                "brand": "deye",
                "priority": "normal",
            },
        )
        return message_id

    def test_real_mock_receiver_returns_valid_receipt(self):
        message_id = self._seed_selected()
        outbox = queue_lead(message_id, "tester")
        result = send_outbox_item(outbox["id"])
        self.assertEqual(result["status"], "sent")
        self.assertTrue(result["crm_lead_id"])
        with db.connect() as con:
            row = con.execute(
                "SELECT status,crm_lead_id,crm_request_id,last_http_status FROM crm_lead_outbox WHERE id=?",
                (outbox["id"],),
            ).fetchone()
        self.assertEqual(row["status"], "sent")
        self.assertEqual(row["last_http_status"], 201)
        self.assertTrue(row["crm_request_id"])

    def test_mock_receiver_duplicate_returns_same_identity(self):
        message_id = self._seed_selected()
        outbox = queue_lead(message_id, "tester")
        first = send_outbox_item(outbox["id"])
        self.assertEqual(first["status"], "sent")
        with db.connect() as con:
            payload = json.loads(
                con.execute("SELECT payload FROM crm_lead_outbox WHERE id=?", (outbox["id"],)).fetchone()[0]
            )
        from tools.crm_adapter_acceptance import post_again
        status, body = post_again(
            os.environ["SATNO_CRM_LEAD_URL"],
            self.token,
            payload,
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["duplicate"])
        self.assertEqual(str(body["data"]["id"]), first["crm_lead_id"])


if __name__ == "__main__":
    unittest.main()
