import hashlib
import re

def _norm(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().lower()

def make_dedup_key(*, external_id=None, chat_name=None, sender_name=None, sent_at=None, text=""):
    chat = _norm(chat_name)
    if external_id not in (None, ""):
        raw = f"ext|{chat}|{_norm(external_id)}"
    else:
        raw = "|".join(["msg", chat, _norm(sender_name), _norm(sent_at), _norm(text)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
