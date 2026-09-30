import re

TITLE_TERMS = ("solar","pv","سولار","خورشیدی","پنل","اینورتر","باتری","نیروگاه","تجهیزات")
CONTENT_TERMS = ("پنل","اینورتر","باتری","خورشیدی","سولار","نیروگاه","لیتیوم","kw","kwh","growatt","deye","jinko","trina","longi","solis","huawei","fronius","kstar","موجودی","استعلام","فروش","خریدار","قیمت")
SOLAR_STRONG = ("پنل","اینورتر","خورشیدی","سولار","نیروگاه","growatt","deye","jinko","trina","longi","solis","huawei","fronius","kstar","kw","kwh","لیتیوم")
GENERIC_ONLY = ("استعلام","فروش","خریدار","قیمت","موجودی")

def normalize(value):
    return re.sub(r"\s+"," ",(value or "").lower().replace("ي","ی").replace("ك","ک")).strip()

def score_source(title, texts):
    title_n=normalize(title)
    title_hits=sum(1 for term in TITLE_TERMS if term in title_n)
    content_hits=0
    matched=set()
    for text in texts:
        t=normalize(text)
        for term in CONTENT_TERMS:
            if term in t:
                content_hits += 1
                matched.add(term)
    score=title_hits*4 + min(content_hits,20) + min(len(matched),8)
    return score, sorted(matched)

def qualifies_source(title, texts, threshold=8):
    score, matched = score_source(title, texts)
    title_n = normalize(title)
    title_solar = any(term in title_n for term in TITLE_TERMS)
    strong_hits = {term for term in matched if term in SOLAR_STRONG}
    # Generic commerce words alone must never qualify a source.
    qualified = score >= threshold and (title_solar or len(strong_hits) >= 2)
    return qualified, score, matched

def is_market_source(title, texts, threshold=8):
    return qualifies_source(title, texts, threshold)[0]
