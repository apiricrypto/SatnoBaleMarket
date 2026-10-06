import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from auth import resolve_session, role_allows
from crm_connector import process_outbox, queue_lead, send_outbox_item
from db import connect
from lead_review import save_review
from source_registry import add_source, delete_source, update_source

router = APIRouter()
SESSION_COOKIE_NAME = "satno_staff_session"


def _user(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    return resolve_session(token) if token else None


def require(permission):
    def dependency(request: Request):
        user = _user(request)
        if not user:
            raise HTTPException(status_code=401, detail="authentication required")
        if not role_allows(user["role"], permission):
            raise HTTPException(status_code=403, detail="forbidden")
        return user
    return dependency


require_read = require("read")
require_review = require("lead:send")
require_admin = require("users:manage")


class ReviewIn(BaseModel):
    review_status: str = "reviewed"
    reviewed_category: Optional[str] = None
    product: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    power: Optional[str] = None
    capacity: Optional[str] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    estimated_amount: Optional[int] = None
    estimated_currency: Optional[str] = None
    location: Optional[str] = None
    contact: Optional[str] = None
    priority: Optional[str] = "normal"
    notes: Optional[str] = None


class SourceCreate(BaseModel):
    peer_type: int
    peer_id: int
    title: Optional[str] = None
    score: int = 0
    matched_terms: Optional[str] = None
    enabled: bool = True


class SourceUpdate(BaseModel):
    title: Optional[str] = None
    score: Optional[int] = None
    matched_terms: Optional[str] = None
    enabled: Optional[bool] = None


def _decode_message(row):
    item = dict(row)
    for key in [
        "brands", "product_types", "models", "power_values", "energy_values",
        "price_values", "currency_values", "quantities", "phones", "locations"
    ]:
        try:
            item[key] = json.loads(item.get(key) or "[]")
        except Exception:
            item[key] = []
    return item


@router.get("/api/review/messages")
def review_messages(message_id: Optional[int] = None, review_status: str = "", category: str = "", limit: int = 50, user=Depends(require_read)):
    limit = max(1, min(int(limit), 200))
    sql = """
        SELECT m.*, r.review_status,r.reviewed_category,r.product,r.brand,r.model,
               r.power,r.capacity,r.price,r.currency,r.estimated_amount,
               r.estimated_currency,r.location,r.contact,r.priority,r.notes,
               r.reviewed_by,r.reviewed_at,r.updated_at AS review_updated_at
        FROM messages m LEFT JOIN lead_reviews r ON r.message_id=m.id WHERE 1=1
    """
    args = []
    if message_id is not None:
        sql += " AND m.id=?"; args.append(message_id)
    if category:
        sql += " AND m.category=?"; args.append(category)
    if review_status == "unreviewed":
        sql += " AND r.message_id IS NULL"
    elif review_status:
        sql += " AND r.review_status=?"; args.append(review_status)
    sql += " ORDER BY m.id DESC LIMIT ?"; args.append(limit)
    with connect() as con:
        rows = con.execute(sql, args).fetchall()
    return [_decode_message(row) for row in rows]


@router.patch("/api/review/messages/{message_id}")
def update_review(message_id: int, payload: ReviewIn, user=Depends(require_review)):
    try:
        return save_review(message_id, user["username"], payload.model_dump())
    except ValueError as exc:
        status = 404 if str(exc) == "message not found" else 400
        raise HTTPException(status_code=status, detail=str(exc))


@router.post("/api/leads/{message_id}/queue")
def queue_selected_lead(message_id: int, user=Depends(require_review)):
    try:
        outbox = queue_lead(message_id, user["username"], require_selected=True)
    except ValueError as exc:
        status = 404 if str(exc) == "message not found" else 400
        raise HTTPException(status_code=status, detail=str(exc))
    return {"outbox_id": outbox["id"], "status": outbox["status"], "message_id": outbox["message_id"]}


@router.get("/api/crm/outbox")
def crm_outbox(limit: int = 100, user=Depends(require_read)):
    limit = max(1, min(int(limit), 500))
    with connect() as con:
        rows = con.execute(
            """SELECT id,message_id,requested_by,status,last_error,created_at,sent_at,
                      attempts,last_attempt_at,next_retry_at,crm_lead_id,crm_status,
                      crm_request_id,duplicate,last_http_status
               FROM crm_lead_outbox ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/api/crm/readiness")
def crm_readiness(user=Depends(require_read)):
    import os
    url = bool((os.getenv("SATNO_CRM_LEAD_URL") or "").strip())
    token = len((os.getenv("SATNO_BALE_MARKET_INGEST_TOKEN") or "").strip()) >= 32
    return {"connector": "bale_market", "url_configured": url, "token_configured": token, "live_delivery_enabled": url and token}


@router.post("/api/crm/outbox/{outbox_id}/send")
def crm_send_item(outbox_id: int, user=Depends(require_review)):
    try:
        return send_outbox_item(outbox_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/api/crm/outbox/process")
def crm_process(limit: int = 10, user=Depends(require_admin)):
    return {"results": process_outbox(limit=max(1, min(int(limit), 50)))}


@router.post("/api/sources")
def source_create(payload: SourceCreate, user=Depends(require_admin)):
    try:
        return add_source(**payload.model_dump())
    except ValueError as exc:
        status = 409 if "already exists" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc))


@router.patch("/api/sources/{source_key:path}")
def source_update(source_key: str, payload: SourceUpdate, user=Depends(require_admin)):
    try:
        return update_source(source_key, **payload.model_dump())
    except ValueError as exc:
        status = 404 if str(exc) == "source not found" else 400
        raise HTTPException(status_code=status, detail=str(exc))


@router.delete("/api/sources/{source_key:path}", status_code=204)
def source_delete(source_key: str, user=Depends(require_admin)):
    try:
        delete_source(source_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return None


@router.get("/review", response_class=HTMLResponse)
def review_page(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not role_allows(user["role"], "lead:send"):
        raise HTTPException(status_code=403, detail="forbidden")
    return HTMLResponse("""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>بررسی سرنخ‌ها</title>
<style>body{font-family:system-ui,Tahoma;background:#f6f8fb;margin:0;color:#152235}.wrap{max-width:1200px;margin:auto;padding:20px}.card{background:#fff;border:1px solid #e6eaf0;border-radius:14px;padding:14px;margin:10px 0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}input,select,textarea,button{box-sizing:border-box;width:100%;padding:9px;border:1px solid #d7dde7;border-radius:8px}textarea{min-height:80px}.meta{font-size:12px;color:#667085}.actions{display:flex;gap:8px;margin-top:10px}.actions button{width:auto}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style></head><body><div class="wrap"><p><a href="/">← داشبورد</a> | <a href="/crm/outbox">صندوق CRM</a></p><h2>بررسی انسانی و انتخاب سرنخ</h2><div class="card"><select id="filter"><option value="unreviewed">بررسی‌نشده</option><option value="">همه</option><option value="reviewed">بررسی‌شده</option><option value="selected">انتخاب‌شده</option><option value="rejected">ردشده</option></select><button onclick="load()">بارگذاری</button></div><div id="list"></div></div>
<script>
var requestedId=new URLSearchParams(location.search).get('message_id');function esc(v){var d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML}function first(a){return a&&a.length?a[0]:''}
async function load(){var url=requestedId?'/api/review/messages?message_id='+encodeURIComponent(requestedId):'/api/review/messages?limit=50&review_status='+encodeURIComponent(filter.value);var r=await fetch(url),rows=await r.json(),html='';rows.forEach(function(x){html+='<div class="card" data-id="'+x.id+'"><div class="meta">#'+x.id+' • '+esc(x.chat_name||'-')+' • '+esc(x.sender_name||x.sender_id||'-')+' • '+esc(x.sent_at||'')+'</div><p>'+esc(x.text)+'</p><div class="grid"><select class="category"><option value="supplier_seller">تأمین‌کننده/فروشنده</option><option value="stock_availability">موجودی/فروش</option><option value="buyer_demand">تقاضای خرید</option><option value="inquiry_project">استعلام/پروژه</option><option value="other">سایر</option></select><input class="product" placeholder="محصول" value="'+esc(x.product||first(x.product_types))+'"><input class="brand" placeholder="برند" value="'+esc(x.brand||first(x.brands))+'"><input class="model" placeholder="مدل" value="'+esc(x.model||first(x.models))+'"><input class="power" placeholder="توان" value="'+esc(x.power||first(x.power_values))+'"><input class="capacity" placeholder="ظرفیت" value="'+esc(x.capacity||first(x.energy_values))+'"><input class="price" placeholder="قیمت متن پیام" value="'+esc(x.price||first(x.price_values))+'"><input class="currency" placeholder="واحد قیمت" value="'+esc(x.currency||first(x.currency_values))+'"><input class="location" placeholder="محل" value="'+esc(x.location||first(x.locations))+'"><input class="contact" placeholder="تماس" value="'+esc(x.contact||first(x.phones))+'"><input class="estimated_amount" type="number" min="0" placeholder="مبلغ نرمال‌شده CRM"><input class="estimated_currency" maxlength="3" placeholder="ISO مثل IRR"><select class="priority"><option>normal</option><option>low</option><option>high</option><option>urgent</option></select></div><textarea class="notes" placeholder="یادداشت بررسی">'+esc(x.notes||'')+'</textarea><div class="actions"><button onclick="save(this,\'reviewed\')">ثبت بررسی</button><button onclick="save(this,\'selected\')">انتخاب برای CRM</button><button onclick="save(this,\'rejected\')">رد</button><button onclick="queueLead(this)">قرار دادن در صف CRM</button><span class="result"></span></div></div>'});list.innerHTML=html;rows.forEach(function(x){var c=document.querySelector('[data-id="'+x.id+'"]');c.querySelector('.category').value=x.reviewed_category||x.category||'other';c.querySelector('.priority').value=x.priority||'normal';if(x.estimated_amount!=null)c.querySelector('.estimated_amount').value=x.estimated_amount;if(x.estimated_currency)c.querySelector('.estimated_currency').value=x.estimated_currency})}
function body(c,status){function g(s){return c.querySelector('.'+s).value.trim()}return{review_status:status,reviewed_category:g('category'),product:g('product')||null,brand:g('brand')||null,model:g('model')||null,power:g('power')||null,capacity:g('capacity')||null,price:g('price')||null,currency:g('currency')||null,estimated_amount:g('estimated_amount')?Number(g('estimated_amount')):null,estimated_currency:g('estimated_currency')||null,location:g('location')||null,contact:g('contact')||null,priority:g('priority'),notes:g('notes')||null}}
async function save(btn,status){var c=btn.closest('.card'),id=c.dataset.id,r=await fetch('/api/review/messages/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body(c,status))}),d=await r.json();c.querySelector('.result').textContent=r.ok?'ثبت شد':(d.detail||'خطا');return r.ok}
async function queueLead(btn){var c=btn.closest('.card'),id=c.dataset.id;if(!(await save(btn,'selected')))return;var r=await fetch('/api/leads/'+id+'/queue',{method:'POST'}),d=await r.json();c.querySelector('.result').textContent=r.ok?('در صف CRM #'+d.outbox_id):(d.detail||'خطا')}
load();
</script></body></html>""")


@router.get("/sources/manage", response_class=HTMLResponse)
def sources_page(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not role_allows(user["role"], "users:manage"):
        raise HTTPException(status_code=403, detail="forbidden")
    return HTMLResponse("""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مدیریت منابع بله</title><style>body{font-family:system-ui,Tahoma;background:#f6f8fb;margin:0}.wrap{max-width:1200px;margin:auto;padding:20px}.card{background:white;padding:14px;border:1px solid #e6eaf0;border-radius:12px;margin:10px 0}input,button{padding:8px;margin:2px;border:1px solid #ddd;border-radius:7px}table{width:100%;border-collapse:collapse}td,th{padding:7px;border-bottom:1px solid #eee;text-align:right}</style></head><body><div class="wrap"><p><a href="/">← داشبورد</a></p><h2>منابع شناسایی‌شده بله</h2><form id="add" class="card"><input id="pt" type="number" value="2" placeholder="peer type"><input id="pid" type="number" placeholder="peer id" required><input id="title" placeholder="عنوان"><input id="score" type="number" value="0" placeholder="امتیاز"><input id="terms" placeholder="کلیدواژه‌ها"><button>افزودن دستی</button></form><div class="card"><table><thead><tr><th>کلید</th><th>عنوان</th><th>امتیاز</th><th>فعال</th><th>کلیدواژه</th><th>عملیات</th></tr></thead><tbody id="rows"></tbody></table></div></div><script>function esc(v){var d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML}async function load(){var r=await fetch('/api/sources'),a=await r.json(),h='';a.forEach(function(x){h+='<tr data-k="'+esc(x.source_key)+'"><td>'+esc(x.source_key)+'</td><td><input class="t" value="'+esc(x.title||'')+'"></td><td><input class="s" type="number" value="'+esc(x.score||0)+'"></td><td><input class="a" type="checkbox" '+(x.enabled?'checked':'')+'></td><td><input class="m" value="'+esc(x.matched_terms||'')+'"></td><td><button onclick="saveRow(this)">ذخیره</button><button onclick="delRow(this)">حذف</button></td></tr>'});rows.innerHTML=h}async function saveRow(b){var tr=b.closest('tr'),k=tr.dataset.k;await fetch('/api/sources/'+encodeURIComponent(k),{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:tr.querySelector('.t').value,score:Number(tr.querySelector('.s').value),enabled:tr.querySelector('.a').checked,matched_terms:tr.querySelector('.m').value})});load()}async function delRow(b){if(!confirm('منبع حذف شود؟'))return;var tr=b.closest('tr');await fetch('/api/sources/'+encodeURIComponent(tr.dataset.k),{method:'DELETE'});load()}add.onsubmit=async function(ev){ev.preventDefault();var r=await fetch('/api/sources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({peer_type:Number(pt.value),peer_id:Number(pid.value),title:title.value||null,score:Number(score.value||0),matched_terms:terms.value||null,enabled:true})});if(!r.ok)alert((await r.json()).detail||'خطا');else{ev.target.reset();pt.value=2;score.value=0;load()}};load();</script></body></html>""")


@router.get("/crm/outbox", response_class=HTMLResponse)
def crm_outbox_page(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse("""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRM Outbox</title><style>body{font-family:system-ui,Tahoma;background:#f6f8fb;margin:0}.wrap{max-width:1200px;margin:auto;padding:20px}.card{background:white;padding:14px;border:1px solid #e6eaf0;border-radius:12px;margin:10px 0}table{width:100%;border-collapse:collapse}td,th{padding:7px;border-bottom:1px solid #eee;text-align:right;font-size:13px}button{padding:7px}</style></head><body><div class="wrap"><p><a href="/">← داشبورد</a> | <a href="/review">بررسی سرنخ‌ها</a></p><h2>صف اتصال SATNO CRM</h2><div id="ready" class="card"></div><div class="card"><table><thead><tr><th>ID</th><th>پیام</th><th>وضعیت</th><th>تلاش</th><th>CRM ID</th><th>HTTP</th><th>خطا</th><th>عملیات</th></tr></thead><tbody id="rows"></tbody></table></div></div><script>function esc(v){var d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML}async function load(){var a=await fetch('/api/crm/readiness'),b=await fetch('/api/crm/outbox'),rd=await a.json(),o=await b.json();ready.textContent='Connector: '+rd.connector+' | URL: '+(rd.url_configured?'تنظیم':'تنظیم نیست')+' | Token: '+(rd.token_configured?'تنظیم':'تنظیم نیست')+' | ارسال زنده: '+(rd.live_delivery_enabled?'فعال':'غیرفعال');var h='';o.forEach(function(x){h+='<tr><td>'+x.id+'</td><td>'+x.message_id+'</td><td>'+esc(x.status)+'</td><td>'+(x.attempts||0)+'</td><td>'+esc(x.crm_lead_id||'')+'</td><td>'+esc(x.last_http_status||'')+'</td><td>'+esc(x.last_error||'')+'</td><td><button onclick="sendOne('+x.id+')">ارسال/تلاش مجدد</button></td></tr>'});rows.innerHTML=h}async function sendOne(id){var r=await fetch('/api/crm/outbox/'+id+'/send',{method:'POST'}),d=await r.json();alert(d.status||d.detail||'نتیجه ثبت شد');load()}load();</script></body></html>""")
