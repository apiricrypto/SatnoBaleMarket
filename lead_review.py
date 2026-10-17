import json
from datetime import datetime, timezone
from business_profiles import load_business_profile, validate_business_profile

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
    if not row:
        return None
    result = dict(row)
    result['business_profile'] = load_business_profile(result.get('business_profile'))
    return result


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
        prior = con.execute("SELECT business_profile,contact FROM lead_reviews WHERE message_id=?", (message_id,)).fetchone()
        previous_profile = load_business_profile(prior['business_profile']) if prior else None
        supplied = values.get('business_profile') is not None
        profile = values.get('business_profile') if supplied else previous_profile
        if previous_profile and 'contact' not in values:
            fields['contact'] = prior['contact']
        if not supplied and profile is not None:
            profile = dict(profile)
            if profile.get('verified_contact') != fields['contact']:
                profile['contact_verification'] = 'unverified'
                profile['verification_note'] = ''
        profile = validate_business_profile(profile, selected=status == 'selected',
            primary_contact=fields['contact'], trusted_stored=not supplied)
        if profile is not None:
            if profile['contact_verification'] == 'confirmed':
                unchanged = bool(previous_profile and previous_profile.get('contact_verification') == 'confirmed'
                    and previous_profile.get('declared_name') == profile['declared_name']
                    and previous_profile.get('entity_type') == profile['entity_type']
                    and previous_profile.get('verification_note') == profile['verification_note']
                    and previous_profile.get('verified_contact') == fields['contact'])
                profile['contact_verified_by'] = previous_profile.get('contact_verified_by') if unchanged else reviewer
                profile['contact_verified_at'] = previous_profile.get('contact_verified_at') if unchanged else now
                profile['verified_contact'] = fields['contact']
            else:
                profile.update(contact_verified_by=None, contact_verified_at=None, verified_contact=None)
        fields['business_profile'] = json.dumps(profile, ensure_ascii=False) if profile is not None else None
        columns = ['message_id', *fields]
        updates = ','.join(f'{key}=excluded.{key}' for key in fields)
        con.execute(
            'INSERT INTO lead_reviews (' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in columns) + ') '
            'ON CONFLICT(message_id) DO UPDATE SET ' + updates,
            [message_id, *fields.values()],
        )
        row = con.execute(
            "SELECT * FROM lead_reviews WHERE message_id=?",
            (message_id,),
        ).fetchone()
    result = dict(row)
    result['business_profile'] = load_business_profile(result.get('business_profile'))
    return result
