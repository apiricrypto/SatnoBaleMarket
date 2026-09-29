import re, json

DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
CHAR_MAP = str.maketrans({
    "ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه",
    "\u200c": " ", "\u200f": " ", "\u200e": " ",
    "٫": ".", "٬": ",",
})

def normalize_text(text: str):
    text = (text or "").translate(CHAR_MAP).translate(DIGIT_MAP).lower()
    text = text.replace("،", ",")
    return re.sub(r"\s+", " ", text).strip()

BRAND_ALIASES = {
    "trina": ["trina", "ترینا"],
    "jinko": ["jinko", "جینکو"],
    "ja solar": ["ja solar", "جی ای سولار", "جی‌ای سولار"],
    "longi": ["longi", "لانگی"],
    "growatt": ["growatt", "گرووات"],
    "huawei": ["huawei", "هواوی"],
    "solis": ["solis", "سولیس"],
    "deye": ["deye", "دیه", "دی آی"],
    "sofar": ["sofar", "سوفار"],
    "must": ["must", "ماست"],
    "sako": ["sako", "ساکو"],
    "sunon": ["sunon", "سانون"],
    "gogreen": ["gogreen", "گوگرین"],
    "marsriva": ["marsriva", "مارسریوا"],
    "lvtopsun": ["lvtopsun"],
}
LOCATIONS = [
    "خوزستان","اهواز","آبادان","خرمشهر","ماهشهر","دزفول","شوشتر",
    "اندیمشک","بهبهان","رامهرمز","ایذه","مسجدسلیمان",
    "تهران","کرج","اصفهان","شیراز","تبریز","مشهد","قم","اراک","کرمان",
    "کرمانشاه","ایلام","لرستان","چهارمحال","بوشهر","بندرعباس","یزد"
]
PRODUCT_TYPES = {
    "panel": ["پنل", "ماژول خورشیدی", "solar panel", "pv module"],
    "inverter": ["اینورتر", "inverter"],
    "battery": ["باتری", "battery", "lifepo4", "lithium"],
    "structure": ["سازه", "استراکچر", "structure", "mounting"],
    "connector": ["mc4", "کانکتور", "connector"],
    "cable": ["کابل", "solar cable", "pv cable"],
    "charge_controller": ["شارژ کنترلر", "charge controller", "mppt controller"],
}
RULE_WEIGHTS = {
    "inquiry_project": {
        "استعلام": 4, "مناقصه": 4, "rfq": 4, "درخواست قیمت": 3,
        "پیشنهاد قیمت": 3, "قیمت می خوام": 3, "قیمت می خواهم": 3, "پروژه": 2,
    },
    "buyer_demand": {
        "خریدار": 4, "درخواست خرید": 4, "نیاز فوری": 4, "نیازمند": 3,
        "نیاز دارم": 3, "نیاز داریم": 3, "خرید دارم": 3, "مشتری": 2,
    },
    "stock_availability": {
        "موجودی": 4, "موجود است": 4, "در انبار": 4,
        "آماده تحویل": 3, "تحویل فوری": 3,
    },
    "supplier_seller": {
        "فروشنده": 4, "تامین": 3, "تأمین": 3, "عرضه": 3,
        "فروش": 2, "قیمت همکاری": 1, "همکار": 1,
    },
}
CATEGORY_PRIORITY = {
    "inquiry_project": 4,
    "buyer_demand": 3,
    "stock_availability": 2,
    "supplier_seller": 1,
}

def uniq(xs):
    out=[]
    for x in xs:
        if x not in out: out.append(x)
    return out

def _contains_phrase(text: str, phrase: str):
    phrase = normalize_text(phrase)
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text))

def extract_brands(low: str):
    found = []
    for canonical, aliases in BRAND_ALIASES.items():
        if any(_contains_phrase(low, alias) for alias in aliases):
            found.append(canonical)
    return found

def extract_product_types(low: str):
    return uniq([
        product_type
        for product_type, terms in PRODUCT_TYPES.items()
        if any(_contains_phrase(low, term) for term in terms)
    ])

def extract_models(low: str):
    models = []
    models.extend(re.findall(
        r'(?:\bmodel\b|مدل)\s*[:\-]?\s*([a-z0-9][a-z0-9._/-]*(?:\s+[a-z0-9][a-z0-9._/-]*){0,2})',
        low,
        re.I,
    ))
    models.extend(re.findall(
        r'\b(?=[a-z0-9/-]*[a-z])(?=[a-z0-9/-]*\d)[a-z0-9]+(?:[-/][a-z0-9]+)+\b',
        low,
        re.I,
    ))

    brand_words = {normalize_text(alias) for aliases in BRAND_ALIASES.values() for alias in aliases}
    for prefix, number, suffix in re.findall(
        r'\b([a-z]{2,8})\s+(\d{3,6}[a-z0-9-]*)(?:\s+([a-z]{2,8}))?\b',
        low,
        re.I,
    ):
        if normalize_text(prefix) in brand_words:
            continue
        if number.lower().endswith(("w", "kw", "kwh", "wh", "ah", "v", "a")):
            continue
        models.append(" ".join(x for x in (prefix, number, suffix) if x))

    return uniq([re.sub(r"\s+", " ", value.strip()).upper() for value in models if value.strip()])

def classify(low: str):
    scores = {}
    for category, rules in RULE_WEIGHTS.items():
        scores[category] = sum(weight for phrase, weight in rules.items() if _contains_phrase(low, phrase))
    if not scores or max(scores.values()) == 0:
        return "other", scores
    category = max(scores, key=lambda k: (scores[k], CATEGORY_PRIORITY[k]))
    return category, scores

def analyze(text: str):
    low = normalize_text(text)
    category, _scores = classify(low)
    brands = extract_brands(low)
    product_types = extract_product_types(low)
    models = extract_models(low)
    power = uniq(re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:kw|w|کیلووات|وات)\b', low, re.I))
    energy = uniq(re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:kwh|wh|ah|کیلووات\s*ساعت|وات\s*ساعت|آمپر\s*ساعت)\b', low, re.I))
    phones = uniq(re.findall(r'(?:\+98|0098|0)?9\d{9}', low))
    prices = uniq([
        m.strip()
        for m in re.findall(
            r'((?:\d[\d,.\s]*\d|\d)\s*(?:میلیون|میلیارد)?\s*(?:تومان|تومن|ریال))',
            low,
        )
    ])
    quantities = uniq(re.findall(r'\b\d+\s*(?:عدد|دستگاه|کارتن|پالت|پنل|باتری)\b', low))
    locations = uniq([x for x in LOCATIONS if _contains_phrase(low, x)])
    return {
        "category": category,
        "brands": brands,
        "product_types": product_types,
        "models": models,
        "power_values": power,
        "energy_values": energy,
        "price_values": prices,
        "quantities": quantities,
        "phones": phones,
        "locations": locations,
    }

def dumps(v):
    return json.dumps(v, ensure_ascii=False)
