import json
import os
import shutil
import tempfile
from urllib import request as urllib_request

import db
from crm_connector import queue_lead, send_outbox_item, validate_receipt
from lead_review import save_review


def post_again(url, token, payload):
    req = urllib_request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + token,
            "x-satno-connector": "bale_market",
        },
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=10) as response:
        status = int(response.status)
        body = json.loads(response.read().decode("utf-8"))
    return status, body


def main():
    url = (os.getenv("SATNO_CRM_LEAD_URL") or "").strip()
    token = (os.getenv("SATNO_BALE_MARKET_INGEST_TOKEN") or "").strip()
    if not url.startswith("http://127.0.0.1:"):
        raise SystemExit("Acceptance receiver must be loopback-only.")
    if len(token) < 32:
        raise SystemExit("Synthetic acceptance token must be at least 32 characters.")

    tmp = tempfile.mkdtemp(prefix="satno-bale-crm-acceptance-")
    try:
        db.DB_PATH = os.path.join(tmp, "acceptance.db")
        db.init_db()
        with db.connect() as con:
            message_id = con.execute(
                """INSERT INTO messages
                   (external_id,chat_name,sender_name,sender_id,text,sent_at,category,
                    brands,product_types,models,power_values,energy_values,price_values,
                    currency_values,locations,phones)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "acceptance-1","بازار آزمایشی","تأمین‌کننده تست","9001",
                    "موجودی آزمایشی اینورتر Deye 80kW در اهواز",
                    "2026-10-06T10:00:00Z","stock_availability",
                    '["deye"]','["inverter"]','["SUN-80K"]','["80kw"]','[]','[]','[]',
                    '["اهواز"]','["09120000000"]',
                ),
            ).lastrowid
        save_review(
            message_id,
            "acceptance",
            {
                "review_status": "selected",
                "reviewed_category": "stock_availability",
                "product": "inverter",
                "brand": "deye",
                "model": "SUN-80K",
                "power": "80kw",
                "location": "اهواز",
                "contact": "09120000000",
                "priority": "normal",
            },
        )
        outbox = queue_lead(message_id, "acceptance")
        result = send_outbox_item(outbox["id"])
        if result.get("status") != "sent" or not result.get("crm_lead_id"):
            raise AssertionError("first connector delivery did not produce a valid receipt")

        with db.connect() as con:
            stored = dict(con.execute("SELECT * FROM crm_lead_outbox WHERE id=?", (outbox["id"],)).fetchone())
        if stored["status"] != "sent" or not stored["crm_request_id"]:
            raise AssertionError("valid CRM receipt was not persisted")
        payload = json.loads(stored["payload"])

        status2, body2 = post_again(url, token, payload)
        receipt2 = validate_receipt(status2, body2, payload["source_record_id"])
        if not receipt2["duplicate"]:
            raise AssertionError("receiver did not report idempotent duplicate")
        if receipt2["crm_lead_id"] != stored["crm_lead_id"]:
            raise AssertionError("duplicate receipt returned a different CRM id")

        print("PASS: Bale Market -> mock ingest_leads adapter acceptance")
        print("PASS: required connector header + Bearer authentication")
        print("PASS: valid receipt identity required; HTTP status alone is insufficient")
        print("PASS: duplicate delivery returned the same CRM lead identity")
        print("PASS: secrets and raw payload were not printed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
