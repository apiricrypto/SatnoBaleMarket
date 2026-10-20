"""Recovery addresses are assigned by trusted staff administration, never a public request."""
import re


def normalize_email(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str) or any(c in value for c in '\r\n\x00'):
        raise ValueError('invalid email')
    value = value.strip().lower()
    if not value:
        return None
    if len(value) > 254 or value.count('@') != 1:
        raise ValueError('invalid email')
    local, domain = value.split('@')
    if (not 1 <= len(local) <= 64 or local.startswith('.') or local.endswith('.') or '..' in local
            or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", local)
            or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}', domain)):
        raise ValueError('invalid email')
    return value
