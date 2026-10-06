import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError

from dotenv import load_dotenv

from db import connect, init_db

load_dotenv(".env.local")

CONNECTOR_NAME = "bale_market"
DEFAULT_MAX_ATTEMPTS = 3
MAX_RAW_PAYLOAD_BYTES = 64 * 1024
MAX_REQUEST_BYTES = 128 * 1024
MAX_SAFE_INTEGER = 9_007_199_254_740_991
ALLOWED_PRIORITIES = {"low", "normal", "high", "urgent"}


class CRMConnectorError(RuntimeError):
    pass


def _json_list(value):
    try:
        data = json.loads(value or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _iso_timestamp(value):
    text = str(value or "").strip()
    if text:
        try:
            if text.endswith("Z"):
                dt = datetime.fromisoformat(text[:-1] + "+00:00")
            else:
                dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_record_id(row):
    stable = "|".join([
        str(row.get("chat_name") or ""),
        str(row.get("external_id") or row.get("dedup_key") or row.get("id") or ""),
    ])
    digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()
    return "bale:" + digest


def _local_idempotency_key(source_record_id):
    return hashlib.sha256(
        (CONNECTOR_NAME + "|" + source_record_id).encode("utf-8")
    ).hexdigest()


def _review_for_message(message_id):
    with connect() as con:
        row = con.execute(
            "SELECT * FROM lead_reviews WHERE message_id=?",
            (message_id,),
        ).fetchone()
    return dict(row) if row else None


def _first(values):
    return values[0] if values else None


def validate_outbound_payload(payload):
    required = ("source_record_id", "title", "captured_at", "raw_payload")
    for field in required:
        if field not in payload:
            raise ValueError(f"{field} is required")
    if not isinstance(payload["source_record_id"], str) or not payload["source_record_id"].strip():
        raise ValueError("source_record_id must be text")
    if len(payload["source_record_id"]) > 200:
        raise ValueError("source_record_id is too long")
    if not isinstance(payload["title"], str) or not payload["title"].strip():
        raise ValueError("title is required")
    if len(payload["title"]) > 500:
        raise ValueError("title is too long")
    if not isinstance(payload["raw_payload"], dict):
        raise ValueError("raw_payload must be an object")
    raw_bytes = len(json.dumps(payload["raw_payload"], ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if raw_bytes > MAX_RAW_PAYLOAD_BYTES:
        raise ValueError("raw_payload is too large")

    captured = payload["captured_at"]
    try:
        dt = datetime.fromisoformat(captured.replace("Z", "+00:00"))
    except Exception:
        raise ValueError("captured_at must be an ISO timestamp with timezone") from None
    if dt.tzinfo is None:
        raise ValueError("captured_at must include timezone")
    if dt.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("captured_at cannot be in the future")

    priority = payload.get("priority", "normal")
    if priority not in ALLOWED_PRIORITIES:
        raise ValueError("priority is invalid")

    amount = payload.get("estimated_amount")
    currency = payload.get("estimated_currency")
    if (amount is None) != (currency is None):
        raise ValueError("estimated_amount and estimated_currency must be paired")
    if amount is not None:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0 or amount > MAX_SAFE_INTEGER:
            raise ValueError("estimated_amount must be a non-negative safe integer")
        if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha() or currency.upper() != currency:
            raise ValueError("estimated_currency must be a three-letter uppercase code")

    text_limits = {
        "source_url": 2048, "organization_name": 500, "contact_name": 300,
        "contact_phone": 64, "contact_email": 320, "province": 200, "city": 200,
        "description": 10000, "deadline": 10,
    }
    for field, limit in text_limits.items():
        value = payload.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > limit):
            raise ValueError(f"{field} is invalid")

    body_bytes = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if body_bytes > MAX_REQUEST_BYTES:
        raise ValueError("request body is too large")
    return payload


def build_lead_payload(row, review=None):
    review = review or {}
    source_record_id = _source_record_id(row)

    brands = _json_list(row.get("brands"))
    product_types = _json_list(row.get("product_types"))
    models = _json_list(row.get("models"))
    power_values = _json_list(row.get("power_values"))
    capacity_values = _json_list(row.get("energy_values"))
    price_values = _json_list(row.get("price_values"))
    currency_values = _json_list(row.get("currency_values"))
    locations = _json_list(row.get("locations"))
    phones = _json_list(row.get("phones"))

    reviewed_brand = review.get("brand") or _first(brands)
    reviewed_product = review.get("product") or _first(product_types)
    reviewed_model = review.get("model") or _first(models)
    reviewed_power = review.get("power") or _first(power_values)
    reviewed_capacity = review.get("capacity") or _first(capacity_values)
    reviewed_price = review.get("price") or _first(price_values)
    reviewed_currency = review.get("currency") or _first(currency_values)
    reviewed_location = review.get("location") or _first(locations)
    reviewed_contact = review.get("contact") or _first(phones)

    raw_payload = {
        "provider": "bale",
        "message": {
            "external_id": row.get("external_id"),
            "chat_name": row.get("chat_name"),
            "sender_id": row.get("sender_id"),
            "sender_name": row.get("sender_name"),
            "sender_username": row.get("sender_username"),
            "sender_link": row.get("sender_link"),
            "text": row.get("text"),
            "sent_at": row.get("sent_at"),
        },
        "extracted": {
            "category": row.get("category"),
            "brands": brands,
            "product_types": product_types,
            "models": models,
            "power_values": power_values,
            "capacity_values": capacity_values,
            "price_values": price_values,
            "currency_values": currency_values,
            "quantities": _json_list(row.get("quantities")),
            "phones": phones,
            "locations": locations,
        },
        "review": {
            "status": review.get("review_status"),
            "category": review.get("reviewed_category"),
            "product": reviewed_product,
            "brand": reviewed_brand,
            "model": reviewed_model,
            "power": reviewed_power,
            "capacity": reviewed_capacity,
            "price": reviewed_price,
            "currency": reviewed_currency,
            "location": reviewed_location,
            "contact": reviewed_contact,
            "notes": review.get("notes"),
            "reviewed_by": review.get("reviewed_by"),
            "reviewed_at": review.get("reviewed_at"),
        },
    }

    payload = {
        "source_record_id": source_record_id,
        "title": ((row.get("text") or "").strip() or f"Bale message {row.get('id')}")[:500],
        "captured_at": _iso_timestamp(row.get("sent_at") or row.get("created_at")),
        "raw_payload": raw_payload,
        "description": (row.get("text") or "")[:10000] or None,
        "contact_name": row.get("sender_name") or None,
        "contact_phone": reviewed_contact or None,
        "city": reviewed_location or None,
        "priority": review.get("priority") or "normal",
    }

    amount = review.get("estimated_amount")
    currency = (review.get("estimated_currency") or "").strip().upper()
    if amount is not None or currency:
        if amount is None or not currency:
            raise ValueError("estimated_amount and estimated_currency must be reviewed together")
        amount = int(amount)
        if amount < 0:
            raise ValueError("estimated_amount must be non-negative")
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("estimated_currency must be a 3-letter code")
        payload["estimated_amount"] = amount
        payload["estimated_currency"] = currency

    payload = {key: value for key, value in payload.items() if value is not None}
    return validate_outbound_payload(payload)


def queue_lead(message_id, requested_by, require_selected=True):
    init_db()
    with connect() as con:
        row = con.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
        if not row:
            raise ValueError("message not found")
        row = dict(row)
        review_row = con.execute(
            "SELECT * FROM lead_reviews WHERE message_id=?",
            (message_id,),
        ).fetchone()
        review = dict(review_row) if review_row else None

        existing = con.execute(
            "SELECT * FROM crm_lead_outbox WHERE message_id=? ORDER BY id LIMIT 1",
            (message_id,),
        ).fetchone()

        if require_selected and not existing:
            if not review or review.get("review_status") != "selected":
                raise ValueError("lead must be reviewed and selected before queueing")

        payload = build_lead_payload(row, review)
        source_record_id = payload["source_record_id"]
        key = _local_idempotency_key(source_record_id)
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        if existing:
            existing = dict(existing)
            if existing["status"] != "sent":
                con.execute(
                    """UPDATE crm_lead_outbox
                       SET payload=?,requested_by=?,status='queued',last_error=NULL,
                           next_retry_at=NULL
                       WHERE id=?""",
                    (payload_json, requested_by, existing["id"]),
                )
            outbox = con.execute(
                "SELECT * FROM crm_lead_outbox WHERE id=?",
                (existing["id"],),
            ).fetchone()
        else:
            con.execute(
                """INSERT INTO crm_lead_outbox
                   (message_id,idempotency_key,requested_by,payload,status)
                   VALUES(?,?,?,?, 'queued')""",
                (message_id, key, requested_by, payload_json),
            )
            outbox = con.execute(
                "SELECT * FROM crm_lead_outbox WHERE message_id=? ORDER BY id LIMIT 1",
                (message_id,),
            ).fetchone()
    return dict(outbox)


def _parse_json_response(response):
    raw = response.read(128 * 1024 + 1)
    if len(raw) > 128 * 1024:
        raise CRMConnectorError("CRM receipt is too large")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CRMConnectorError("CRM receipt is not valid JSON") from None


def validate_receipt(http_status, body, expected_source_record_id):
    if http_status not in (200, 201):
        raise CRMConnectorError(f"unexpected CRM HTTP status {http_status}")
    if not isinstance(body, dict):
        raise CRMConnectorError("CRM receipt must be an object")
    data = body.get("data")
    duplicate = body.get("duplicate")
    request_id = body.get("request_id")
    if not isinstance(data, dict):
        raise CRMConnectorError("CRM receipt is missing data")
    if not isinstance(duplicate, bool):
        raise CRMConnectorError("CRM receipt is missing duplicate flag")
    if not isinstance(request_id, str) or not request_id.strip():
        raise CRMConnectorError("CRM receipt is missing request_id")

    crm_id = data.get("id")
    if isinstance(crm_id, bool) or crm_id is None or str(crm_id).strip() == "":
        raise CRMConnectorError("CRM receipt is missing lead id")
    if data.get("source") != CONNECTOR_NAME:
        raise CRMConnectorError("CRM receipt source mismatch")
    if data.get("source_record_id") != expected_source_record_id:
        raise CRMConnectorError("CRM receipt source_record_id mismatch")
    crm_status = data.get("status")
    if not isinstance(crm_status, str) or not crm_status:
        raise CRMConnectorError("CRM receipt status is invalid")
    created_at = data.get("created_at")
    if not isinstance(created_at, str) or "T" not in created_at:
        raise CRMConnectorError("CRM receipt created_at is invalid")
    return {
        "crm_lead_id": str(crm_id),
        "crm_status": crm_status,
        "crm_request_id": request_id,
        "duplicate": duplicate,
        "receipt": body,
    }


def _retry_delay_seconds(attempts):
    return min(60 * (2 ** max(0, attempts - 1)), 3600)


def _mark_failure(outbox_id, attempts, error, http_status=None, retryable=True):
    max_attempts = max(1, int(os.getenv("SATNO_CRM_MAX_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS))))
    now = datetime.now(timezone.utc)
    if retryable and attempts < max_attempts:
        status = "retry"
        next_retry = now + timedelta(seconds=_retry_delay_seconds(attempts))
        next_retry_at = next_retry.isoformat()
    else:
        status = "dead"
        next_retry_at = None
    with connect() as con:
        con.execute(
            """UPDATE crm_lead_outbox
               SET status=?,attempts=?,last_attempt_at=?,next_retry_at=?,
                   last_error=?,last_http_status=?
               WHERE id=?""",
            (
                status,
                attempts,
                now.isoformat(),
                next_retry_at,
                str(error)[:500],
                http_status,
                outbox_id,
            ),
        )
    return status


def send_outbox_item(outbox_id):
    init_db()
    with connect() as con:
        row = con.execute(
            "SELECT * FROM crm_lead_outbox WHERE id=?",
            (outbox_id,),
        ).fetchone()
    if not row:
        raise ValueError("outbox item not found")
    outbox = dict(row)
    if outbox["status"] == "sent":
        return {"status": "sent", "outbox_id": outbox_id, "already_sent": True}

    url = (os.getenv("SATNO_CRM_LEAD_URL") or "").strip()
    token = (os.getenv("SATNO_BALE_MARKET_INGEST_TOKEN") or "").strip()
    if not url:
        return {
            "status": "queued",
            "message": "SATNO_CRM_LEAD_URL is not configured",
            "outbox_id": outbox_id,
        }
    if len(token) < 32:
        return {
            "status": "queued",
            "message": "SATNO_BALE_MARKET_INGEST_TOKEN is not configured",
            "outbox_id": outbox_id,
        }

    attempts = int(outbox.get("attempts") or 0) + 1
    payload_text = outbox["payload"]
    try:
        payload_obj = json.loads(payload_text)
    except json.JSONDecodeError:
        status = _mark_failure(
            outbox_id, attempts, "queued payload is invalid JSON", retryable=False
        )
        return {"status": status, "outbox_id": outbox_id, "error": "invalid queued payload"}

    expected_source_record_id = payload_obj.get("source_record_id")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + token,
        "x-satno-connector": CONNECTOR_NAME,
    }
    req = urllib_request.Request(
        url,
        data=payload_text.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    http_status = None
    try:
        with urllib_request.urlopen(req, timeout=15) as response:
            http_status = int(getattr(response, "status", 0))
            body = _parse_json_response(response)
        receipt = validate_receipt(http_status, body, expected_source_record_id)
        sent_at = datetime.now(timezone.utc).isoformat()
        with connect() as con:
            con.execute(
                """UPDATE crm_lead_outbox
                   SET status='sent',last_error=NULL,sent_at=?,attempts=?,
                       last_attempt_at=?,next_retry_at=NULL,last_http_status=?,
                       crm_lead_id=?,crm_status=?,crm_request_id=?,duplicate=?,receipt=?
                   WHERE id=?""",
                (
                    sent_at,
                    attempts,
                    sent_at,
                    http_status,
                    receipt["crm_lead_id"],
                    receipt["crm_status"],
                    receipt["crm_request_id"],
                    1 if receipt["duplicate"] else 0,
                    json.dumps(receipt["receipt"], ensure_ascii=False),
                    outbox_id,
                ),
            )
        return {
            "status": "sent",
            "outbox_id": outbox_id,
            "crm_lead_id": receipt["crm_lead_id"],
            "crm_status": receipt["crm_status"],
            "duplicate": receipt["duplicate"],
        }
    except HTTPError as exc:
        http_status = int(getattr(exc, "code", 0) or 0)
        retryable = http_status == 429 or http_status >= 500
        status = _mark_failure(
            outbox_id,
            attempts,
            f"HTTPError: {http_status}",
            http_status=http_status,
            retryable=retryable,
        )
        return {"status": status, "outbox_id": outbox_id, "error": f"HTTP {http_status}"}
    except (URLError, TimeoutError, OSError, CRMConnectorError) as exc:
        status = _mark_failure(
            outbox_id,
            attempts,
            f"{type(exc).__name__}: {exc}",
            http_status=http_status,
            retryable=True,
        )
        return {"status": status, "outbox_id": outbox_id, "error": str(exc)[:300]}


def process_outbox(limit=10):
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    max_attempts = max(1, int(os.getenv("SATNO_CRM_MAX_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS))))
    with connect() as con:
        rows = con.execute(
            """SELECT id FROM crm_lead_outbox
               WHERE status IN ('queued','retry')
                 AND COALESCE(attempts,0) < ?
                 AND (next_retry_at IS NULL OR next_retry_at<=?)
               ORDER BY id
               LIMIT ?""",
            (max_attempts, now, int(limit)),
        ).fetchall()
    return [send_outbox_item(row["id"]) for row in rows]


def send_queued_lead(message_id, requested_by):
    outbox = queue_lead(message_id, requested_by)
    return send_outbox_item(outbox["id"])
