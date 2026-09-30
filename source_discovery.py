import re

TITLE_TERMS = ("solar","pv","سولار","خورشیدی","پنل","اینورتر","باتری","نیروگاه","تجهیزات")
CONTENT_TERMS = ("پنل","اینورتر","باتری","خورشیدی","سولار","نیروگاه","لیتیوم","kw","kwh","growatt","deye","jinko","trina","longi","solis","huawei","fronius","kstar","موجودی","استعلام","فروش","خریدار","قیمت")

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

def is_market_source(title, texts, threshold=4):
    score,_=score_source(title,texts)
    return score >= threshold
