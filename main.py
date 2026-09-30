from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from db import init_db, connect
from classifier import analyze, dumps
from dedup import make_dedup_key
from display_utils import format_tehran_jalali, normalize_datetime_filter
from search_utils import normalize_search_text, query_terms
from time_utils import parse_message_datetime
import json

app = FastAPI(title="SATNO Bale Market Intelligence", version="0.2.0")

class MessageIn(BaseModel):
    external_id: Optional[str] = None
    chat_name: Optional[str] = None
    sender_name: Optional[str] = None
    sender_id: Optional[str] = None
    sender_username: Optional[str] = None
    sender_link: Optional[str] = None
    text: str
    sent_at: Optional[str] = None

@app.on_event("startup")
def startup():
    init_db()

def save_message(m: MessageIn):
    a = analyze(m.text)
    dedup_key = make_dedup_key(
        external_id=m.external_id,
        chat_name=m.chat_name,
        sender_name=m.sender_name,
        sent_at=m.sent_at,
        text=m.text,
    )
    with connect() as con:
        cur = con.execute("""
        INSERT OR IGNORE INTO messages
        (external_id,chat_name,sender_name,sender_id,sender_username,sender_link,text,sent_at,category,brands,product_types,models,power_values,energy_values,price_values,quantities,phones,locations,dedup_key)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            m.external_id,m.chat_name,m.sender_name,m.sender_id,m.sender_username,m.sender_link,m.text,m.sent_at,a["category"],
            dumps(a["brands"]),dumps(a["product_types"]),dumps(a["models"]),
            dumps(a["power_values"]),dumps(a["energy_values"]),dumps(a["price_values"]),
            dumps(a["quantities"]),dumps(a["phones"]),dumps(a["locations"]),dedup_key
        ))
        inserted_id = cur.lastrowid if cur.rowcount == 1 else None
        return inserted_id, a

@app.get("/health")
def health():
    return {"status":"ok","service":"satno-bale-market","version":"0.2.0"}

@app.post("/api/messages")
def create_message(m: MessageIn):
    mid, a = save_message(m)
    return {"id": mid, "analysis": a}

@app.get("/api/messages")
def list_messages(q: str = "", category: str = "", sender_id: str = "", date_from: str = "", date_to: str = "", limit: int = Query(100, ge=1, le=500)):
    sql = "SELECT * FROM messages WHERE 1=1"
    args=[]
    if q:
        searchable = "LOWER(COALESCE(text,'') || ' ' || COALESCE(chat_name,'') || ' ' || COALESCE(sender_name,'') || ' ' || COALESCE(sender_username,'') || ' ' || COALESCE(brands,'') || ' ' || COALESCE(product_types,'') || ' ' || COALESCE(models,'') || ' ' || COALESCE(power_values,'') || ' ' || COALESCE(energy_values,'') || ' ' || COALESCE(price_values,'') || ' ' || COALESCE(quantities,'') || ' ' || COALESCE(locations,''))"
        for variants in query_terms(q):
            sql += " AND (" + " OR ".join([searchable + " LIKE ?" for _ in variants]) + ")"
            args.extend([f"%{v}%" for v in variants])
    if category:
        sql += " AND category=?"; args.append(category)
    if sender_id:
        sql += " AND sender_id=?"; args.append(sender_id)
    normalized_from = normalize_datetime_filter(date_from)
    normalized_to = normalize_datetime_filter(date_to, end=True)
    # Historical Bale rows may contain legacy numeric/non-ISO timestamps.
    # Fetch candidates first and apply date bounds in Python after normalizing each row.
    sql += " ORDER BY id DESC"
    with connect() as con:
        rows=[dict(r) for r in con.execute(sql,args).fetchall()]
    if normalized_from or normalized_to:
        from_dt = parse_message_datetime(normalized_from) if normalized_from else None
        to_dt = parse_message_datetime(normalized_to) if normalized_to else None
        filtered=[]
        for r in rows:
            dt=parse_message_datetime(r.get("sent_at")) or parse_message_datetime(r.get("created_at"))
            if not dt:
                continue
            if from_dt and dt < from_dt:
                continue
            if to_dt and dt > to_dt:
                continue
            filtered.append(r)
        rows=filtered
    rows=rows[:limit]
    for r in rows:
        for k in ["brands","product_types","models","power_values","energy_values","price_values","quantities","phones","locations"]:
            try: r[k]=json.loads(r[k] or "[]")
            except Exception: r[k]=[]
        r["sent_at_display"] = format_tehran_jalali(r.get("sent_at") or r.get("created_at"))
    return rows

@app.get("/api/stats")
def stats():
    with connect() as con:
        total=con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        cats={r[0]:r[1] for r in con.execute("SELECT category,COUNT(*) FROM messages GROUP BY category")}
    return {"total": total, "categories": cats}

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse("""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SATNO Bale Market Intelligence</title>
<style>
body{font-family:system-ui,Tahoma;background:#f6f8fb;margin:0;color:#152235}.wrap{max-width:1200px;margin:auto;padding:20px}
h1{font-size:24px}.sub{color:#667085}.bar{display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr auto auto;gap:8px;margin:16px 0}
input,select,button{padding:11px;border:1px solid #d7dde7;border-radius:10px;background:white;min-width:0}
button{cursor:pointer}.stats,.card{background:white;border:1px solid #e6eaf0;border-radius:14px;padding:14px;margin:10px 0}
.meta{font-size:12px;color:#667085}.tag{display:inline-block;background:#eef3f8;border-radius:20px;padding:3px 8px;margin:3px;font-size:12px}
a{color:#0866c6;text-decoration:none}.error{color:#b42318}.hint{font-size:12px;color:#667085;margin-top:-8px}
@media(max-width:900px){.bar{grid-template-columns:1fr 1fr}.bar #q{grid-column:1/-1}}
</style></head><body><div class="wrap">
<h1>SATNO | هوش بازار بله</h1><div class="sub">نسخه آزمایشی 0.3 — جستجوی بازار، تاریخ شمسی و شناسه خریدار/فروشنده</div>
<div id="stats" class="stats">در حال بارگذاری...</div>
<div class="bar">
<input id="q" placeholder="جستجو: برند، محصول، شهر، متن...">
<select id="cat"><option value="">همه دسته‌ها</option><option value="supplier_seller">فروشنده/تأمین‌کننده</option><option value="buyer_demand">خریدار/تقاضا</option><option value="stock_availability">موجودی</option><option value="inquiry_project">استعلام/پروژه</option><option value="other">سایر</option></select>
<input id="sender" placeholder="ID خریدار/فروشنده">
<input id="from" inputmode="numeric" placeholder="از: ۱۴۰۵/۰۷/۰۱">
<input id="to" inputmode="numeric" placeholder="تا: ۱۴۰۵/۰۷/۰۸">
<button id="searchBtn" type="button">جستجو</button>
<button id="clearBtn" type="button">پاک‌کردن</button>
</div>
<div class="hint">تاریخ را به صورت شمسی وارد کنید؛ مثال: ۱۴۰۵/۰۷/۰۸</div>
<div id="list"></div></div>
<script>
const labels={supplier_seller:'فروشنده/تأمین‌کننده',buyer_demand:'خریدار/تقاضا',stock_availability:'موجودی',inquiry_project:'استعلام/پروژه',other:'سایر'};
function escapeHtml(v){const d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML;}
function senderHtml(r){
 const label=escapeHtml(r.sender_username||r.sender_name||r.sender_id||'-');
 if(r.sender_link && /^https:\/\/ble\.ir\/[A-Za-z0-9_.-]+\/?$/.test(r.sender_link)){
   return '<a href="'+escapeHtml(r.sender_link)+'" target="_blank" rel="noopener noreferrer">بازکردن در بله: '+label+'</a>';
 }
 return label+(r.sender_id?' • ID: '+escapeHtml(r.sender_id):'');
}
function params(){
 const p=new URLSearchParams();
 const values={q:'q',category:'cat',sender_id:'sender',date_from:'from',date_to:'to'};
 for(const [key,id] of Object.entries(values)){const v=document.getElementById(id).value.trim();if(v)p.set(key,v);}
 return p;
}
async function load(){
 const list=document.getElementById('list');
 list.innerHTML='<div class="stats">در حال جستجو...</div>';
 try{
   const [sr,rr]=await Promise.all([fetch('/api/stats'),fetch('/api/messages?'+params().toString())]);
   if(!sr.ok||!rr.ok) throw new Error('HTTP '+sr.status+'/'+rr.status);
   const s=await sr.json(), rows=await rr.json();
   document.getElementById('stats').textContent='کل پیام‌ها: '+s.total+' | نتایج جستجو: '+rows.length;
   list.innerHTML=rows.length?rows.map(r=>'<div class="card"><div class="meta">'+escapeHtml(r.chat_name||'-')+' • '+senderHtml(r)+' • '+escapeHtml(r.sent_at_display||r.sent_at||'')+'</div><p>'+escapeHtml(r.text)+'</p><span class="tag">'+escapeHtml(labels[r.category]||r.category)+'</span> '+(r.brands||[]).map(x=>'<span class="tag">'+escapeHtml(x)+'</span>').join('')+' '+(r.models||[]).map(x=>'<span class="tag">مدل: '+escapeHtml(x)+'</span>').join('')+' '+(r.power_values||[]).map(x=>'<span class="tag">توان: '+escapeHtml(x)+'</span>').join('')+' '+(r.price_values||[]).map(x=>'<span class="tag">قیمت: '+escapeHtml(x)+'</span>').join('')+' '+(r.locations||[]).map(x=>'<span class="tag">'+escapeHtml(x)+'</span>').join('')+'</div>').join(''):'<div class="stats">نتیجه‌ای پیدا نشد.</div>';
 }catch(e){list.innerHTML='<div class="stats error">خطا در جستجو: '+escapeHtml(e.message)+'</div>';}
}
function clearFilters(){['q','sender','from','to'].forEach(id=>document.getElementById(id).value='');document.getElementById('cat').value='';load();}
document.getElementById('searchBtn').addEventListener('click',load);
document.getElementById('clearBtn').addEventListener('click',clearFilters);
['q','sender','from','to'].forEach(id=>document.getElementById(id).addEventListener('keydown',e=>{if(e.key==='Enter')load();}));
load();
</script></body></html>""")
