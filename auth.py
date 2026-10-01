import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from db import connect, init_db

ITERATIONS=310000

def hash_password(password, salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),bytes.fromhex(salt),ITERATIONS)
    return "pbkdf2_sha256$%s$%s$%s" % (ITERATIONS,salt,digest.hex())

def verify_password(password, encoded):
    try:
        scheme,iters,salt,digest=encoded.split("$",3)
        if scheme!="pbkdf2_sha256": return False
        candidate=hashlib.pbkdf2_hmac("sha256",password.encode("utf-8"),bytes.fromhex(salt),int(iters)).hex()
        return hmac.compare_digest(candidate,digest)
    except Exception:
        return False

def create_user(username,password,role="viewer",display_name=None):
    if role not in {"admin","sales","viewer"}: raise ValueError("invalid role")
    if len(password)<10: raise ValueError("password must be at least 10 characters")
    init_db()
    with connect() as con:
        con.execute("INSERT INTO staff_users(username,password_hash,role,display_name) VALUES(?,?,?,?)",
                    (username.strip().lower(),hash_password(password),role,display_name))


SESSION_HOURS = 8

def authenticate_user(username, password):
    init_db()
    normalized = username.strip().lower()
    with connect() as con:
        row = con.execute(
            "SELECT id,username,password_hash,role,display_name,is_active FROM staff_users WHERE username=?",
            (normalized,),
        ).fetchone()
    if not row or not row["is_active"] or not verify_password(password, row["password_hash"]):
        return None
    return {k: row[k] for k in ("id","username","role","display_name","is_active")}

def _hash_session_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_session(user_id, ttl_hours=SESSION_HOURS):
    if ttl_hours <= 0:
        raise ValueError("ttl_hours must be positive")
    init_db()
    token = secrets.token_urlsafe(32)
    token_hash = _hash_session_token(token)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
    with connect() as con:
        con.execute(
            "INSERT INTO staff_sessions(user_id,token_hash,expires_at) VALUES(?,?,?)",
            (user_id, token_hash, expires_at),
        )
    return token

def resolve_session(token):
    if not token:
        return None
    init_db()
    token_hash = _hash_session_token(token)
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        row = con.execute(
            """
            SELECT u.id,u.username,u.role,u.display_name,u.is_active,s.expires_at
            FROM staff_sessions s
            JOIN staff_users u ON u.id=s.user_id
            WHERE s.token_hash=? AND s.revoked_at IS NULL
              AND s.expires_at>? AND u.is_active=1
            LIMIT 1
            """,
            (token_hash, now),
        ).fetchone()
    if not row:
        return None
    return {k: row[k] for k in ("id","username","role","display_name","is_active")}

def revoke_session(token):
    if not token:
        return False
    init_db()
    token_hash = _hash_session_token(token)
    revoked_at = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        cur = con.execute(
            "UPDATE staff_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
            (revoked_at, token_hash),
        )
    return cur.rowcount == 1

def role_allows(role, permission):
    permissions = {
        "viewer": {"read"},
        "sales": {"read", "lead:send"},
        "admin": {"read", "lead:send", "message:write", "users:manage"},
    }
    return permission in permissions.get(role, set())
