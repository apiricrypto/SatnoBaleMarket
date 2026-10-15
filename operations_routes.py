import asyncio
import json
import os
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import urlparse

from bale import BaleClient
from bale.peer import Peer
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from auth import resolve_session, role_allows
from crm_connector import process_outbox, queue_lead, send_outbox_item
from db import connect
from lead_review import save_review
from source_registry import add_source, delete_source, delete_sources_bulk, update_source
from username_sources import enqueue_username, list_username_queue, remove_username, accept_verified_resolution, set_resolution_failure, canonical_username
from search_utils import normalize_search_text

load_dotenv(".env.local")

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


class SourceBulkItem(BaseModel):
    peer_type: int
    peer_id: int


class SourceBulkDelete(BaseModel):
    items: list[SourceBulkItem]


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


def _cache_discovery_results(query, results):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        for item in results:
            con.execute(
                """INSERT INTO source_discovery_cache
                   (peer_type,peer_id,title,username,members_count,query_text,discovered_at,last_seen_at)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(peer_type,peer_id) DO UPDATE SET
                     title=excluded.title,
                     username=excluded.username,
                     members_count=excluded.members_count,
                     query_text=excluded.query_text,
                     last_seen_at=excluded.last_seen_at""",
                (
                    str(item.get("peer_type")),
                    str(item.get("peer_id")),
                    item.get("title"),
                    item.get("username"),
                    item.get("members_count"),
                    query,
                    now,
                    now,
                ),
            )


def _cached_discovery_matches(query):
    qnorm = normalize_search_text(query)
    if not qnorm:
        return []
    with connect() as con:
        rows = [dict(r) for r in con.execute(
            """SELECT peer_type,peer_id,title,username,members_count,last_seen_at
               FROM source_discovery_cache
               ORDER BY last_seen_at DESC"""
        ).fetchall()]
    out = []
    for row in rows:
        if str(row.get("peer_type")) != "2":
            continue
        title_norm = normalize_search_text(row.get("title") or "")
        user_norm = normalize_search_text(row.get("username") or "")
        if (title_norm and qnorm in title_norm) or (user_norm and qnorm == user_norm):
            row["peer_type"] = int(row["peer_type"])
            row["peer_id"] = int(row["peer_id"])
            row["match"] = "cache"
            row["already_added"] = False
            out.append(row)
    return out[:10]


async def _discover_bale_live(query: str, token: str):
    results = []
    async with BaleClient(token) as client:
        def add_result(full, match):
            item = {
                "peer_type": full.peer.type,
                "peer_id": full.peer.id,
                "title": getattr(full, "title", None) or query,
                "username": getattr(full, "username", None),
                "members_count": getattr(full, "members_count", None),
                "match": match,
            }
            if not any(
                x["peer_type"] == item["peer_type"] and x["peer_id"] == item["peer_id"]
                for x in results
            ):
                results.append(item)

        # Exact public username/link lookup first. Keep this path short and bounded.
        if query and " " not in query:
            try:
                info = await asyncio.wait_for(client.resolve(query), timeout=5)
                full = await asyncio.wait_for(client.get_full(info.peer), timeout=5)
                resolved_username = normalize_search_text(getattr(full, "username", "") or "")
                if resolved_username == normalize_search_text(query):
                    add_result(full, "username")
                    return results
            except Exception:
                pass

        # Bale server-side title search. This RPC is known to be unreliable on
        # some transport revisions, so it must never block the staff UI.
        try:
            candidates = await asyncio.wait_for(
                client.resolver.search_peer(query, kind="channel", limit=10),
                timeout=6,
            )
        except Exception:
            candidates = []

        for candidate in candidates:
            full = candidate
            try:
                full = await asyncio.wait_for(client.get_full(candidate.peer), timeout=3)
            except Exception:
                pass
            if _candidate_relevance({"title": getattr(full, "title", ""), "username": getattr(full, "username", "")}, query) >= 60:
                add_result(full, "title")
            if len(results) >= 10:
                break

        # Final bounded fallback: scan the account dialog list. This is the
        # path that previously found some channels (e.g. when SearchPeer did
        # not return them). Keep it bounded so the UI never hangs.
        if len(results) < 10:
            try:
                dialogs = await asyncio.wait_for(
                    client.get_dialogs(limit=500, page_size=50, resolve_names=True),
                    timeout=8,
                )
            except Exception:
                dialogs = []
            qnorm = normalize_search_text(query)
            for dialog in dialogs:
                title = getattr(dialog, "title", "") or ""
                title_norm = normalize_search_text(title)
                peer = getattr(dialog, "peer", None)
                if peer is None:
                    continue
                matched = bool(qnorm and (qnorm in title_norm or title_norm in qnorm))
                full = None
                username = None
                if matched or (" " not in query):
                    try:
                        full = await asyncio.wait_for(client.get_full(peer), timeout=2)
                        username = getattr(full, "username", None)
                    except Exception:
                        full = None
                user_norm = normalize_search_text(username or "")
                if matched or (qnorm and user_norm and qnorm == user_norm):
                    add_result(full or dialog, "dialogs")
                if len(results) >= 10:
                    break

    return results[:10]


def _candidate_relevance(row, query):
    qnorm = normalize_search_text(query or "")
    title_norm = normalize_search_text(row.get("title") or "")
    user_norm = normalize_search_text(row.get("username") or "")
    if not qnorm:
        return 1
    if user_norm and qnorm == user_norm:
        return 100
    if title_norm and qnorm == title_norm:
        return 95
    if user_norm and qnorm in user_norm:
        return 90
    if title_norm and qnorm in title_norm:
        return 80
    # Fuzzy title matching is useful for spacing/wording differences, but keep
    # the threshold high enough to avoid showing unrelated Bale search noise.
    if title_norm:
        ratio = SequenceMatcher(None, qnorm, title_norm).ratio()
        if ratio >= 0.72:
            return 60 + int(ratio * 20)
    # A prior search query is not evidence that this Peer matches.
    # Never suggest a candidate solely because it was returned by fuzzy SearchPeer.
    return 0


@router.post("/api/sources/verify/{peer_type}/{peer_id}")
async def verify_source_candidate(peer_type: int, peer_id: int, q: str = "", user=Depends(require_admin)):
    token = (os.getenv("BALE_TOKEN") or "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="BALE_TOKEN روی سرور تنظیم نیست")
    if peer_type != 2:
        raise HTTPException(status_code=400, detail="فقط کانال یا گروه قابل تأیید است")
    peer = Peer.user(peer_id) if peer_type == 1 else Peer.channel(peer_id)
    try:
        async with BaleClient(token) as client:
            full = await asyncio.wait_for(client.get_full(peer), timeout=6)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="تأیید مشخصات از بله timeout شد")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"تأیید مشخصات ناموفق بود: {type(exc).__name__}")

    title = getattr(full, "title", None) or ""
    username = (getattr(full, "username", None) or "").lstrip("@") or None
    members_count = getattr(full, "members_count", None)
    query = (q or "").strip().lstrip("@")
    qnorm = normalize_search_text(query)
    verified_match = False
    if qnorm:
        verified_match = (
            (username and normalize_search_text(username) == qnorm)
            or qnorm in normalize_search_text(title)
        )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        con.execute(
            """INSERT INTO source_discovery_cache
               (peer_type,peer_id,title,username,members_count,query_text,discovered_at,last_seen_at)
               VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(peer_type,peer_id) DO UPDATE SET
                 title=excluded.title,
                 username=excluded.username,
                 members_count=excluded.members_count,
                 query_text=excluded.query_text,
                 last_seen_at=excluded.last_seen_at""",
            (str(peer_type), str(peer_id), title, username, members_count, query or None, now, now),
        )
        registered = con.execute(
            "SELECT 1 FROM source_registry WHERE peer_type=? AND peer_id=?",
            (str(peer_type), str(peer_id)),
        ).fetchone() is not None

    return {
        "peer_type": peer_type,
        "peer_id": peer_id,
        "title": title,
        "username": username,
        "members_count": members_count,
        "verified_match": bool(verified_match),
        "already_added": registered,
    }


@router.get("/api/sources/candidates")
def source_candidates(q: str = "", limit: int = 100, user=Depends(require_admin)):
    limit = max(1, min(int(limit), 300))
    with connect() as con:
        registry = {
            (str(row["peer_type"]), str(row["peer_id"]))
            for row in con.execute("SELECT peer_type,peer_id FROM source_registry").fetchall()
        }
        rows = [
            dict(row)
            for row in con.execute(
                """SELECT peer_type,peer_id,title,username,members_count,query_text,last_seen_at
                   FROM source_discovery_cache
                   ORDER BY last_seen_at DESC"""
            ).fetchall()
        ]

    ranked = []
    for row in rows:
        if str(row.get("peer_type")) != "2":
            continue
        score = _candidate_relevance(row, q)
        if q and score <= 0:
            continue
        row["peer_type"] = int(row["peer_type"])
        row["peer_id"] = int(row["peer_id"])
        row["already_added"] = (str(row["peer_type"]), str(row["peer_id"])) in registry
        row["relevance"] = score
        ranked.append(row)

    ranked.sort(key=lambda x: (x["relevance"], x.get("last_seen_at") or ""), reverse=True)
    if q:
        ranked = [x for x in ranked if x["relevance"] >= 60]
    return {"query": q, "results": ranked[:limit]}


@router.get("/api/sources/discover")
async def source_discover(q: str, user=Depends(require_admin)):
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="نام یا آدرس کانال/گروه را وارد کنید")
    token = (os.getenv("BALE_TOKEN") or "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="BALE_TOKEN روی سرور تنظیم نیست")

    parsed = urlparse(query if "://" in query else "")
    if parsed.netloc.lower() in {"ble.ir", "www.ble.ir"}:
        query = parsed.path.strip("/").split("/", 1)[0] or query
    query = query.lstrip("@").strip()

    # First return instant local matches from already-known sources. This keeps
    # the page responsive even when Bale's SearchPeer transport is degraded.
    qnorm = normalize_search_text(query)
    with connect() as con:
        known = [
            dict(row)
            for row in con.execute(
                """SELECT source_key,title,peer_type,peer_id,score,enabled,last_seen_at
                   FROM source_registry
                   ORDER BY score DESC,title"""
            ).fetchall()
        ]
    local = []
    for row in known:
        if qnorm and qnorm in normalize_search_text(row.get("title") or ""):
            local.append({
                "peer_type": int(row["peer_type"]),
                "peer_id": int(row["peer_id"]),
                "title": row.get("title"),
                "username": None,
                "members_count": None,
                "match": "local_registry",
                "already_added": True,
            })
    if local:
        return {"query": query, "results": local[:10], "mode": "local"}

    cached = _cached_discovery_matches(query)
    if cached:
        return {"query": query, "results": cached, "mode": "cache"}

    try:
        results = await asyncio.wait_for(_discover_bale_live(query, token), timeout=12)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="پاسخ جستجوی بله بیش از حد طول کشید. از Peer ID استفاده کنید یا چند دقیقه بعد دوباره تلاش کنید.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"جستجوی بله ناموفق بود: {type(exc).__name__}",
        )

    results = [item for item in results if str(item.get("peer_type")) == "2" and _candidate_relevance(item, query) >= 60]
    if results:
        _cache_discovery_results(query, results)
    return {"query": query, "results": results, "mode": "live"}


@router.patch("/api/sources/item/{peer_type}/{peer_id}")
def source_update_by_peer(peer_type: int, peer_id: int, payload: SourceUpdate, user=Depends(require_admin)):
    source_key = f"bale:{peer_type}:{peer_id}"
    try:
        return update_source(source_key, **payload.model_dump())
    except ValueError as exc:
        status = 404 if str(exc) == "source not found" else 400
        raise HTTPException(status_code=status, detail=str(exc))


@router.delete("/api/sources/item/{peer_type}/{peer_id}", status_code=204)
def source_delete_by_peer(peer_type: int, peer_id: int, user=Depends(require_admin)):
    source_key = f"bale:{peer_type}:{peer_id}"
    try:
        delete_source(source_key)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return None


class UsernameSourceInput(BaseModel):
    username: str
    label: Optional[str] = None
    score: int = 50


@router.get("/api/sources/usernames")
def usernames_list(user=Depends(require_admin)):
    return {"sources": list_username_queue()}


@router.post("/api/sources/usernames")
def usernames_add(payload: UsernameSourceInput, user=Depends(require_admin)):
    try:
        return enqueue_username(payload.username, payload.label, payload.score)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/api/sources/usernames/{username}")
def usernames_delete(username: str, user=Depends(require_admin)):
    try:
        return remove_username(username)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/api/sources/usernames/{username}/resolve")
async def usernames_resolve(username: str, user=Depends(require_admin)):
    try:
        username = canonical_username(username)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not any(row["username"] == username and row["status"] == "pending" for row in list_username_queue()):
        raise HTTPException(status_code=404, detail="Username is not pending")
    token = (os.getenv("BALE_TOKEN") or "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="Bale account token is not configured")
    try:
        async with BaleClient(token) as client:
            resolved = await asyncio.wait_for(client.resolve(username), timeout=6)
            peer = getattr(resolved, "peer", None)
            if peer is None:
                raise ValueError("Resolve returned no Peer")
            full = await asyncio.wait_for(client.get_full(peer), timeout=6)
            real_username = getattr(full, "username", "") or getattr(resolved, "username", "")
            return accept_verified_resolution(
                username, real_username, peer.type, peer.id, getattr(full, "title", None)
            )
    except (asyncio.TimeoutError, LookupError, ValueError) as exc:
        set_resolution_failure(username, type(exc).__name__)
        raise HTTPException(status_code=422, detail="Bale did not confirm this username; it remains pending")
    except Exception as exc:
        set_resolution_failure(username, type(exc).__name__)
        raise HTTPException(status_code=502, detail="Bale transport error; username remains pending")


@router.post("/api/sources/bulk-delete")
def sources_bulk_delete(payload: SourceBulkDelete, user=Depends(require_admin)):
    try:
        return delete_sources_bulk([x.model_dump() for x in payload.items])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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
<style>body{font-family:system-ui,Tahoma;background:#f6f8fb;margin:0;color:#152235}.wrap{max-width:1200px;margin:auto;padding:20px}.card{background:#fff;border:1px solid #e6eaf0;border-radius:14px;padding:14px;margin:10px 0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}input,select,textarea,button{box-sizing:border-box;width:100%;padding:9px;border:1px solid #d7dde7;border-radius:8px}textarea{min-height:80px}.meta{font-size:12px;color:#667085}.actions{display:flex;gap:8px;margin-top:10px}.actions button{width:auto}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style><link rel="stylesheet" href="/assets/satno-ui.css?v=issue1-nav-3"></head><body class="staff-shell"><div class="wrap"><div class="section-head"><div><h2>بررسی سرنخ‌ها</h2><div class="muted">پیام‌های بازار را بازبینی، اصلاح و برای CRM انتخاب کنید.</div></div><div class="nav" aria-label="ناوبری اصلی"><a href="/">جست‌وجوی بازار</a><a href="/review" aria-current="page">بررسی سرنخ‌ها</a><a href="/sources/manage">مدیریت منابع</a><a href="/status">وضعیت همگام‌سازی</a><a href="/crm/outbox">صف CRM</a><a href="/admin/users">کاربران</a></div></div><div class="card toolbar"><select id="filter"><option value="unreviewed">بررسی‌نشده</option><option value="">همه</option><option value="reviewed">بررسی‌شده</option><option value="selected">انتخاب‌شده</option><option value="rejected">ردشده</option></select><button class="primary" onclick="load()">بارگذاری</button><span class="muted">روی هر کارت می‌توانید اطلاعات استخراج‌شده را اصلاح کنید.</span></div><div id="list"></div></div>
<script>
var requestedId=new URLSearchParams(location.search).get('message_id');function esc(v){var d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML}function first(a){return a&&a.length?a[0]:''}
async function load(){var url=requestedId?'/api/review/messages?message_id='+encodeURIComponent(requestedId):'/api/review/messages?limit=50&review_status='+encodeURIComponent(filter.value);var r=await fetch(url),rows=await r.json(),html='';rows.forEach(function(x){html+='<div class="card result-card cat-'+esc(x.reviewed_category||x.category||'other')+'" data-id="'+x.id+'"><div class="section-head"><div><div class="meta">#'+x.id+' • '+esc(x.chat_name||'-')+' • '+esc(x.sender_name||x.sender_id||'-')+' • '+esc(x.sent_at||'')+'</div><div class="message">'+esc(x.text)+'</div></div><span class="pill">'+esc(x.review_status||'بررسی‌نشده')+'</span></div><div class="grid"><select class="category"><option value="supplier_seller">تأمین‌کننده/فروشنده</option><option value="stock_availability">موجودی/فروش</option><option value="buyer_demand">تقاضای خرید</option><option value="inquiry_project">استعلام/پروژه</option><option value="other">سایر</option></select><input class="product" placeholder="محصول" value="'+esc(x.product||first(x.product_types))+'"><input class="brand" placeholder="برند" value="'+esc(x.brand||first(x.brands))+'"><input class="model" placeholder="مدل" value="'+esc(x.model||first(x.models))+'"><input class="power" placeholder="توان" value="'+esc(x.power||first(x.power_values))+'"><input class="capacity" placeholder="ظرفیت" value="'+esc(x.capacity||first(x.energy_values))+'"><input class="price" placeholder="قیمت متن پیام" value="'+esc(x.price||first(x.price_values))+'"><input class="currency" placeholder="واحد قیمت" value="'+esc(x.currency||first(x.currency_values))+'"><input class="location" placeholder="محل" value="'+esc(x.location||first(x.locations))+'"><input class="contact" placeholder="تماس" value="'+esc(x.contact||first(x.phones))+'"><input class="estimated_amount" type="number" min="0" placeholder="مبلغ نرمال‌شده CRM"><input class="estimated_currency" maxlength="3" placeholder="ISO مثل IRR"><select class="priority"><option>normal</option><option>low</option><option>high</option><option>urgent</option></select></div><textarea class="notes" placeholder="یادداشت بررسی">'+esc(x.notes||'')+'</textarea><div class="actions"><button onclick="save(this,\'reviewed\')">ثبت بررسی</button><button onclick="save(this,\'selected\')">انتخاب برای CRM</button><button onclick="save(this,\'rejected\')">رد</button><button onclick="queueLead(this)">قرار دادن در صف CRM</button><span class="result"></span></div></div>'});list.innerHTML=html;rows.forEach(function(x){var c=document.querySelector('[data-id="'+x.id+'"]');c.querySelector('.category').value=x.reviewed_category||x.category||'other';c.querySelector('.priority').value=x.priority||'normal';if(x.estimated_amount!=null)c.querySelector('.estimated_amount').value=x.estimated_amount;if(x.estimated_currency)c.querySelector('.estimated_currency').value=x.estimated_currency})}
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
    return HTMLResponse("""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>مدیریت منابع بله | SATNO</title>
<style>
body{font-family:system-ui,Tahoma;background:#f4f7fb;margin:0;color:#17212f}
.wrap{max-width:1180px;margin:auto;padding:22px}.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:16px;margin:12px 0;box-shadow:0 4px 14px #0f172a0a}
.searchbox{display:grid;grid-template-columns:1fr auto;gap:8px}.searchbox input{font-size:15px}
input,button{box-sizing:border-box;padding:10px;border:1px solid #cfd8e3;border-radius:9px;background:#fff}
button{cursor:pointer}.primary{background:#0f4c5c;color:#fff;border-color:#0f4c5c}.danger{color:#b42318}.muted{color:#667085;font-size:13px}
.results{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px;margin-top:10px}.candidate{border:1px solid #e5e7eb;border-radius:12px;padding:10px}
.source{display:grid;grid-template-columns:76px minmax(200px,2fr) minmax(154px,170px) 86px minmax(140px,1fr) minmax(150px,1fr) 112px;gap:9px;align-items:center;border-top:1px solid #eef2f6;padding:12px 0;min-width:0}
.source:first-child{border-top:0}
.source>*{min-width:0}
.source .bulk-picker{display:inline-flex!important;align-items:center!important;gap:5px!important;white-space:nowrap!important;font-size:12px!important}
.source .bulk-picker input{flex:0 0 auto}
.source .scorebox{display:grid!important;grid-template-columns:38px minmax(60px,1fr) 38px!important;align-items:center!important;gap:3px!important;min-width:0!important;white-space:nowrap!important}
.source .scorebox input{width:100%!important;min-width:0!important;text-align:center!important;padding:6px 2px!important;font-size:14px!important}
.source .scorebox button{width:38px!important;min-width:0!important;padding:6px 2px!important;min-height:38px!important;font-size:12px!important}
.source .save,.source .del{width:100%;margin:2px 0}
@media(min-width:901px) and (max-width:1499px){.source{grid-template-columns:76px minmax(170px,1.7fr) 160px 84px minmax(120px,1fr) 112px}.source>div:nth-last-child(2){grid-column:2 / 5}}
.status{font-size:13px;margin-top:8px}.ok{color:#067647}.err{color:#b42318}
.badge{display:inline-block;background:#eef6f8;padding:3px 8px;border-radius:99px;font-size:12px}
@media(max-width:900px){.source{grid-template-columns:minmax(0,1fr) minmax(0,1fr)!important}.source>div:first-of-type,.source>.terms,.source>div:nth-last-child(2){grid-column:1/-1}.source>.scorebox{grid-column:1/-1;max-width:240px}.source>div:last-child{display:flex;gap:8px;grid-column:1/-1}.source .save,.source .del{width:auto;flex:1}.searchbox{grid-template-columns:1fr}}
</style><link rel="stylesheet" href="/assets/satno-ui.css?v=issue1-nav-3"></head>
<body class="staff-shell"><div class="wrap">
<div class="section-head"><div><h2>مدیریت منابع بله</h2><div class="muted">منابع پایش را خودتان اضافه، ویرایش، اولویت‌بندی یا غیرفعال کنید.</div></div><div class="nav" aria-label="ناوبری اصلی"><a href="/">جست‌وجوی بازار</a><a href="/review">بررسی سرنخ‌ها</a><a href="/sources/manage" aria-current="page">مدیریت منابع</a><a href="/status">وضعیت همگام‌سازی</a><a href="/crm/outbox">صف CRM</a><a href="/admin/users">کاربران</a></div></div>

<div class="card">
<div class="section-head"><div><h3>افزودن منبع جدید</h3><div class="muted">جستجو با نام، @username، لینک بله یا Peer ID</div></div><span class="pill">کنترل دستی منابع</span></div>
<div class="searchbox"><input id="discoverQ" autocomplete="off" placeholder="مثال: بازار انرژی خورشیدی یا @channelname یا https://ble.ir/channelname"><button id="discoverBtn" class="primary" type="button">جستجو در بله</button></div>
<div id="discoverMsg" class="status muted"></div><div id="discoverResults" class="results"></div>
<div style="margin-top:16px;border-top:1px solid #edf1f5;padding-top:14px">
  <div class="section-head"><div><strong>جستجو در کانال‌های شناسایی‌شده</strong><div class="muted">این بخش فقط نتایج مرتبط را از Cache محلی Sync نشان می‌دهد و وابسته به SearchPeer زنده نیست.</div></div></div>
  <input id="candidateQ" autocomplete="off" placeholder="بخشی از نام کانال یا username را وارد کنید؛ مثال: partonorpars" style="width:100%;margin-bottom:8px">
  <div id="candidateMsg" class="status muted"></div><div id="candidateResults" class="results"></div>
</div>
<div class="card" style="margin-top:14px">
  <h3>افزودن با شناسه عمومی بله</h3>
  <p class="muted">@username یا لینک ble.ir؛ منبع تا تأیید شناسه واقعی بله وارد پایش نمی‌شود.</p>
  <form id="usernameForm" class="toolbar">
    <input id="usernameValue" required placeholder="@username یا https://ble.ir/username">
    <input id="usernameLabel" placeholder="عنوان دلخواه">
    <button type="submit" class="primary">ثبت شناسه عمومی</button>
  </form>
  <div id="usernameMsg" class="status muted"></div>
  <div id="usernameRows"></div>
</div>
<details style="margin-top:12px"><summary>افزودن با Peer ID (حالت فنی)</summary>
<form id="manualForm" style="margin-top:8px"><input id="pt" type="number" value="2" placeholder="Peer type"><input id="pid" type="number" placeholder="Peer ID" required><input id="manualTitle" placeholder="عنوان"><input id="manualScore" type="number" value="50" placeholder="امتیاز"><button class="primary">افزودن</button></form>
</details>
</div>

<div class="card"><div class="section-head"><h3>منابع ثبت‌شده <span id="sourceCount" class="badge">...</span></h3><button id="reloadBtn" type="button">↻ تازه‌سازی</button></div>
<div class="muted">امتیاز = اولویت Sync. عدد بالاتر زودتر اسکن می‌شود. عادی 50، مهم 80، خیلی مهم 100.</div>
<div class="toolbar" style="margin:12px 0;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
  <input id="sourceFilter" type="search" placeholder="فیلتر منابع بر اساس عنوان یا Peer ID" style="flex:1;min-width:190px">
  <label style="display:flex;align-items:center;gap:6px"><input id="selectVisibleSources" type="checkbox"> انتخاب همه موارد نمایش‌داده‌شده</label>
  <span id="selectedSourceCount" class="muted" aria-live="polite">0 مورد انتخاب شده</span>
  <button id="bulkDeleteBtn" type="button" class="danger" disabled>حذف انتخاب‌شده‌ها</button>
</div>
<div id="sourceMsg" class="status muted">در حال بارگذاری منابع...</div><div id="sourceList"></div></div>
</div>
<script>
(function(){
 const $=id=>document.getElementById(id);
 const esc=v=>{const d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML};
 async function api(url,opt){
   const r=await fetch(url,opt); let d=null;
   try{d=await r.json()}catch(e){}
   if(!r.ok) throw new Error((d&&d.detail)||('HTTP '+r.status));
   return d;
 }
 function setMsg(el,text,ok){
   el.textContent=text||''; el.className='status '+(ok===true?'ok':ok===false?'err':'muted');
 }
 async function discover(){
   const q=$('discoverQ').value.trim();
   if(!q){setMsg($('discoverMsg'),'نام یا آدرس کانال/گروه را وارد کنید.',false);return;}
   $('discoverResults').innerHTML=''; setMsg($('discoverMsg'),'در حال جستجو در بله...',null);
   const controller=new AbortController();
   const timer=setTimeout(()=>controller.abort(),15000);
   try{
     const d=await api('/api/sources/discover?q='+encodeURIComponent(q),{signal:controller.signal});
     if(!d.results.length){setMsg($('discoverMsg'),'نتیجه‌ای پیدا نشد. @username یا لینک دقیق را امتحان کنید.',false);return;}
     setMsg($('discoverMsg'),d.results.length+' نتیجه پیدا شد.',true);
     for(const x of d.results){
       const box=document.createElement('div'); box.className='candidate';
       box.innerHTML='<strong>'+esc(x.title||'-')+'</strong><div class="muted">'+(x.username?'@'+esc(x.username)+' • ':'')+'Peer '+esc(x.peer_id)+(x.members_count?' • '+esc(x.members_count)+' عضو':'')+'</div>';
       const btn=document.createElement('button'); btn.type='button'; btn.className='primary'; btn.textContent='افزودن این منبع';
       btn.addEventListener('click',()=>addCandidate(x,btn,$('discoverMsg')));
       box.appendChild(btn); $('discoverResults').appendChild(box);
     }
   }catch(e){
     setMsg($('discoverMsg'),e.name==='AbortError'?'جستجو بیش از ۱۵ ثانیه طول کشید و متوقف شد. از Peer ID استفاده کنید.':e.message,false);
   }finally{clearTimeout(timer);}
 }
 async function addCandidate(x,btn,msgEl){
   btn.disabled=true;
   try{
     await api('/api/sources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({peer_type:x.peer_type,peer_id:x.peer_id,title:x.title||x.username||null,score:50,matched_terms:null,enabled:true})});
     setMsg(msgEl||$('discoverMsg'),'منبع اضافه شد.',true); await loadSources(); await loadCandidates();
     btn.textContent='اضافه شد';
   }catch(e){setMsg(msgEl||$('discoverMsg'),e.message,false);}
   finally{btn.disabled=false;}
 }
 function renderCandidates(items,container,msgEl){
   container.innerHTML='';
   if(!items.length){setMsg(msgEl,'تطابق مناسبی در فهرست شناسایی‌شده پیدا نشد.',false);return;}
   const strong=items.filter(x=>(x.relevance||0)>=60).length;
   setMsg(msgEl,strong?strong+' نتیجه مرتبط پیدا شد.':items.length+' نتیجه احتمالی پیدا شد؛ ابتدا مشخصات را از بله تأیید کنید.',strong>0);
   for(const x of items){
     const box=document.createElement('div');box.className='candidate';
     const strength=(x.relevance||0)>=60?'مرتبط':'نیازمند تأیید';
     box.innerHTML='<div class="section-head"><strong>'+esc(x.title||'-')+'</strong><span class="pill">'+strength+'</span></div><div class="muted">'+(x.username?'@'+esc(x.username)+' • ':'')+'Peer '+esc(x.peer_id)+(x.last_seen_at?' • آخرین مشاهده '+esc(x.last_seen_at):'')+'</div>';
     const verify=document.createElement('button');verify.type='button';verify.textContent='تأیید مشخصات از بله';
     verify.addEventListener('click',()=>verifyCandidate(x,box,msgEl));
     box.appendChild(verify);
     if(x.already_added){
       const state=document.createElement('button');state.type='button';state.disabled=true;state.textContent='قبلاً اضافه شده';
       box.appendChild(state);
     }
     container.appendChild(box);
   }
 }
 async function verifyCandidate(x,box,msgEl){
   setMsg(msgEl,'در حال تأیید مشخصات از بله...',null);
   try{
     const q=$('candidateQ').value.trim();
     const d=await api('/api/sources/verify/'+x.peer_type+'/'+x.peer_id+'?q='+encodeURIComponent(q),{method:'POST'});
     box.querySelector('strong').textContent=d.title||'-';
     const info=box.querySelector('.muted');
     info.textContent=(d.username?'@'+d.username+' • ':'')+'Peer '+d.peer_id+(d.members_count?' • '+d.members_count+' عضو':'');
     box.querySelectorAll('.verified-add').forEach(el=>el.remove());
     if(d.verified_match){
       setMsg(msgEl,'مشخصات با عبارت جستجو تأیید شد.',true);
       if(!d.already_added){
         const btn=document.createElement('button');btn.type='button';btn.className='primary verified-add';btn.textContent='افزودن منبع تأییدشده';
         btn.addEventListener('click',()=>addCandidate(d,btn,msgEl));box.appendChild(btn);
       }else{
         setMsg(msgEl,'این Peer قبلاً اضافه شده؛ مشخصات واقعی آن نمایش داده شد.',true);
       }
     }else{
       setMsg(msgEl,'این Peer با نام/username جستجو شده تطابق ندارد و امکان افزودن آن غیرفعال شد.',false);
       box.querySelectorAll('button').forEach(btn=>{
         if(btn.textContent.includes('افزودن')) btn.remove();
       });
     }
   }catch(e){setMsg(msgEl,e.message,false);}
 }
 async function loadCandidates(){
   const q=$('candidateQ').value.trim();
   setMsg($('candidateMsg'),'در حال خواندن فهرست محلی...',null);
   try{
     if(!q){setMsg($('candidateMsg'),'برای جلوگیری از نمایش کانال‌های نامرتبط، بخشی از نام یا username را وارد کنید.',null);$('candidateResults').innerHTML='';return;}
     const d=await api('/api/sources/candidates?limit=50&q='+encodeURIComponent(q));
     renderCandidates(d.results,$('candidateResults'),$('candidateMsg'));
   }catch(e){setMsg($('candidateMsg'),e.message,false);}
 }
 async function loadSources(){
   setMsg($('sourceMsg'),'در حال بارگذاری منابع...',null);
   try{
     const a=await api('/api/sources');
     $('sourceCount').textContent=String(a.length);
     $('sourceList').innerHTML='';
     for(const x of a){
       const row=document.createElement('div'); row.className='source';
       row.dataset.pt=x.peer_type; row.dataset.pid=x.peer_id;row.dataset.title=x.title||'';
       const pick=document.createElement('label');pick.className='bulk-picker';
       pick.style.cssText='display:flex;align-items:center;gap:5px;min-width:65px';
       pick.innerHTML='<input type="checkbox" class="bulk-select"> انتخاب';
       row.appendChild(pick);
       row.insertAdjacentHTML('beforeend','<div><input class="title" value="'+esc(x.title||'')+'" style="width:100%"><div class="muted">'+esc(x.source_key)+'</div></div>'+
       '<div class="scorebox"><button type="button" class="minus">−10</button><input class="score" type="number" min="0" value="'+esc(x.score||0)+'"><button type="button" class="plus">+10</button></div>'+
       '<label><input class="enabled" type="checkbox" '+(x.enabled?'checked':'')+'> فعال</label>'+
       '<input class="terms" value="'+esc(x.matched_terms||'')+'" placeholder="کلیدواژه‌ها">'+
       '<div class="muted">آخرین مشاهده: '+esc(x.last_seen_at||'-')+'</div>'+
       '<div><button type="button" class="primary save">ذخیره</button> <button type="button" class="danger del">حذف</button></div>');
       row.querySelector('.bulk-select').addEventListener('change',updateBulkSelection);
       row.querySelector('.minus').addEventListener('click',()=>bump(row,-10));
       row.querySelector('.plus').addEventListener('click',()=>bump(row,10));
       row.querySelector('.save').addEventListener('click',()=>saveSource(row));
       row.querySelector('.del').addEventListener('click',()=>deleteSource(row));
       $('sourceList').appendChild(row);
     }
     applySourceFilter();
     setMsg($('sourceMsg'),a.length?('نمایش '+a.length+' منبع ثبت‌شده'):'هیچ منبعی در Registry ثبت نشده است.',a.length>0);
   }catch(e){$('sourceCount').textContent='!';setMsg($('sourceMsg'),'خطا در دریافت منابع: '+e.message,false);}
 }
 function bump(row,n){const i=row.querySelector('.score');i.value=Math.max(0,Number(i.value||0)+n)}
 async function saveSource(row){
   try{
     await api('/api/sources/item/'+encodeURIComponent(row.dataset.pt)+'/'+encodeURIComponent(row.dataset.pid),{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:row.querySelector('.title').value.trim(),score:Number(row.querySelector('.score').value||0),enabled:row.querySelector('.enabled').checked,matched_terms:row.querySelector('.terms').value.trim()||null})});
     setMsg($('sourceMsg'),'تغییرات ذخیره شد.',true); await loadSources();
   }catch(e){setMsg($('sourceMsg'),'ذخیره ناموفق: '+e.message,false);}
 }
 function visibleSources(){
   return Array.from($('sourceList').querySelectorAll('.source')).filter(row=>row.style.display!=='none');
 }
 function updateBulkSelection(){
   const rows=visibleSources(),selected=Array.from($('sourceList').querySelectorAll('.bulk-select:checked'));
   $('selectedSourceCount').textContent=selected.length+' مورد انتخاب شده';
   $('bulkDeleteBtn').disabled=selected.length===0;
   $('selectVisibleSources').checked=rows.length>0&&rows.every(row=>row.querySelector('.bulk-select').checked);
   $('selectVisibleSources').indeterminate=rows.some(row=>row.querySelector('.bulk-select').checked)&&!$('selectVisibleSources').checked;
 }
 function applySourceFilter(){
   const q=$('sourceFilter').value.trim().toLocaleLowerCase();
   $('sourceList').querySelectorAll('.source').forEach(row=>{
     const hay=(row.dataset.title+' '+row.dataset.pt+' '+row.dataset.pid).toLocaleLowerCase();
     row.style.display=!q||hay.includes(q)?'':'none';
   });
   updateBulkSelection();
 }
 async function bulkDeleteSelected(){
   const selected=Array.from($('sourceList').querySelectorAll('.source')).filter(row=>row.querySelector('.bulk-select').checked);
   if(!selected.length)return;
   if(selected.length>100){setMsg($('sourceMsg'),'در هر عملیات حداکثر 100 منبع قابل حذف است.',false);return;}
   const details=selected.slice(0,10).map(row=>row.dataset.title+' (Peer '+row.dataset.pid+')').join('\\n');
   if(!confirm('حذف '+selected.length+' منبع انتخاب‌شده از فهرست Sync؟\\nپیام‌های تاریخی حذف نمی‌شوند.\\n\\n'+details+(selected.length>10?'\\n...':'')))return;
   const confirmed=prompt('برای تأیید نهایی، عدد '+selected.length+' را وارد کنید:');
   if(confirmed!==String(selected.length)){setMsg($('sourceMsg'),'حذف لغو شد.',null);return;}
   const button=$('bulkDeleteBtn');button.disabled=true;
   try{
     const payload={items:selected.map(row=>({peer_type:Number(row.dataset.pt),peer_id:Number(row.dataset.pid)}))};
     const result=await api('/api/sources/bulk-delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
     await loadSources();
     setMsg($('sourceMsg'),result.deleted+' منبع حذف شد. پیام‌های تاریخی حفظ شدند.',true);
   }catch(e){setMsg($('sourceMsg'),'حذف گروهی ناموفق: '+e.message,false);updateBulkSelection();}
 }
 async function deleteSource(row){
   if(!confirm('این منبع از فهرست Sync حذف شود؟ پیام‌های تاریخی حذف نمی‌شوند.')) return;
   try{
     const r=await fetch('/api/sources/item/'+encodeURIComponent(row.dataset.pt)+'/'+encodeURIComponent(row.dataset.pid),{method:'DELETE'});
     if(!r.ok) throw new Error('HTTP '+r.status);
     await loadSources();
   }catch(e){setMsg($('sourceMsg'),'حذف ناموفق: '+e.message,false);}
 }
 async function loadUsernames(){
  try{
    const d=await api('/api/sources/usernames');
    $('usernameRows').innerHTML='';
    for(const x of d.sources){
      const box=document.createElement('div');box.className='candidate';
      box.innerHTML='<strong>@'+esc(x.username)+'</strong> '+esc(x.label||'')+
        '<div class="muted">وضعیت: '+esc(x.status)+(x.error_code?' • '+esc(x.error_code):'')+'</div>';
      if(x.status==='pending'){
        const b=document.createElement('button');b.type='button';b.textContent='تلاش برای تأیید';
        b.onclick=async()=>{b.disabled=true;try{await api('/api/sources/usernames/'+encodeURIComponent(x.username)+'/resolve',{method:'POST'});setMsg($('usernameMsg'),'شناسه تأیید و به منابع ثبت‌شده اضافه شد.',true);await loadSources();}catch(e){setMsg($('usernameMsg'),e.message,false)}finally{await loadUsernames()}};
        box.appendChild(b);
      }
      const del=document.createElement('button');del.type='button';del.textContent='حذف از صف شناسه‌ها';
      del.onclick=async()=>{if(!confirm('این شناسه از صف پیگیری حذف شود؟'))return;try{await api('/api/sources/usernames/'+encodeURIComponent(x.username),{method:'DELETE'});await loadUsernames();}catch(e){setMsg($('usernameMsg'),e.message,false)}};
      box.appendChild(del);$('usernameRows').appendChild(box);
    }
  }catch(e){setMsg($('usernameMsg'),e.message,false)}
 }
 $('usernameForm').addEventListener('submit',async e=>{
   e.preventDefault();
   try{
     const body={username:$('usernameValue').value.trim(),label:$('usernameLabel').value.trim()};
     await api('/api/sources/usernames',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
     setMsg($('usernameMsg'),'ثبت شد؛ در انتظار تأیید بله است.',true);
     e.target.reset();await loadUsernames();
   }catch(err){setMsg($('usernameMsg'),err.message,false)}
 });
 loadUsernames();
 $('discoverBtn').addEventListener('click',discover);
 $('discoverQ').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();discover();}});
 $('reloadBtn').addEventListener('click',loadSources);
 $('sourceFilter').addEventListener('input',applySourceFilter);
 $('selectVisibleSources').addEventListener('change',e=>{visibleSources().forEach(row=>row.querySelector('.bulk-select').checked=e.target.checked);updateBulkSelection();});
 $('bulkDeleteBtn').addEventListener('click',bulkDeleteSelected);
 $('candidateQ').addEventListener('input',()=>{clearTimeout(window.__candTimer);window.__candTimer=setTimeout(loadCandidates,250);});
 $('manualForm').addEventListener('submit',async e=>{
   e.preventDefault();
   try{
     await api('/api/sources',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({peer_type:Number($('pt').value),peer_id:Number($('pid').value),title:$('manualTitle').value||null,score:Number($('manualScore').value||50),matched_terms:null,enabled:true})});
     e.target.reset(); $('pt').value=2; $('manualScore').value=50; await loadSources();
   }catch(err){setMsg($('sourceMsg'),'افزودن ناموفق: '+err.message,false);}
 });
 loadSources();
})();
</script></body></html>""")


@router.get("/crm/outbox", response_class=HTMLResponse)
def crm_outbox_page(request: Request):
    user = _user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return HTMLResponse("""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CRM Outbox</title><style>body{margin:0}.wrap{max-width:1200px;margin:auto;padding:20px}td,th{padding:10px;text-align:right;font-size:13px}button{padding:8px}</style><link rel="stylesheet" href="/assets/satno-ui.css?v=issue1-nav-3"></head><body class="staff-shell"><div class="wrap"><div class="section-head"><div><h2>صف اتصال SATNO CRM</h2><div class="muted">وضعیت Leadهای انتخاب‌شده و آمادگی اتصال Alpha 2.2</div></div><div class="nav" aria-label="ناوبری اصلی"><a href="/">جست‌وجوی بازار</a><a href="/review">بررسی سرنخ‌ها</a><a href="/sources/manage">مدیریت منابع</a><a href="/status">وضعیت همگام‌سازی</a><a href="/crm/outbox" aria-current="page">صف CRM</a><a href="/admin/users">کاربران</a></div></div><div id="ready" class="metric-grid"></div><div class="card"><table><thead><tr><th>ID</th><th>پیام</th><th>وضعیت</th><th>تلاش</th><th>CRM ID</th><th>HTTP</th><th>خطا</th><th>عملیات</th></tr></thead><tbody id="rows"></tbody></table></div></div><script>function esc(v){var d=document.createElement('div');d.textContent=v==null?'':String(v);return d.innerHTML}async function load(){var a=await fetch('/api/crm/readiness'),b=await fetch('/api/crm/outbox'),rd=await a.json(),o=await b.json();ready.innerHTML='<div class="metric"><div class="label">Connector</div><div class="value">'+esc(rd.connector)+'</div></div><div class="metric"><div class="label">Endpoint</div><div class="value '+(rd.url_configured?'kpi-good':'kpi-warn')+'">'+(rd.url_configured?'آماده':'تنظیم نیست')+'</div></div><div class="metric"><div class="label">Token</div><div class="value '+(rd.token_configured?'kpi-good':'kpi-warn')+'">'+(rd.token_configured?'آماده':'تنظیم نیست')+'</div></div><div class="metric"><div class="label">ارسال زنده</div><div class="value '+(rd.live_delivery_enabled?'kpi-good':'kpi-warn')+'">'+(rd.live_delivery_enabled?'فعال':'غیرفعال')+'</div></div>';var h='';o.forEach(function(x){h+='<tr><td>'+x.id+'</td><td>'+x.message_id+'</td><td>'+esc(x.status)+'</td><td>'+(x.attempts||0)+'</td><td>'+esc(x.crm_lead_id||'')+'</td><td>'+esc(x.last_http_status||'')+'</td><td>'+esc(x.last_error||'')+'</td><td><button onclick="sendOne('+x.id+')">ارسال/تلاش مجدد</button></td></tr>'});rows.innerHTML=h}async function sendOne(id){var r=await fetch('/api/crm/outbox/'+id+'/send',{method:'POST'}),d=await r.json();alert(d.status||d.detail||'نتیجه ثبت شد');load()}load();</script></body></html>""")
