import re, json

DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
CHAR_MAP = str.maketrans({
    "ي": "ی", "ى": "ی", "ك": "ک", "ة": "ه", "ۀ": "ه",
    "\u200c": " ", "\u200f": " ", "\u200e": " ",
})

def normalize_text(text: str):
    text = (text or "").translate(CHAR_MAP).translate(DIGIT_MAP).lower()
    text = text.replace("،", ",")
    return re.sub(r"\s+", " ", text).strip()

BRANDS = [
    "trina","jinko","ja solar","longi","growatt","huawei","solis","deye",
    "sofar","must","sako","sunon","gogreen","marsriva","lvtopsun",
    "ترینا","جینکو","لانگی","گرووات","هواوی","سولیس","دی آی","دیه","سوفار","ماست","ساکو","سانون","گوگرین","مارسریوا"
]
LOCATIONS = [
    "خوزستان","اهواز","آبادان","خرمشهر","ماهشهر","دزفول","شوشتر",
    "تهران","کرج","اصفهان","شیراز","تبریز","مشهد","قم","اراک","کرمان",
    "کرمانشاه","ایلام","لرستان","چهارمحال","بوشهر","بندرعباس","یزد"
]
RULES = {
    "inquiry_project": ["استعلام","مناقصه","پروژه","درخواست قیمت","قیمت می خوام","قیمت می خواهم","rfq","پیشنهاد قیمت"],
    "buyer_demand": ["خریدار","خرید دارم","نیاز دارم","نیاز داریم","نیاز فوری","نیازمند","درخواست خرید","مشتری"],
    "stock_availability": ["موجودی","موجود است","آماده تحویل","تحویل فوری","در انبار"],
    "supplier_seller": ["فروش","فروشنده","تامین","تأمین","عرضه","قیمت همکاری","همکار"]
}

def uniq(xs):
    out=[]
    for x in xs:
        if x not in out: out.append(x)
    return out

def analyze(text: str):
    low = normalize_text(text)
    scores = {k: sum(1 for w in words if normalize_text(w) in low) for k, words in RULES.items()}
    category = max(scores, key=scores.get) if max(scores.values(), default=0) else "other"
    brands = uniq([b for b in BRANDS if normalize_text(b) in low])
    power = uniq(re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:kw|w|کیلووات|وات)\b', low, re.I))
    phones = uniq(re.findall(r'(?:\+98|0098|0)?9\d{9}', low))
    # Price-like values near تومان/ریال
    prices = uniq([m.strip() for m in re.findall(r'((?:\d[\d,\. ]{2,})\s*(?:تومان|تومن|ریال))', low)])
    quantities = uniq(re.findall(r'\b\d+\s*(?:عدد|دستگاه|کارتن|پالت|پنل|باتری)\b', low))
    locations = uniq([x for x in LOCATIONS if normalize_text(x) in low])
    return {
        "category": category,
        "brands": brands,
        "power_values": power,
        "price_values": prices,
        "quantities": quantities,
        "phones": phones,
        "locations": locations,
    }

def dumps(v):
    return json.dumps(v, ensure_ascii=False)
