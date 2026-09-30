from datetime import datetime, timezone, timedelta
from typing import Optional

TEHRAN = timezone(timedelta(hours=3, minutes=30))
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

def parse_message_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt=value
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=TEHRAN)
        return dt.astimezone(timezone.utc)
    if isinstance(value, (int,float)):
        number=float(value)
    else:
        raw=str(value).strip().translate(_PERSIAN_DIGITS)
        if not raw:
            return None
        # Handle common SDK reprs such as "2026-09-30 12:30:00+00:00".
        try:
            dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
            if dt.tzinfo is None:
                dt=dt.replace(tzinfo=TEHRAN)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
        try:
            number=float(raw)
        except ValueError:
            return None
    try:
        if abs(number)>10_000_000_000:
            number/=1000.0
        return datetime.fromtimestamp(number,tz=timezone.utc)
    except (ValueError,OSError,OverflowError):
        return None

def canonical_sent_at(value):
    dt=parse_message_datetime(value)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""
