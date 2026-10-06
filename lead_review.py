from datetime import datetime, timezone

from db import connect, init_db

REVIEW_STATUSES = {"unreviewed", "reviewed", "selected", "rejected"}
CATEGORIES = {
    "supplier_seller",
    "stock_availability",
    "buyer_demand",
    "inquiry_project",
    "other",
}
PRIORITIES = {"low", "normal", "high", "urgent"}


def get_review(message_id):
    init_db()
    with connect() as con:
        row = con.execute(
            "SELECT * FROM lead_reviews WHERE message_id=?",
            (message_id,),
        ).fetchone()
    return dict(row) if row else None


def save_review(message_id, reviewer, values):
    init_db()
    status = values.get("review_status", "reviewed")
    if status not in REVIEW_STATUSES:
        raise ValueError("invalid review_status")
    category = values.get("reviewed_category")
    if category is not None and category not in CATEGORIES:
        raise ValueError("invalid reviewed_category")
    priority = values.get("priority")
    if priority is not None and priority not in PRIORITIES:
        raise ValueError("invalid priority")

    amount = values.get("estimated_amount")
    currency = values.get("estimated_currency")
    if amount in ("", None):
        amount = None
    else:
        try:
            amount = int(amount)
        except (TypeError, ValueError):
            raise ValueError("estimated_amount must be an integer") from None
        if amount < 0:
            raise ValueError("estimated_amount must be non-negative")
    if currency in ("", None):
        currency = None
    else:
        currency = str(currency).strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("estimated_currency must be a 3-letter code")
    if (amount is None) != (currency is None):
        raise ValueError("estimated_amount and estimated_currency must be set together")

    now = datetime.now(timezone.utc).isoformat()
    fields = {
        "review_status": status,
        "reviewed_category": category,
        "product": values.get("product"),
        "brand": values.get("brand"),
        "model": values.get("model"),
        "power": values.get("power"),
        "capacity": values.get("capacity"),
        "price": values.get("price"),
        "currency": values.get("currency"),
        "estimated_amount": amount,
        "estimated_currency": currency,
        "location": values.get("location"),
        "contact": values.get("contact"),
        "priority": priority or "normal",
        "notes": values.get("notes"),
        "reviewed_by": reviewer,
        "reviewed_at": now,
        "updated_at": now,
    }

    with connect() as con:
        exists = con.execute("SELECT 1 FROM messages WHERE id=?", (message_id,)).fetchone()
        if not exists:
            raise ValueError("message not found")
        con.execute(
            """INSERT INTO lead_reviews
               (message_id,review_status,reviewed_category,product,brand,model,power,capacity,
                price,currency,estimated_amount,estimated_currency,location,contact,priority,
                notes,reviewed_by,reviewed_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(message_id) DO UPDATE SET
                 review_status=excluded.review_status,
                 reviewed_category=excluded.reviewed_category,
                 product=excluded.product,
                 brand=excluded.brand,
                 model=excluded.model,
                 power=excluded.power,
                 capacity=excluded.capacity,
                 price=excluded.price,
                 currency=excluded.currency,
                 estimated_amount=excluded.estimated_amount,
                 estimated_currency=excluded.estimated_currency,
                 location=excluded.location,
                 contact=excluded.contact,
                 priority=excluded.priority,
                 notes=excluded.notes,
                 reviewed_by=excluded.reviewed_by,
                 reviewed_at=excluded.reviewed_at,
                 updated_at=excluded.updated_at""",
            (
                message_id,
                fields["review_status"],
                fields["reviewed_category"],
                fields["product"],
                fields["brand"],
                fields["model"],
                fields["power"],
                fields["capacity"],
                fields["price"],
                fields["currency"],
                fields["estimated_amount"],
                fields["estimated_currency"],
                fields["location"],
                fields["contact"],
                fields["priority"],
                fields["notes"],
                fields["reviewed_by"],
                fields["reviewed_at"],
                fields["updated_at"],
            ),
        )
        row = con.execute(
            "SELECT * FROM lead_reviews WHERE message_id=?",
            (message_id,),
        ).fetchone()
    return dict(row)
