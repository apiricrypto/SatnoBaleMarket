from ui_theme import staff_document
import os
from fastapi import FastAPI, Query, Request, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
from db import init_db, connect
from classifier import analyze, dumps
from dedup import make_dedup_key
from display_utils import format_tehran_jalali, normalize_datetime_filter
from search_utils import normalize_search_text, query_terms, message_search_score
from time_utils import parse_message_datetime
from auth import authenticate_user, create_session, resolve_session, revoke_session, role_allows, create_user, list_users, update_user, change_own_password
from crm_connector import queue_lead
from operations_routes import router as operations_router
from ui_theme import SATNO_UI_CSS
import json

app = FastAPI(title="SATNO Bale Market Intelligence", version="0.5.2")
app.include_router(operations_router)

@app.get("/assets/satno-ui.css")
def satno_ui_css():
    return Response(content=SATNO_UI_CSS, media_type="text/css; charset=utf-8")

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

@app.get("/assets/Vazirmatn-Regular.woff2")
def persian_font():
    from pathlib import Path
    return FileResponse(Path(__file__).with_name("assets") / "Vazirmatn-Regular.woff2", media_type="font/woff2", headers={"Cache-Control": "public, max-age=604800"})


@app.get("/assets/login-solar.webp")
def login_solar_photo():
    from pathlib import Path
    return FileResponse(Path(__file__).with_name("assets") / "login-solar.webp", media_type="image/webp", headers={"Cache-Control": "public, max-age=604800"})


@app.get("/assets/login-solar-art.svg")
def login_solar_art():
    from pathlib import Path
    return Response(
        Path(__file__).with_name("assets").joinpath("login-solar-art.svg").read_bytes(),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if _session_user(request):
        return RedirectResponse("/", status_code=303)
    return HTMLResponse("""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ورود | بله مارکت ساتنو</title><link rel="icon" href="data:,">
<style>
@font-face{font-family:Vazirmatn;src:url("/assets/Vazirmatn-Regular.woff2") format("woff2");font-display:swap}
:root{font-family:Vazirmatn,Tahoma,"Segoe UI",sans-serif;color:#142b4a}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;background:#f5f7fc}
.login-shell{display:grid;grid-template-columns:1fr 1fr;min-height:100vh;direction:ltr}
.hero{position:relative;color:#fff;direction:rtl;padding:55px clamp(28px,5vw,78px);display:flex;flex-direction:column;overflow:hidden;background:linear-gradient(150deg,rgba(4,43,95,.88),rgba(9,63,127,.54) 55%,rgba(4,43,95,.16)),url('/assets/login-solar.webp') center/cover no-repeat;border-radius:0 26px 26px 0}
.hero-top{display:flex;justify-content:space-between;align-items:flex-start;gap:18px}
.brand{font-weight:900;letter-spacing:.4px;font-size:31px;line-height:1.1;direction:ltr;text-align:left}
.brand small{display:block;font-size:14px;font-weight:600;letter-spacing:0;direction:rtl;text-align:left;margin-top:5px}
.eyebrow{font-weight:700;line-height:1.8}
.hero-main{margin:auto 0;text-align:center}
.hero-main h1{font-size:clamp(34px,4vw,65px);margin:0 0 14px;font-weight:900}
.hero-main p{font-size:clamp(16px,1.6vw,26px);margin:0}
.features{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:52px}
.feature{font-size:13px;line-height:2;text-align:center}
.feature b{display:grid;place-items:center;font-size:29px;font-weight:500;width:68px;height:68px;max-width:100%;border:1px solid #ffffff55;border-radius:16px;background:#ffffff22;margin:0 auto 10px}
.hero-foot{font-size:12px;line-height:1.8;color:#e6f1ff;margin-top:35px}
.form-side{direction:rtl;display:flex;align-items:center;justify-content:center;padding:30px}
.login-card{background:#fff;border:1px solid #e1e8f3;border-radius:24px;padding:clamp(24px,4vw,44px);width:min(100%,510px);box-shadow:0 18px 60px #122c5410}
.login-wordmark{text-align:center;font-size:30px;font-weight:900;letter-spacing:2px;color:#087c91;margin-bottom:24px}.login-wordmark span{display:block;font-size:12px;letter-spacing:0;color:#617189}
h2{text-align:center;font-size:clamp(23px,2.4vw,31px);margin:0 0 7px}
.subtitle{text-align:center;color:#71809b;margin:0 0 30px}
label{font-size:13px;font-weight:700;display:block;margin:14px 0 7px}
.field{display:flex;align-items:center;border:1px solid #d5e0ef;border-radius:13px;background:#fff;overflow:hidden}
.field:focus-within{outline:3px solid #cbdcff;border-color:#3979dc}
input{width:100%;min-width:0;height:54px;border:0;outline:none;padding:0 16px;font:inherit;background:transparent;color:#172b4d}
.toggle{border:0;background:none;color:#285b9a;cursor:pointer;padding:12px;font:inherit;white-space:nowrap}
button[type=submit]{width:100%;height:57px;border:0;border-radius:13px;background:linear-gradient(90deg,#0872d1,#0b438a);color:#fff;font:inherit;font-weight:800;font-size:18px;margin-top:23px;cursor:pointer}
button:disabled{opacity:.62;cursor:wait}
.error{min-height:24px;color:#b42318;font-size:13px;margin:10px 0}
.help{color:#667894;font-size:13px;margin-top:20px}
.footer{text-align:center;border-top:1px solid #e8edf4;padding-top:20px;color:#6c7d96;font-size:12px;margin-top:28px}
:focus-visible{outline:3px solid #91baff;outline-offset:3px}
@media(max-width:950px){.login-shell{grid-template-columns:1fr}.hero{border-radius:0 0 24px 24px;min-height:325px;padding:24px}.hero-main{margin:30px 0 0}.hero-main h1{font-size:35px}.features{margin-top:25px;gap:7px}.feature b{width:44px;height:44px;font-size:20px}.form-side{padding:20px}}
@media(max-width:490px){.hero{min-height:260px}.hero-top .eyebrow{display:none}.features{grid-template-columns:repeat(2,1fr)}.feature{font-size:11px}.login-card{padding:20px}.form-side{padding:12px}.brand{font-size:24px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
</style></head><body>
<main class="login-shell">
<section class="hero" aria-label="معرفی بله مارکت ساتنو">
<div class="hero-top"><div class="brand">SATNO<small>گروه ساتنو</small></div><div class="eyebrow">انرژی هوشمند<br>فرصت‌های بیشتر</div></div>
<div class="hero-main"><h1>بله مارکت ساتنو</h1><p>پایش هوشمند بازار، از گفتگو تا فرصت</p>
<div class="features"><div class="feature"><b aria-hidden="true"><svg viewBox="0 0 24 24" width="27" height="27" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16v12H8l-4 4z M8 8h8 M8 12h5"/></svg></b>جمع‌آوری گفتگوهای بازار</div>
<div class="feature"><b aria-hidden="true"><svg viewBox="0 0 24 24" width="27" height="27" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10h4v10 M10 20V4h4v16 M16 20v-7h4v7"/></svg></b>تحلیل سرنخ‌ها</div>
<div class="feature"><b aria-hidden="true"><svg viewBox="0 0 24 24" width="27" height="27" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4h18l-7 8v7l-4 2v-9z"/></svg></b>جست‌وجوی پیشرفته</div>
<div class="feature"><b aria-hidden="true"><svg viewBox="0 0 24 24" width="27" height="27" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20l6-6 M14 10l6-6 M4 4l16 16 M14 4h6v6 M4 14v6h6"/></svg></b>مدیریت فرصت‌های بازار</div></div></div>
<div class="hero-foot">SATNO BALE MARKET · From Conversations to Opportunities</div></section>
<section class="form-side"><form class="login-card" id="loginForm">
<div class="login-wordmark">SATNO<span>هوش بازار بله</span></div><h2>ورود به بله مارکت</h2><p class="subtitle">اطلاعات حساب کاربری خود را وارد کنید</p>
<label for="username">نام کاربری</label><div class="field"><input id="username" name="username" autocomplete="username" required placeholder="نام کاربری" maxlength="100"></div>
<label for="password">رمز عبور</label><div class="field"><input id="password" name="password" type="password" autocomplete="current-password" required placeholder="رمز عبور"><button id="togglePassword" type="button" class="toggle" aria-label="نمایش رمز عبور" aria-pressed="false">نمایش</button></div>
<p class="error" id="err" role="alert" aria-live="polite"></p>
<button id="loginBtn" type="submit">ورود</button>
<p class="help">برای بازیابی رمز عبور با مدیر سامانه تماس بگیرید.</p>
<div class="footer">گروه ساتنو · بله مارکت ۰.۵.۲</div>
</form></section></main>
<script>
const form=document.getElementById('loginForm'),btn=document.getElementById('loginBtn'),err=document.getElementById('err'),pwd=document.getElementById('password');
document.getElementById('togglePassword').addEventListener('click',e=>{
 const visible=pwd.type==='text';pwd.type=visible?'password':'text';
 e.currentTarget.textContent=visible?'نمایش':'پنهان';e.currentTarget.setAttribute('aria-pressed',String(!visible));e.currentTarget.setAttribute('aria-label',visible?'نمایش رمز عبور':'پنهان کردن رمز عبور');
});
form.addEventListener('submit',async e=>{
 e.preventDefault();if(btn.disabled)return;err.textContent='';
 const username=document.getElementById('username').value.trim();
 if(!username||!pwd.value){err.textContent='نام کاربری و رمز عبور الزامی است.';return;}
 btn.disabled=true;form.setAttribute('aria-busy','true');btn.textContent='در حال ورود…';
 try{
 const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username,password:pwd.value})});
 if(r.ok){location.replace('/');return}
 err.textContent=r.status===401?'نام کاربری یا رمز عبور نادرست است.':'ورود ناموفق بود. دوباره تلاش کنید.';
 }catch(e){err.textContent='ارتباط با سرور برقرار نشد.'}
 finally{btn.disabled=false;form.removeAttribute('aria-busy');btn.textContent='ورود'}
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

class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/auth/change-password")
def change_password(payload: ChangePasswordIn, request: Request, response: Response):
    user = _session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="authentication required")
    try:
        change_own_password(user["id"], payload.current_password, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"ok": True, "reauthentication_required": True}


@app.get("/profile/password", response_class=HTMLResponse)
def change_password_page(request: Request):
    if not _session_user(request):
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse(staff_document("""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>تغییر رمز عبور | SATNO</title><link rel="stylesheet" href="/assets/satno-ui.css">
<style>main{max-width:490px;margin:8vh auto;padding:25px;background:white;border:1px solid #dde6f3;border-radius:20px;box-shadow:0 12px 34px #102d4a10}label{display:block;margin:14px 0 5px}input{width:100%;padding:13px}button{margin-top:19px;padding:12px 22px}#status{margin-top:14px;min-height:25px}body{padding:0}</style></head><body>
<div class="wrap"><main class="password-card"><h2>تغییر رمز عبور</h2><p>برای امنیت حساب، رمز فعلی را وارد کنید.</p>
<form id="changeForm"><label for="current">رمز فعلی</label><input id="current" type="password" autocomplete="current-password" required>
<label for="newpass">رمز جدید (حداقل ۱۲ کاراکتر)</label><input id="newpass" type="password" autocomplete="new-password" minlength="12" required>
<label for="repeat">تکرار رمز جدید</label><input id="repeat" type="password" autocomplete="new-password" minlength="12" required>
<p class="hint">پس از تغییر رمز، همه نشست‌های قبلی بسته می‌شوند و باید دوباره وارد شوید.</p><button class="primary" type="submit" id="save">تغییر رمز عبور</button><p id="status" role="alert" aria-live="polite"></p></form><p><a href="/">بازگشت به داشبورد</a></p></main></div>
<script>
document.getElementById('changeForm').onsubmit=async e=>{
 e.preventDefault();const status=document.getElementById('status'),button=document.getElementById('save');
 const current=document.getElementById('current').value,pass=document.getElementById('newpass').value;
 if(pass!==document.getElementById('repeat').value){status.textContent='تکرار رمز جدید یکسان نیست.';return}
 if(pass.length<12){status.textContent='رمز جدید باید حداقل ۱۲ کاراکتر باشد.';return}
 button.disabled=true;status.textContent='در حال تغییر رمز…';
 try{const r=await fetch('/api/auth/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:current,new_password:pass})});
 if(r.ok){status.textContent='رمز تغییر کرد. لطفاً دوباره وارد شوید.';setTimeout(()=>location.replace('/login'),1300)}
 else {const d=await r.json();status.textContent=d.detail==='current password is incorrect'?'رمز فعلی صحیح نیست.':'تغییر رمز انجام نشد. اطلاعات را بررسی کنید.'}
 }catch(e){status.textContent='ارتباط با سرور برقرار نشد.'}
 finally{button.disabled=false}
};
</script></body></html>""", _session_user(request), request.url.path))


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request):
    user = _session_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if not role_allows(user["role"], "users:manage"):
        raise HTTPException(status_code=403, detail="forbidden")
    return HTMLResponse(staff_document("""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>مدیریت کاربران | SATNO Bale Market</title>
<style>
body{font-family:system-ui,Tahoma;background:#f6f8fb;color:#152235;margin:0}.wrap{max-width:1000px;margin:auto;padding:20px}
.card{background:#fff;border:1px solid #e6eaf0;border-radius:14px;padding:14px;margin:10px 0}
input,select,button{padding:9px;border:1px solid #d7dde7;border-radius:9px;margin:3px}button{cursor:pointer}
table{width:100%;border-collapse:collapse;background:white}th,td{padding:8px;border-bottom:1px solid #eee;text-align:right}
.err{color:#b42318}a{color:#0866c6;text-decoration:none}
</style><link rel="stylesheet" href="/assets/satno-ui.css?v=052-final"></head><body class="staff-shell"><div class="wrap"><h2>مدیریت کاربران پرسنل</h2><div class="nav" aria-label="ناوبری اصلی"><a href="/">جست‌وجوی بازار</a><a href="/review">بررسی سرنخ‌ها</a><a href="/sources/manage">مدیریت منابع</a><a href="/status">وضعیت همگام‌سازی</a><a href="/crm/outbox">صف CRM</a><a href="/admin/users" aria-current="page">کاربران</a></div>
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
</script></body></html>""", _session_user(request), request.url.path))

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
    return {"status":"ok","service":"satno-bale-market","version":"0.5.2"}

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
    return HTMLResponse(staff_document("""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>وضعیت منابع | SATNO Bale Market</title>
<style>
body{font-family:system-ui,Tahoma;background:#f6f8fb;color:#152235;margin:0}.wrap{max-width:1100px;margin:auto;padding:20px}
.card{background:white;border:1px solid #e6eaf0;border-radius:14px;padding:14px;margin:10px 0}
table{width:100%;border-collapse:collapse;background:white}th,td{padding:8px;border-bottom:1px solid #eee;text-align:right;font-size:13px}
a{color:#0866c6;text-decoration:none}
</style><link rel="stylesheet" href="/assets/satno-ui.css?v=052-final"></head><body class="staff-shell"><div class="wrap">
<h2>وضعیت منابع و Sync</h2><div class="nav" aria-label="ناوبری اصلی"><a href="/">جست‌وجوی بازار</a><a href="/review">بررسی سرنخ‌ها</a><a href="/sources/manage">مدیریت منابع</a><a href="/status" aria-current="page">وضعیت همگام‌سازی</a><a href="/crm/outbox">صف CRM</a><a href="/admin/users">کاربران</a><a href="/profile/password">تغییر رمز</a></div>
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
</script></body></html>""", _session_user(request), request.url.path))

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
    return HTMLResponse(staff_document("""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SATNO Bale Market Intelligence</title>
<style>
body{font-family:system-ui,Tahoma;background:#f4f7fb;margin:0;color:#152235}.wrap{max-width:1220px;margin:auto;padding:22px}
h1{font-size:26px;margin-bottom:5px}.sub{color:#667085}.nav{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.nav a,.nav button{padding:9px 12px;border:1px solid #dce3ec;border-radius:10px;background:#fff;color:#174b63;text-decoration:none}.nav a:hover{background:#eef7fb}.searchpanel{background:#fff;border:1px solid #e6eaf0;border-radius:16px;padding:14px;margin:14px 0}.bar{display:grid;grid-template-columns:2fr 1fr 1fr 1fr 1fr auto auto;gap:8px;margin:0}
input,select,button{padding:11px;border:1px solid #d7dde7;border-radius:10px;background:white;min-width:0}
button{cursor:pointer}.stats,.card{background:white;border:1px solid #e6eaf0;border-radius:14px;padding:14px;margin:10px 0;box-shadow:0 4px 14px #0f172a0a}
.card p{line-height:1.8}.meta{font-size:12px;color:#667085}.tag{display:inline-block;background:#eef3f8;border-radius:20px;padding:3px 8px;margin:3px;font-size:12px}
a{color:#0866c6;text-decoration:none}.error{color:#b42318}.hint{font-size:12px;color:#667085;margin-top:8px}
.datebox{display:flex;gap:4px}.datebox input{width:100%}.calBtn{padding:8px}.picker{position:fixed;inset:0;background:#0005;display:none;align-items:center;justify-content:center;z-index:20}.picker.show{display:flex}.pickerBox{background:#fff;border-radius:14px;padding:14px;width:min(360px,92vw)}.pickerHead{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.days{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}.days button{padding:8px 2px}.muted{opacity:.35}
@media(max-width:900px){.bar{grid-template-columns:1fr 1fr}.bar #q{grid-column:1/-1}}
</style><link rel="stylesheet" href="/assets/satno-ui.css?v=052-final"></head><body class="staff-shell market-board"><div class="wrap">
<h1>SATNO | هوش بازار بله</h1><div class="sub">نسخه 0.5 Staff — ورود پرسنل، RBAC و جستجوی تاریخچه بازار</div>
<div class="nav" aria-label="ناوبری اصلی"><a href="/" aria-current="page">جست‌وجوی بازار</a><a href="/review">بررسی سرنخ‌ها</a><a href="/sources/manage">مدیریت منابع</a><a href="/status">وضعیت همگام‌سازی</a><a href="/crm/outbox">صف CRM</a><a href="/admin/users">کاربران</a><a href="/profile/password">تغییر رمز</a><button id="logoutBtn" type="button">خروج</button></div>
<div id="stats" class="metric-grid"><div class="metric"><div class="label">در حال بارگذاری</div><div class="value">…</div></div></div>
<div class="searchpanel"><div class="bar">
<input id="q" placeholder="جستجو: نام دقیق محصول، مدل، برند، متن پیام...">
<select id="cat"><option value="">همه دسته‌ها</option><option value="supplier_seller">فروشنده/تأمین‌کننده</option><option value="buyer_demand">خریدار/تقاضا</option><option value="stock_availability">موجودی</option><option value="inquiry_project">استعلام/پروژه</option><option value="other">سایر</option></select>
<input id="sender" placeholder="ID خریدار/فروشنده">
<div class="datebox"><input id="from" inputmode="numeric" autocomplete="off" placeholder="از تاریخ (اختیاری)"><button type="button" class="calBtn" data-target="from">📅</button></div>
<div class="datebox"><input id="to" inputmode="numeric" autocomplete="off" placeholder="تا تاریخ (اختیاری)"><button type="button" class="calBtn" data-target="to">📅</button></div>
<button id="searchBtn" type="button">جستجو</button>
<button id="clearBtn" type="button">پاک‌کردن</button>
</div>
<div class="hint">می‌توانید نام کامل محصول/متن پیام را Paste کنید. جستجو تفاوت نیم‌فاصله، اعداد فارسی/انگلیسی و خط تیره مدل‌ها را نادیده می‌گیرد. تاریخ شمسی نمونه: ۱۴۰۵/۰۷/۰۸</div></div>
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
let dateTouched={from:false,to:false};
function params(){
 const p=new URLSearchParams();
 const values={q:'q',category:'cat',sender_id:'sender'};
 for(const [key,id] of Object.entries(values)){const v=document.getElementById(id).value.trim();if(v)p.set(key,v);}
 for(const id of ['from','to']){
   const v=document.getElementById(id).value.trim();
   if(dateTouched[id] && v)p.set(id==='from'?'date_from':'date_to',v);
 }
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
   document.getElementById('stats').innerHTML=
   '<div class="metric"><div class="label">کل پیام‌ها</div><div class="value">'+s.total+'</div><div class="foot">دیتابیس بازار</div></div>'+
   '<div class="metric"><div class="label">نتایج این جستجو</div><div class="value">'+rows.length+'</div><div class="foot">'+(document.getElementById('q').value.trim()?'فیلتر فعال':'آخرین پیام‌ها')+'</div></div>'+
   '<div class="metric"><div class="label">منابع فعال</div><div class="value">'+s.active_sources+'</div><div class="foot">کانال/گروه تحت پایش</div></div>'+
   '<div class="metric"><div class="label">History خوانده‌شده</div><div class="value">'+s.history_scanned+'</div><div class="foot">رکورد بررسی‌شده</div></div>'+
   '<div class="metric"><div class="label">آخرین Sync</div><div class="value '+((ls&&ls.status==='ok')?'kpi-good':'kpi-warn')+'">'+(ls?(ls.status||'—'):'—')+'</div><div class="foot">'+(ls?(ls.finished_at||ls.started_at||''):'هنوز ثبت نشده')+'</div></div>';
   list.innerHTML=rows.length?rows.map(r=>'<div class="card result-card cat-'+escapeHtml(r.category||'other')+'"><div class="meta">'+escapeHtml(r.chat_name||'-')+' • '+senderHtml(r)+' • '+escapeHtml(r.sent_at_display||r.sent_at||'')+'</div><div class="message">'+escapeHtml(r.text)+'</div><div>'+'<span class="tag">'+escapeHtml(labels[r.category]||r.category)+'</span> '+(r.brands||[]).map(x=>'<span class="tag">'+escapeHtml(x)+'</span>').join('')+' '+(r.models||[]).map(x=>'<span class="tag">مدل: '+escapeHtml(x)+'</span>').join('')+' '+(r.power_values||[]).map(x=>'<span class="tag">توان: '+escapeHtml(x)+'</span>').join('')+' '+(r.price_values||[]).map(x=>'<span class="tag">قیمت: '+escapeHtml(x)+'</span>').join('')+' '+(r.locations||[]).map(x=>'<span class="tag">'+escapeHtml(x)+'</span>').join('')+' '+(r.currency_values||[]).map(x=>'<span class="tag">واحد: '+escapeHtml(x)+'</span>').join('')+'</div><div class="actions"><a class="leadBtn" href="/review?message_id='+r.id+'">بررسی سرنخ</a></div></div>').join(''):'<div class="empty-state"><strong>نتیجه‌ای پیدا نشد</strong><div class="muted" style="margin-top:6px">عبارت جستجو یا فیلترها را تغییر دهید.</div></div>';
 }catch(e){list.innerHTML='<div class="stats error">خطا در جستجو: '+escapeHtml(e.message)+'</div>';}
}
function clearFilters(){['q','sender','from','to'].forEach(id=>document.getElementById(id).value='');dateTouched={from:false,to:false};document.getElementById('cat').value='';load();}

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
document.querySelectorAll('.calBtn').forEach(b=>b.addEventListener('click',()=>{dateTouched[b.dataset.target]=true;openPicker(b.dataset.target);}));
document.getElementById('pickerClose').onclick=()=>document.getElementById('picker').classList.remove('show');
document.getElementById('prevMonth').onclick=()=>{pickerM--;if(pickerM<1){pickerM=12;pickerY--;}renderPicker();};
document.getElementById('nextMonth').onclick=()=>{pickerM++;if(pickerM>12){pickerM=1;pickerY++;}renderPicker();};

document.getElementById('logoutBtn').addEventListener('click',async()=>{await fetch('/api/auth/logout',{method:'POST'});location.href='/login';});
document.getElementById('searchBtn').addEventListener('click',load);
document.getElementById('clearBtn').addEventListener('click',clearFilters);
['q','sender'].forEach(id=>document.getElementById(id).addEventListener('keydown',e=>{if(e.key==='Enter')load();}));
['from','to'].forEach(id=>{
 const el=document.getElementById(id);
 el.value='';
 el.addEventListener('input',()=>{dateTouched[id]=true;});
 el.addEventListener('keydown',e=>{if(e.key==='Enter')load();});
});
load();
</script></body></html>""", _session_user(request), request.url.path))
