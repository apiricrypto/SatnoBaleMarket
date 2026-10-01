import hashlib
import json
import os
from datetime import datetime, timezone
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError

from db import connect, init_db


def _json_list(value):
    try:
        data = json.loads(value or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _idempotency_key(row):
    base = "|".join([
        "bale",
        str(row.get("external_id") or ""),
        str(row.get("chat_name") or ""),
        str(row.get("id") or ""),
    ])
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def build_lead_payload(row):
    return {
        "contract_version": "satno.lead.v1",
        "source": "bale-market",
        "source_record_id": row.get("id"),
        "idempotency_key": _idempotency_key(row),
        "title": (row.get("text") or "")[:180],
        "description": row.get("text") or "",
        "category": row.get("category"),
        "brands": _json_list(row.get("brands")),
        "product_types": _json_list(row.get("product_types")),
        "models": _json_list(row.get("models")),
        "power_values": _json_list(row.get("power_values")),
        "energy_values": _json_list(row.get("energy_values")),
        "price_values": _json_list(row.get("price_values")),
        "quantities": _json_list(row.get("quantities")),
        "locations": _json_list(row.get("locations")),
        "phones": _json_list(row.get("phones")),
        "sender": {
            "id": row.get("sender_id"),
            "name": row.get("sender_name"),
            "username": row.get("sender_username"),
            "link": row.get("sender_link"),
        },
        "provenance": {
            "chat_name": row.get("chat_name"),
            "external_id": row.get("external_id"),
            "sent_at": row.get("sent_at"),
            "created_at": row.get("created_at"),
        },
    }


def queue_lead(message_id, requested_by):
    init_db()
    with connect() as con:
        row = con.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
        if not row:
            raise ValueError("message not found")
        row = dict(row)
        payload = build_lead_payload(row)
        key = payload["idempotency_key"]
        con.execute(
            """
            INSERT OR IGNORE INTO crm_lead_outbox
            (message_id,idempotency_key,requested_by,payload,status)
            VALUES(?,?,?,?, 'queued')
            """,
            (message_id, key, requested_by, json.dumps(payload, ensure_ascii=False)),
        )
        outbox = con.execute(
            "SELECT * FROM crm_lead_outbox WHERE idempotency_key=?",
            (key,),
        ).fetchone()
    return dict(outbox)


def send_queued_lead(message_id, requested_by):
    outbox = queue_lead(message_id, requested_by)
    url = (os.getenv("SATNO_CRM_LEAD_URL") or "").strip()
    token = (os.getenv("SATNO_CRM_API_TOKEN") or "").strip()

    if not url:
        return {
            "status": "queued",
            "message": "SATNO_CRM_LEAD_URL is not configured",
            "outbox_id": outbox["id"],
        }

    payload = outbox["payload"].encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token

    req = urllib_request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(req, timeout=15) as response:
            code = int(getattr(response, "status", 200))
            if code < 200 or code >= 300:
                raise RuntimeError(f"CRM returned HTTP {code}")
        sent_at = datetime.now(timezone.utc).isoformat()
        with connect() as con:
            con.execute(
                "UPDATE crm_lead_outbox SET status='sent',last_error=NULL,sent_at=? WHERE id=?",
                (sent_at, outbox["id"]),
            )
        return {"status": "sent", "outbox_id": outbox["id"]}
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
        error = f"{type(exc).__name__}: {exc}"[:500]
        with connect() as con:
            con.execute(
                "UPDATE crm_lead_outbox SET status='failed',last_error=? WHERE id=?",
                (error, outbox["id"]),
            )
        return {"status": "failed", "error": error, "outbox_id": outbox["id"]}
