import re, json

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
    "inquiry_project": ["استعلام","مناقصه","پروژه","درخواست قیمت","rfq","پیشنهاد قیمت"],
    "buyer_demand": ["خریدار","خرید دارم","نیاز دارم","نیازمند","درخواست خرید","مشتری"],
    "stock_availability": ["موجودی","موجود است","آماده تحویل","تحویل فوری","در انبار"],
    "supplier_seller": ["فروش","فروشنده","تامین","تأمین","عرضه","قیمت همکاری","همکار"]
}

def uniq(xs):
    out=[]
    for x in xs:
        if x not in out: out.append(x)
    return out

def analyze(text: str):
    low = text.lower()
    scores = {k: sum(1 for w in words if w in low) for k, words in RULES.items()}
    category = max(scores, key=scores.get) if max(scores.values(), default=0) else "other"
    brands = uniq([b for b in BRANDS if b.lower() in low])
    power = uniq(re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:kw|w|کیلووات|وات)\b', low, re.I))
    phones = uniq(re.findall(r'(?:\+98|0098|0)?9\d{9}', text))
    # Price-like values near تومان/ریال
    prices = uniq([m[0].strip() for m in re.findall(r'((?:\d[\d,\. ]{2,})\s*(?:تومان|تومن|ریال))', text)])
    quantities = uniq(re.findall(r'\b\d+\s*(?:عدد|دستگاه|کارتن|پالت|پنل|باتری)\b', text))
    locations = uniq([x for x in LOCATIONS if x in text])
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
