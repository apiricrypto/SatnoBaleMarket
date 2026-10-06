import json
import os
import tempfile
import unittest
from unittest.mock import patch

import db
from crm_connector import (
    build_lead_payload,
    queue_lead,
    send_outbox_item,
    validate_receipt,
)
from lead_review import save_review


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *_args):
        return self._body


class CRMConnectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = os.path.join(self.tmp.name, "crm-test.db")
        db.init_db()
        with db.connect() as con:
            self.message_id = con.execute(
                """
                INSERT INTO messages
                (external_id,chat_name,sender_name,sender_id,sender_username,sender_link,
                 text,sent_at,category,brands,product_types,models,power_values,
                 energy_values,price_values,currency_values,locations,phones)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "42","بازار سولار","فروشنده","1001","seller","https://ble.ir/seller",
                    "موجودی اینورتر Deye 80kW قیمت 1000000 ریال",
                    "2026-10-01T10:00:00+00:00","stock_availability",
                    '["deye"]','["inverter"]','["SUN-80K"]','["80kw"]',
                    '["16kwh"]','["1000000 ریال"]','["IRR"]','["اهواز"]','["09120000000"]'
                ),
            ).lastrowid
        save_review(
            self.message_id,
            "admin1",
            {
                "review_status": "selected",
                "reviewed_category": "stock_availability",
                "product": "inverter",
                "brand": "deye",
                "model": "SUN-80K",
                "power": "80kw",
                "capacity": "16kwh",
                "price": "1000000 ریال",
                "currency": "IRR",
                "estimated_amount": 1000000,
                "estimated_currency": "IRR",
                "location": "اهواز",
                "contact": "09120000000",
                "priority": "high",
                "notes": "reviewed",
            },
        )
        self.old_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)
        self.tmp.cleanup()

    def _row(self):
        with db.connect() as con:
            return dict(con.execute("SELECT * FROM messages WHERE id=?", (self.message_id,)).fetchone())

    def test_payload_matches_ingest_leads_contract_shape(self):
        payload = build_lead_payload(self._row(), {
            "review_status": "selected",
            "product": "inverter",
            "brand": "deye",
            "model": "SUN-80K",
            "power": "80kw",
            "capacity": "16kwh",
            "price": "1000000 ریال",
            "currency": "IRR",
            "estimated_amount": 1000000,
            "estimated_currency": "IRR",
            "location": "اهواز",
            "contact": "09120000000",
            "priority": "high",
        })
        allowed = {
            "source_record_id","source_url","title","organization_name","contact_name",
            "contact_phone","contact_email","province","city","description",
            "estimated_amount","estimated_currency","deadline","priority","raw_payload",
            "captured_at",
        }
        self.assertTrue(set(payload).issubset(allowed))
        self.assertIsInstance(payload["source_record_id"], str)
        self.assertTrue(payload["source_record_id"].startswith("bale:"))
        self.assertEqual(payload["estimated_currency"], "IRR")
        self.assertEqual(payload["estimated_amount"], 1000000)
        self.assertEqual(payload["raw_payload"]["review"]["brand"], "deye")
        self.assertNotIn("contract_version", payload)
        self.assertNotIn("source", payload)
        self.assertNotIn("idempotency_key", payload)

    def test_queue_requires_human_selection_for_new_items(self):
        with db.connect() as con:
            other = con.execute(
                "INSERT INTO messages(text,category) VALUES(?,?)",
                ("تقاضای خرید پنل", "buyer_demand"),
            ).lastrowid
        with self.assertRaisesRegex(ValueError, "reviewed and selected"):
            queue_lead(other, "sales1")

    def test_queue_is_idempotent_and_preserves_existing_row(self):
        first = queue_lead(self.message_id, "admin1")
        second = queue_lead(self.message_id, "admin1")
        self.assertEqual(first["id"], second["id"])
        with db.connect() as con:
            count = con.execute("SELECT COUNT(*) FROM crm_lead_outbox").fetchone()[0]
        self.assertEqual(count, 1)

    def test_legacy_queued_row_is_preserved_and_payload_refreshed(self):
        with db.connect() as con:
            legacy_id = con.execute(
                """INSERT INTO crm_lead_outbox
                   (message_id,idempotency_key,requested_by,payload,status)
                   VALUES(?,?,?,?,?)""",
                (self.message_id, "legacy-key", "admin1", '{"contract_version":"satno.lead.v1"}', "queued"),
            ).lastrowid
        outbox = queue_lead(self.message_id, "admin2")
        self.assertEqual(outbox["id"], legacy_id)
        payload = json.loads(outbox["payload"])
        self.assertIn("source_record_id", payload)
        self.assertNotIn("contract_version", payload)

    def test_valid_receipt_requires_identity_not_just_http_200(self):
        source_id = "bale:abc"
        good = {
            "data": {
                "id": 91,
                "source": "bale_market",
                "source_record_id": source_id,
                "status": "new",
                "created_at": "2026-10-06T10:00:00Z",
            },
            "duplicate": False,
            "request_id": "req-1",
        }
        receipt = validate_receipt(201, good, source_id)
        self.assertEqual(receipt["crm_lead_id"], "91")
        with self.assertRaisesRegex(Exception, "source mismatch"):
            validate_receipt(200, {**good, "data": {**good["data"], "source": "wrong"}}, source_id)

    def test_send_uses_connector_header_and_stores_valid_receipt(self):
        outbox = queue_lead(self.message_id, "admin1")
        payload = json.loads(outbox["payload"])
        os.environ["SATNO_CRM_LEAD_URL"] = "http://127.0.0.1:8099/functions/v1/ingest_leads"
        os.environ["SATNO_BALE_MARKET_INGEST_TOKEN"] = "x" * 40

        body = {
            "data": {
                "id": 123,
                "source": "bale_market",
                "source_record_id": payload["source_record_id"],
                "status": "new",
                "created_at": "2026-10-06T10:00:00Z",
            },
            "duplicate": False,
            "request_id": "mock-request",
        }

        captured = {}
        def fake_open(req, timeout=0):
            captured["connector"] = req.get_header("X-satno-connector")
            captured["authorization"] = req.get_header("Authorization")
            captured["timeout"] = timeout
            return FakeResponse(201, body)

        with patch("crm_connector.urllib_request.urlopen", fake_open):
            result = send_outbox_item(outbox["id"])

        self.assertEqual(result["status"], "sent")
        self.assertEqual(captured["connector"], "bale_market")
        self.assertTrue(captured["authorization"].startswith("Bearer "))
        with db.connect() as con:
            row = con.execute("SELECT * FROM crm_lead_outbox WHERE id=?", (outbox["id"],)).fetchone()
        self.assertEqual(row["crm_lead_id"], "123")
        self.assertEqual(row["crm_request_id"], "mock-request")
        self.assertEqual(row["status"], "sent")

    def test_http_200_with_invalid_receipt_is_not_success(self):
        outbox = queue_lead(self.message_id, "admin1")
        os.environ["SATNO_CRM_LEAD_URL"] = "http://127.0.0.1:8099/functions/v1/ingest_leads"
        os.environ["SATNO_BALE_MARKET_INGEST_TOKEN"] = "x" * 40
        os.environ["SATNO_CRM_MAX_ATTEMPTS"] = "2"
        with patch(
            "crm_connector.urllib_request.urlopen",
            lambda *_args, **_kwargs: FakeResponse(200, {"ok": True}),
        ):
            result = send_outbox_item(outbox["id"])
        self.assertEqual(result["status"], "retry")
        with db.connect() as con:
            row = con.execute("SELECT status,attempts,crm_lead_id FROM crm_lead_outbox WHERE id=?", (outbox["id"],)).fetchone()
        self.assertEqual(row["status"], "retry")
        self.assertEqual(row["attempts"], 1)
        self.assertIsNone(row["crm_lead_id"])


if __name__ == "__main__":
    unittest.main()
