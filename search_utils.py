import math
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

_SEARCH_WEIGHTS = {
    "models": 12,
    "brands": 10,
    "product_types": 8,
    "locations": 7,
    "power_values": 7,
    "energy_values": 7,
    "price_values": 6,
    "currency_values": 5,
    "sender_username": 5,
    "sender_name": 4,
    "chat_name": 3,
    "text": 2,
    "category": 1,
}


def normalize_search_text(value: str) -> str:
    text=(value or "").lower().translate(_ARABIC_TO_PERSIAN).translate(_PERSIAN_DIGITS)
    text=re.sub(r"[\u200c\u200d\u200e\u200f]", " ", text)
    # Treat common model separators as spaces too, so SUN-80K and SUN 80K match.
    text=text.replace("-", " ").replace("/", " ").replace("_", " ")
    text=re.sub(r"[^\w\u0600-\u06ff.+]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def expand_term(term: str):
    term=normalize_search_text(term)
    variants={term}
    if term in ALIASES:
        variants.add(ALIASES[term])
    for alias, canonical in ALIASES.items():
        if term == canonical:
            variants.add(alias)
    return sorted(normalize_search_text(v) for v in variants if v)


def query_terms(query: str):
    return [expand_term(t) for t in normalize_search_text(query).split() if t]


def _field_text(row, field):
    return normalize_search_text(str(row.get(field) or ""))


def message_search_score(row, query: str) -> int:
    """Return 0 for no match, otherwise a relevance score.

    Search intentionally runs on normalized persisted data in Python instead of
    relying on SQLite raw LIKE matching. This fixes Persian/Arabic character,
    zero-width-space, Persian-digit and model-separator mismatches.
    """
    normalized_query = normalize_search_text(query)
    if not normalized_query:
        return 0

    normalized_fields = {
        field: _field_text(row, field) for field in _SEARCH_WEIGHTS
    }

    text_haystack = normalized_fields["text"]
    structured = " ".join(
        normalized_fields[k]
        for k in (
            "models","brands","product_types","locations","power_values",
            "energy_values","price_values","currency_values","chat_name",
            "sender_name","sender_username"
        )
    ).strip()
    all_haystack = (text_haystack + " " + structured).strip()

    # Pasting an exact product/message phrase should always be the strongest hit.
    if normalized_query and normalized_query in all_haystack:
        bonus = 120
        if normalized_query in text_haystack:
            bonus += 30
        return bonus

    groups = query_terms(normalized_query)
    if not groups:
        return 0

    score = 0
    matched_groups = 0
    for variants in groups:
        group_best = 0
        for field, weight in _SEARCH_WEIGHTS.items():
            haystack = normalized_fields[field]
            if haystack and any(v and v in haystack for v in variants):
                group_best = max(group_best, weight)
        if group_best:
            matched_groups += 1
            score += group_best

    # Short searches stay strict. Longer pasted titles tolerate harmless extra
    # words while still requiring most terms to match.
    required = len(groups) if len(groups) <= 3 else max(3, math.ceil(len(groups) * 0.65))
    if matched_groups < required:
        return 0

    coverage = matched_groups / len(groups)
    score += int(coverage * 30)
    return score
