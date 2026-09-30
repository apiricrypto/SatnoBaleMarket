import re
from datetime import datetime, timezone, timedelta

TEHRAN = timezone(timedelta(hours=3, minutes=30))
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

def parse_message_datetime(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    raw=str(value).strip().translate(_PERSIAN_DIGITS)
    if not raw:
        return None
    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        try:
            number=float(raw)
            # Bale may expose Unix seconds or milliseconds.
            if abs(number) > 10_000_000_000:
                number /= 1000.0
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    try:
        dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=TEHRAN)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

def canonical_sent_at(value):
    dt=parse_message_datetime(value)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else (str(value) if value is not None else "")
