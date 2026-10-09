import os
from fastapi import FastAPI, Query, Request, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional
from db import init_db, connect
from classifier import analyze, dumps
from dedup import make_dedup_key
from display_utils import format_tehran_jalali, normalize_datetime_filter
from search_utils import normalize_search_text, query_terms, message_search_score
from time_utils import parse_message_datetime
from auth import authenticate_user, create_session, resolve_session, revoke_session, role_allows, create_user, list_users, update_user
from crm_connector import queue_lead
from operations_routes import router as operations_router
import json

app = FastAPI(title="SATNO Bale Market Intelligence", version="0.5.0")
app.include_router(operations_router)

SESSION_COOKIE_NAME = "satno_staff_session"
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

class LoginIn(BaseModel):
    username: str
    password: str

def _session_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    return resolve_session(token) if token else None

def require_permission(permission):
    def dependency(request: Request):
        user = _session_user(request)
        if not user:
            raise HTTPException(status_code=401, detail="authentication required")
        if not role_allows(user["role"], permission):
            raise HTTPException(status_code=403, detail="forbidden")
        return user
    return dependency

require_read = require_permission("read")
require_message_write = require_permission("message:write")
require_users_manage = require_permission("users:manage")
require_lead_send = require_permission("lead:send")

class StaffUserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    display_name: Optional[str] = None

class StaffUserUpdate(BaseModel):
    role: Optional[str] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

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
        (external_id,chat_name,sender_name,sender_id,sender_username,sender_link,text,sent_at,category,brands,product_types,models,power_values,energy_values,price_values,currency_values,quantities,phones,locations,dedup_key)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            m.external_id,m.chat_name,m.sender_name,m.sender_id,m.sender_username,m.sender_link,m.text,m.sent_at,a["category"],
            dumps(a["brands"]),dumps(a["product_types"]),dumps(a["models"]),
            dumps(a["power_values"]),dumps(a["energy_values"]),dumps(a["price_values"]),dumps(a["currency_values"]),
            dumps(a["quantities"]),dumps(a["phones"]),dumps(a["locations"]),dedup_key
        ))
        inserted_id = cur.lastrowid if cur.rowcount == 1 else None
        return inserted_id, a

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _session_user(request):
        return RedirectResponse("/", status_code=303)
    return HTMLResponse("""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ورود پرسنل | SATNO Bale Market</title>
<style>
body{font-family:system-ui,Tahoma;background:#f6f8fb;color:#152235;display:grid;place-items:center;min-height:100vh;margin:0}
.box{width:min(380px,90vw);background:white;border:1px solid #e6eaf0;border-radius:16px;padding:22px;box-shadow:0 10px 30px #0001}
input,button{box-sizing:border-box;width:100%;padding:12px;margin:7px 0;border:1px solid #d7dde7;border-radius:10px}
button{cursor:pointer;background:#102d3d;color:white}.err{color:#b42318;min-height:24px}
</style></head><body><form class="box" id="loginForm">
<h2>ورود پرسنل ساتنو</h2><input id="username" autocomplete="username" placeholder="نام کاربری" required>
<input id="password" type="password" autocomplete="current-password" placeholder="رمز عبور" required>
<button type="submit">ورود</button><div id="err" class="err"></div></form>
<script>
document.getElementById('loginForm').addEventListener('submit',async(e)=>{
 e.preventDefault();const err=document.getElementById('err');err.textContent='';
 const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username.value,password:password.value})});
 if(r.ok){location.href='/';return;} err.textContent='نام کاربری یا رمز عبور نادرست است.';
});
</script></body></html>""")

@app.post("/api/auth/login")
def login(payload: LoginIn, response: Response):
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_session(user["id"])
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=8 * 60 * 60,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return {"username": user["username"], "display_name": user["display_name"], "role": user["role"]}

@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        revoke_session(token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"ok": True}

@app.get("/api/auth/me")
def auth_me(user=Depends(require_read)):
    return {"username": user["username"], "display_name": user["display_name"], "role": user["role"]}

@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request):
    user = _session_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not role_allows(user["role"], "users:manage"):
        raise HTTPException(status_code=403, detail="forbidden")
    return HTMLResponse("""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>مدیریت کاربران | SATNO Bale Market</title>
<style>
body{font-family:system-ui,Tahoma;background:#f6f8fb;color:#152235;margin:0}.wrap{max-width:1000px;margin:auto;padding:20px}
.card{background:#fff;border:1px solid #e6eaf0;border-radius:14px;padding:14px;margin:10px 0}
input,select,button{padding:9px;border:1px solid #d7dde7;border-radius:9px;margin:3px}button{cursor:pointer}
table{width:100%;border-collapse:collapse;background:white}th,td{padding:8px;border-bottom:1px solid #eee;text-align:right}
.err{color:#b42318}a{color:#0866c6;text-decoration:none}
</style></head><body><div class="wrap"><h2>مدیریت کاربران پرسنل</h2>
<p><a href="/">← داشبورد</a></p>
<form id="create" class="card"><input id="username" placeholder="نام کاربری" required>
<input id="display_name" placeholder="نام نمایشی"><input id="password" type="password" placeholder="رمز عبور (حداقل ۱۰ کاراکتر)" required>
<select id="role"><option value="viewer">viewer</option><option value="sales">sales</option><option value="admin">admin</option></select>
<button type="submit">ایجاد کاربر</button><span id="msg"></span></form>
<div class="card"><table><thead><tr><th>کاربر</th><th>نام</th><th>نقش</th><th>فعال</th><th>عملیات</th></tr></thead><tbody id="rows"></tbody></table></div>
</div><script>
function e(v){const d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML;}
async function load(){
 const r=await fetch('/api/admin/users'); if(!r.ok)return; const users=await r.json();
 rows.innerHTML=users.map(u=>'<tr><td>'+e(u.username)+'</td><td><input id="n'+u.id+'" value="'+e(u.display_name||'')+'"></td><td><select id="r'+u.id+'"><option '+(u.role==='viewer'?'selected':'')+'>viewer</option><option '+(u.role==='sales'?'selected':'')+'>sales</option><option '+(u.role==='admin'?'selected':'')+'>admin</option></select></td><td><input id="a'+u.id+'" type="checkbox" '+(u.is_active?'checked':'')+'></td><td><button onclick="save('+u.id+')">ذخیره</button><button onclick="resetPw('+u.id+')">رمز جدید</button></td></tr>').join('');
}
async function save(id){
 const body={role:document.getElementById('r'+id).value,display_name:document.getElementById('n'+id).value,is_active:document.getElementById('a'+id).checked};
 const r=await fetch('/api/admin/users/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!r.ok){alert((await r.json()).detail||'خطا');return;} load();
}
async function resetPw(id){
 const p=prompt('رمز جدید (حداقل ۱۰ کاراکتر):'); if(!p)return;
 const r=await fetch('/api/admin/users/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:p})});
 if(!r.ok){alert((await r.json()).detail||'خطا');return;} alert('رمز تغییر کرد و Sessionهای قبلی لغو شدند.');
}
document.getElementById('create').addEventListener('submit',async(ev)=>{
 ev.preventDefault(); msg.textContent='';
 const r=await fetch('/api/admin/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username.value,display_name:display_name.value,password:password.value,role:role.value})});
 if(!r.ok){msg.textContent=(await r.json()).detail||'خطا';return;}
 ev.target.reset(); load();
});
load();
</script></body></html>""")

@app.get("/api/admin/users")
def admin_list_users(user=Depends(require_users_manage)):
    return list_users()

@app.post("/api/admin/users", status_code=201)
def admin_create_user(payload: StaffUserCreate, user=Depends(require_users_manage)):
    try:
        create_user(payload.username, payload.password, payload.role, payload.display_name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    created = next((u for u in list_users() if u["username"] == payload.username.strip().lower()), None)
    return created

@app.patch("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: StaffUserUpdate, user=Depends(require_users_manage)):
    try:
        return update_user(
            user_id,
            role=payload.role,
            display_name=payload.display_name,
            is_active=payload.is_active,
            password=payload.password,
        )
    except ValueError as exc:
        message = str(exc)
        status = 404 if message == "user not found" else 400
        raise HTTPException(status_code=status, detail=message)

@app.get("/health")
def health():
    return {"status":"ok","service":"satno-bale-market","version":"0.5.0"}

@app.post("/api/messages")
def create_message(m: MessageIn, user=Depends(require_message_write)):
    mid, a = save_message(m)
    return {"id": mid, "analysis": a}

@app.get("/api/messages")
def list_messages(q: str = "", category: str = "", sender_id: str = "", date_from: str = "", date_to: str = "", limit: int = Query(100, ge=1, le=500), user=Depends(require_read)):
    sql = "SELECT * FROM messages WHERE 1=1"
    args=[]
    if category:
        sql += " AND category=?"; args.append(category)
    if sender_id:
        sid = sender_id.strip().lstrip("@")
        sql += " AND (sender_id LIKE ? OR LOWER(COALESCE(sender_username,'')) LIKE ? OR LOWER(COALESCE(sender_name,'')) LIKE ?)"
        like_sid=f"%{sid}%"; args += [like_sid, like_sid.lower(), like_sid.lower()]
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
    if q:
        scored=[]
        for r in rows:
            score=message_search_score(r, q)
            if score > 0:
                r["search_score"]=score
                scored.append(r)
        rows=sorted(scored, key=lambda r: (r.get("search_score",0), r.get("id") or 0), reverse=True)
    rows=rows[:limit]
    for r in rows:
        for k in ["brands","product_types","models","power_values","energy_values","price_values","currency_values","quantities","phones","locations"]:
            try: r[k]=json.loads(r[k] or "[]")
            except Exception: r[k]=[]
        r["sent_at_display"] = format_tehran_jalali(r.get("sent_at") or r.get("created_at"))
        r["sender_clickable"] = bool(r.get("sender_link"))
    return rows

@app.get("/api/sources")
def sources(user=Depends(require_read)):
    with connect() as con:
        rows = [dict(r) for r in con.execute(
            """
            SELECT source_key,title,peer_type,peer_id,score,matched_terms,enabled,discovered_at,last_seen_at
            FROM source_registry
            ORDER BY enabled DESC, score DESC, title
            """
        ).fetchall()]
    return rows

@app.get("/api/sync/status")
def sync_status(user=Depends(require_read)):
    with connect() as con:
        latest = con.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        totals = con.execute(
            "SELECT COALESCE(SUM(messages_scanned),0),COALESCE(SUM(messages_saved),0),COALESCE(SUM(completed),0),COUNT(*) FROM backfill_state"
        ).fetchone()
        sender_stats = con.execute(
            "SELECT COUNT(*),SUM(CASE WHEN sender_username IS NOT NULL AND sender_username!='' THEN 1 ELSE 0 END) FROM sender_directory"
        ).fetchone()
        outbox = con.execute(
            "SELECT status,COUNT(*) FROM crm_lead_outbox GROUP BY status"
        ).fetchall()
    return {
        "latest_sync": dict(latest) if latest else None,
        "history_scanned": totals[0],
        "history_saved": totals[1],
        "history_completed_sources": totals[2],
        "history_sources": totals[3],
        "senders_cached": sender_stats[0] or 0,
        "senders_with_username": sender_stats[1] or 0,
        "crm_outbox": {r[0]: r[1] for r in outbox},
    }

@app.get("/status", response_class=HTMLResponse)
def status_page(request: Request):
    user = _session_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse("""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>وضعیت منابع | SATNO Bale Market</title>
<style>
body{font-family:system-ui,Tahoma;background:#f6f8fb;color:#152235;margin:0}.wrap{max-width:1100px;margin:auto;padding:20px}
.card{background:white;border:1px solid #e6eaf0;border-radius:14px;padding:14px;margin:10px 0}
table{width:100%;border-collapse:collapse;background:white}th,td{padding:8px;border-bottom:1px solid #eee;text-align:right;font-size:13px}
a{color:#0866c6;text-decoration:none}
</style></head><body><div class="wrap">
<h2>وضعیت منابع و Sync</h2><p><a href="/">← بازگشت به داشبورد</a></p>
<div id="summary" class="card">در حال بارگذاری...</div>
<div class="card"><table><thead><tr><th>منبع</th><th>نوع</th><th>امتیاز</th><th>فعال</th><th>آخرین مشاهده</th></tr></thead><tbody id="rows"></tbody></table></div>
</div><script>
function e(v){const d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML;}
async function load(){
 const [s,r]=await Promise.all([fetch('/api/sync/status'),fetch('/api/sources')]);
 if(!s.ok||!r.ok){document.getElementById('summary').textContent='خطا در دریافت وضعیت';return;}
 const st=await s.json(), rows=await r.json();
 const ls=st.latest_sync||{};
 document.getElementById('summary').textContent=
 'آخرین Sync: '+(ls.finished_at||ls.started_at||'-')+
 ' | وضعیت: '+(ls.status||'-')+
 ' | دیالوگ دیده‌شده: '+(ls.dialogs_seen||0)+
 ' | پیام جدید: '+(ls.messages_saved||0)+
 ' | منابع History: '+st.history_sources+
 ' | فرستنده‌های Cache: '+st.senders_cached+
 ' | CRM Outbox: '+JSON.stringify(st.crm_outbox||{})+
 ((ls.error_code||ls.error_detail)?' | هشدار: '+e(ls.error_code||'')+' '+e(ls.error_detail||''):'');
 document.getElementById('rows').innerHTML=rows.map(x=>'<tr><td>'+e(x.title||x.source_key)+'</td><td>'+e(x.peer_type||'')+'</td><td>'+e(x.score)+'</td><td>'+(x.enabled?'بله':'خیر')+'</td><td>'+e(x.last_seen_at||'')+'</td></tr>').join('');
}
load();
</script></body></html>""")

@app.post("/api/leads/{message_id}/send")
def send_lead(message_id: int, user=Depends(require_lead_send)):
    """Deprecated compatibility endpoint: review-selected leads are queued only.

    Actual delivery is an explicit server-side outbox action, so CRM Alpha 2.1
    cannot be contacted accidentally while sender conformance is being prepared.
    """
    try:
        outbox = queue_lead(message_id, user["username"], require_selected=True)
    except ValueError as exc:
        status = 404 if str(exc) == "message not found" else 400
        raise HTTPException(status_code=status, detail=str(exc))
    return {"status": "queued", "outbox_id": outbox["id"], "delivery": "not_attempted"}

@app.get("/api/stats")
def stats(user=Depends(require_read)):
    with connect() as con:
        total=con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        cats={r[0]:r[1] for r in con.execute("SELECT category,COUNT(*) FROM messages GROUP BY category")}
        last=con.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()
        sources=con.execute("SELECT COUNT(*) FROM source_registry WHERE enabled=1").fetchone()[0]
        backfill=con.execute("SELECT COALESCE(SUM(messages_scanned),0),COALESCE(SUM(messages_saved),0) FROM backfill_state").fetchone()
    return {"total": total, "categories": cats, "last_sync": dict(last) if last else None,
            "active_sources":sources,"history_scanned":backfill[0],"history_saved":backfill[1]}

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    user = _session_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
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
.datebox{display:flex;gap:4px}.datebox input{width:100%}.calBtn{padding:8px}.picker{position:fixed;inset:0;background:#0005;display:none;align-items:center;justify-content:center;z-index:20}.picker.show{display:flex}.pickerBox{background:#fff;border-radius:14px;padding:14px;width:min(360px,92vw)}.pickerHead{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.days{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}.days button{padding:8px 2px}.muted{opacity:.35}
@media(max-width:900px){.bar{grid-template-columns:1fr 1fr}.bar #q{grid-column:1/-1}}
</style></head><body><div class="wrap">
<h1>SATNO | هوش بازار بله</h1><div class="sub">نسخه 0.5 Staff — ورود پرسنل، RBAC و جستجوی تاریخچه بازار</div>
<div class="meta"><a href="/status">وضعیت منابع و Sync</a> • <a href="/review">بررسی سرنخ‌ها</a> • <a href="/sources/manage">مدیریت منابع</a> • <a href="/crm/outbox">صف CRM</a> • <a href="/admin/users">مدیریت کاربران</a> • <button id="logoutBtn" type="button">خروج</button></div>
<div id="stats" class="stats">در حال بارگذاری...</div>
<div class="bar">
<input id="q" placeholder="جستجو: نام دقیق محصول، مدل، برند، متن پیام...">
<select id="cat"><option value="">همه دسته‌ها</option><option value="supplier_seller">فروشنده/تأمین‌کننده</option><option value="buyer_demand">خریدار/تقاضا</option><option value="stock_availability">موجودی</option><option value="inquiry_project">استعلام/پروژه</option><option value="other">سایر</option></select>
<input id="sender" placeholder="ID خریدار/فروشنده">
<div class="datebox"><input id="from" inputmode="numeric" placeholder="از تاریخ"><button type="button" class="calBtn" data-target="from">📅</button></div>
<div class="datebox"><input id="to" inputmode="numeric" placeholder="تا تاریخ"><button type="button" class="calBtn" data-target="to">📅</button></div>
<button id="searchBtn" type="button">جستجو</button>
<button id="clearBtn" type="button">پاک‌کردن</button>
</div>
<div class="hint">می‌توانید نام کامل محصول/متن پیام را Paste کنید. جستجو تفاوت نیم‌فاصله، اعداد فارسی/انگلیسی و خط تیره مدل‌ها را نادیده می‌گیرد. تاریخ شمسی نمونه: ۱۴۰۵/۰۷/۰۸</div>
<div id="list"></div></div>
<div id="picker" class="picker"><div class="pickerBox"><div class="pickerHead"><button id="nextMonth">◀</button><strong id="pickerTitle"></strong><button id="prevMonth">▶</button></div><div class="days" id="pickerDays"></div><button id="pickerClose" type="button">بستن</button></div></div>
<script>
const labels={supplier_seller:'فروشنده/تأمین‌کننده',buyer_demand:'خریدار/تقاضا',stock_availability:'موجودی',inquiry_project:'استعلام/پروژه',other:'سایر'};
function escapeHtml(v){const d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML;}
async function sendLead(id,btn){
 btn.disabled=true;const old=btn.textContent;btn.textContent='در حال ارسال...';
 try{
   const r=await fetch('/api/leads/'+id+'/send',{method:'POST'});
   const data=await r.json();
   if(r.ok){btn.textContent=data.status==='sent'?'ارسال شد':'در صف CRM';}
   else{btn.textContent='خطا';alert('ارسال Lead ناموفق بود');}
 }catch(e){btn.textContent='خطا';}
 setTimeout(()=>{btn.disabled=false;btn.textContent=old;},2500);
}
function senderHtml(r){
 const label=escapeHtml(r.sender_username||r.sender_name||r.sender_id||'-');
 if(r.sender_link && /^https:\/\/ble\.ir\/[A-Za-z0-9_.-]+\/?$/.test(r.sender_link)){
   return '<a href="'+escapeHtml(r.sender_link)+'" target="_blank" rel="noopener noreferrer">بازکردن در بله: '+label+'</a>';
 }
 const id=r.sender_id?' • ID: '+escapeHtml(r.sender_id):'';
 return label+id+' <span class="tag">لینک عمومی بله موجود نیست</span>';
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
   const ls=s.last_sync; const syncText=ls?(' | آخرین Sync: '+(ls.finished_at||ls.started_at)+' | جدید: '+ls.messages_saved):' | هنوز Sync ثبت نشده'; const sourceText=' | منابع فعال: '+s.active_sources+' | History: '+s.history_scanned;
   document.getElementById('stats').textContent='کل پیام‌ها: '+s.total+' | نتایج: '+rows.length+sourceText+syncText;
   list.innerHTML=rows.length?rows.map(r=>'<div class="card"><div class="meta">'+escapeHtml(r.chat_name||'-')+' • '+senderHtml(r)+' • '+escapeHtml(r.sent_at_display||r.sent_at||'')+'</div><p>'+escapeHtml(r.text)+'</p><span class="tag">'+escapeHtml(labels[r.category]||r.category)+'</span> '+(r.brands||[]).map(x=>'<span class="tag">'+escapeHtml(x)+'</span>').join('')+' '+(r.models||[]).map(x=>'<span class="tag">مدل: '+escapeHtml(x)+'</span>').join('')+' '+(r.power_values||[]).map(x=>'<span class="tag">توان: '+escapeHtml(x)+'</span>').join('')+' '+(r.price_values||[]).map(x=>'<span class="tag">قیمت: '+escapeHtml(x)+'</span>').join('')+' '+(r.locations||[]).map(x=>'<span class="tag">'+escapeHtml(x)+'</span>').join('')+' '+(r.currency_values||[]).map(x=>'<span class="tag">واحد: '+escapeHtml(x)+'</span>').join('')+' <a class="leadBtn" href="/review?message_id='+r.id+'">بررسی و انتخاب سرنخ</a></div>').join(''):'<div class="stats">نتیجه‌ای پیدا نشد.</div>';
 }catch(e){list.innerHTML='<div class="stats error">خطا در جستجو: '+escapeHtml(e.message)+'</div>';}
}
function clearFilters(){['q','sender','from','to'].forEach(id=>document.getElementById(id).value='');document.getElementById('cat').value='';load();}

const jMonths=['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
let pickerTarget=null,pickerY=1405,pickerM=7;
function jMonthDays(y,m){if(m<=6)return 31;if(m<=11)return 30;return ((y+1)%4===0)?30:29;}
function openPicker(target){
 pickerTarget=target;
 const v=document.getElementById(target).value.replace(/[۰-۹]/g,d=>'۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
 const p=v.split('/').map(Number); if(p.length===3&&p[0]){pickerY=p[0];pickerM=p[1];}
 renderPicker();document.getElementById('picker').classList.add('show');
}
function renderPicker(){
 document.getElementById('pickerTitle').textContent=jMonths[pickerM-1]+' '+pickerY;
 const box=document.getElementById('pickerDays');box.innerHTML='';
 for(let d=1;d<=jMonthDays(pickerY,pickerM);d++){const b=document.createElement('button');b.type='button';b.textContent=d;b.onclick=()=>{document.getElementById(pickerTarget).value=pickerY+'/'+String(pickerM).padStart(2,'0')+'/'+String(d).padStart(2,'0');document.getElementById('picker').classList.remove('show');};box.appendChild(b);}
}
document.querySelectorAll('.calBtn').forEach(b=>b.addEventListener('click',()=>openPicker(b.dataset.target)));
document.getElementById('pickerClose').onclick=()=>document.getElementById('picker').classList.remove('show');
document.getElementById('prevMonth').onclick=()=>{pickerM--;if(pickerM<1){pickerM=12;pickerY--;}renderPicker();};
document.getElementById('nextMonth').onclick=()=>{pickerM++;if(pickerM>12){pickerM=1;pickerY++;}renderPicker();};

document.getElementById('logoutBtn').addEventListener('click',async()=>{await fetch('/api/auth/logout',{method:'POST'});location.href='/login';});
document.getElementById('searchBtn').addEventListener('click',load);
document.getElementById('clearBtn').addEventListener('click',clearFilters);
['q','sender','from','to'].forEach(id=>document.getElementById(id).addEventListener('keydown',e=>{if(e.key==='Enter')load();}));
load();
</script></body></html>""")
