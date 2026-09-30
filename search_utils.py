import re

_ARABIC_TO_PERSIAN = str.maketrans({"ي":"ی","ك":"ک","ة":"ه","ۀ":"ه"})
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

ALIASES = {
    "گرووات": "growatt",
    "گروات": "growatt",
    "growatt": "growatt",
    "دی آی": "deye",
    "دیه": "deye",
    "deye": "deye",
    "جینکو": "jinko",
    "jinko": "jinko",
    "ترینا": "trina",
    "trina": "trina",
}

def normalize_search_text(value: str) -> str:
    text=(value or "").lower().translate(_ARABIC_TO_PERSIAN).translate(_PERSIAN_DIGITS)
    text=re.sub(r"[\u200c\u200d\u200e\u200f]", " ", text)
    text=re.sub(r"[^\w\u0600-\u06ff.+-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def expand_term(term: str):
    term=normalize_search_text(term)
    variants={term}
    if term in ALIASES:
        variants.add(ALIASES[term])
    for alias, canonical in ALIASES.items():
        if term == canonical:
            variants.add(alias)
    return sorted(v for v in variants if v)

def query_terms(query: str):
    return [expand_term(t) for t in normalize_search_text(query).split() if t]
