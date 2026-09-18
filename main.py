from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from db import init_db, connect
from classifier import analyze, dumps
import json

app = FastAPI(title="SATNO Bale Market Intelligence", version="0.2.0")

class MessageIn(BaseModel):
    external_id: Optional[str] = None
    chat_name: Optional[str] = None
    sender_name: Optional[str] = None
    text: str
    sent_at: Optional[str] = None

@app.on_event("startup")
def startup():
    init_db()

def save_message(m: MessageIn):
    a = analyze(m.text)
    with connect() as con:
        cur = con.execute('''
        INSERT OR IGNORE INTO messages
        (external_id,chat_name,sender_name,text,sent_at,category,brands,power_values,price_values,quantities,phones,locations)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (m.external_id,m.chat_name,m.sender_name,m.text,m.sent_at,a["category"],
              dumps(a["brands"]),dumps(a["power_values"]),dumps(a["price_values"]),
              dumps(a["quantities"]),dumps(a["phones"]),dumps(a["locations"])))
        return cur.lastrowid, a

@app.get("/health")
def health():
    return {"status":"ok","service":"satno-bale-market","version":"0.2.0"}

@app.post("/api/messages")
def create_message(m: MessageIn):
    mid, a = save_message(m)
    return {"id": mid, "analysis": a}

@app.get("/api/messages")
def list_messages(q: str = "", category: str = "", limit: int = Query(100, ge=1, le=500)):
    sql = "SELECT * FROM messages WHERE 1=1"
    args=[]
    if q:
        sql += " AND (text LIKE ? OR chat_name LIKE ? OR sender_name LIKE ? OR brands LIKE ? OR locations LIKE ?)"
        like=f"%{q}%"; args += [like,like,like,like,like]
    if category:
        sql += " AND category=?"; args.append(category)
    sql += " ORDER BY COALESCE(sent_at, created_at) DESC LIMIT ?"; args.append(limit)
    with connect() as con:
        rows=[dict(r) for r in con.execute(sql,args).fetchall()]
    for r in rows:
        for k in ["brands","power_values","price_values","quantities","phones","locations"]:
            try: r[k]=json.loads(r[k] or "[]")
            except Exception: r[k]=[]
    return rows

@app.get("/api/stats")
def stats():
    with connect() as con:
        total=con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        cats={r[0]:r[1] for r in con.execute("SELECT category,COUNT(*) FROM messages GROUP BY category")}
    return {"total": total, "categories": cats}

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse('''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SATNO Bale Market Intelligence</title>
<style>
body{font-family:system-ui,Tahoma;background:#f6f8fb;margin:0;color:#152235}.wrap{max-width:1100px;margin:auto;padding:20px}
h1{font-size:24px}.sub{color:#667085}.bar{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}
input,select,button{padding:11px;border:1px solid #d7dde7;border-radius:10px;background:white}
input{flex:1;min-width:220px}button{cursor:pointer}.stats,.card{background:white;border:1px solid #e6eaf0;border-radius:14px;padding:14px;margin:10px 0}
.meta{font-size:12px;color:#667085}.tag{display:inline-block;background:#eef3f8;border-radius:20px;padding:3px 8px;margin:3px;font-size:12px}
</style></head><body><div class="wrap">
<h1>SATNO | هوش بازار بله</h1><div class="sub">نسخه MVP 0.2 — ساختار Flat مناسب GitHub موبایل</div>
<div id="stats" class="stats">در حال بارگذاری...</div>
<div class="bar"><input id="q" placeholder="جستجو: برند، محصول، شهر، متن..."><select id="cat">
<option value="">همه دسته‌ها</option><option value="supplier_seller">فروشنده/تأمین‌کننده</option>
<option value="buyer_demand">خریدار/تقاضا</option><option value="stock_availability">موجودی</option>
<option value="inquiry_project">استعلام/پروژه</option><option value="other">سایر</option></select><button onclick="load()">جستجو</button></div>
<div id="list"></div></div>
<script>
const labels={supplier_seller:'فروشنده/تأمین‌کننده',buyer_demand:'خریدار/تقاضا',stock_availability:'موجودی',inquiry_project:'استعلام/پروژه',other:'سایر'};
async function load(){
 let q=encodeURIComponent(document.getElementById('q').value),c=encodeURIComponent(document.getElementById('cat').value);
 let s=await (await fetch('/api/stats')).json(); document.getElementById('stats').innerText=`کل پیام‌ها: ${s.total}`;
 let rows=await (await fetch(`/api/messages?q=${q}&category=${c}`)).json();
 document.getElementById('list').innerHTML=rows.map(r=>`<div class="card"><div class="meta">${r.chat_name||'-'} • ${r.sender_name||'-'} • ${r.sent_at||''}</div>
 <p>${escapeHtml(r.text)}</p><span class="tag">${labels[r.category]||r.category}</span>
 ${(r.brands||[]).map(x=>`<span class="tag">${x}</span>`).join('')} ${(r.locations||[]).map(x=>`<span class="tag">${x}</span>`).join('')}</div>`).join('');
}
function escapeHtml(s){return (s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));}
document.getElementById('q').addEventListener('keydown',e=>{if(e.key==='Enter')load()}); load();
</script></body></html>''')
