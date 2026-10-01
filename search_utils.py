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


_SEARCH_WEIGHTS = {
    "models": 9,
    "brands": 8,
    "product_types": 7,
    "locations": 6,
    "power_values": 6,
    "energy_values": 6,
    "price_values": 5,
    "sender_username": 5,
    "sender_name": 4,
    "chat_name": 3,
    "text": 2,
    "category": 1,
}

def message_search_score(row, query: str) -> int:
    normalized_query = normalize_search_text(query)
    if not normalized_query:
        return 0

    groups = query_terms(normalized_query)
    score = 0
    matched_groups = 0

    for variants in groups:
        group_best = 0
        for field, weight in _SEARCH_WEIGHTS.items():
            haystack = normalize_search_text(str(row.get(field) or ""))
            if not haystack:
                continue
            if any(v and v in haystack for v in variants):
                group_best = max(group_best, weight)
        if group_best:
            matched_groups += 1
            score += group_best

    if matched_groups != len(groups):
        return 0

    text_haystack = normalize_search_text(str(row.get("text") or ""))
    if normalized_query in text_haystack:
        score += 4

    structured = " ".join(
        normalize_search_text(str(row.get(k) or ""))
        for k in ("models","brands","product_types","locations","power_values","energy_values")
    )
    if normalized_query in structured:
        score += 8

    return score
