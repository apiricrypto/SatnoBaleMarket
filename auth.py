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


def list_users():
    init_db()
    with connect() as con:
        rows = con.execute(
            "SELECT id,username,role,display_name,is_active,created_at FROM staff_users ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]

def _active_admin_count(con):
    return con.execute(
        "SELECT COUNT(*) FROM staff_users WHERE role='admin' AND is_active=1"
    ).fetchone()[0]

def _revoke_user_sessions(con, user_id):
    revoked_at = datetime.now(timezone.utc).isoformat()
    con.execute(
        "UPDATE staff_sessions SET revoked_at=? WHERE user_id=? AND revoked_at IS NULL",
        (revoked_at, user_id),
    )

def update_user(user_id, role=None, display_name=None, is_active=None, password=None):
    if role is not None and role not in {"admin","sales","viewer"}:
        raise ValueError("invalid role")
    if is_active is not None and not isinstance(is_active, bool):
        raise ValueError("is_active must be boolean")
    if password is not None and len(password) < 10:
        raise ValueError("password must be at least 10 characters")

    init_db()
    with connect() as con:
        current = con.execute(
            "SELECT id,username,role,display_name,is_active FROM staff_users WHERE id=?",
            (user_id,),
        ).fetchone()
        if not current:
            raise ValueError("user not found")

        next_role = role if role is not None else current["role"]
        next_active = int(is_active) if is_active is not None else current["is_active"]
        if current["role"] == "admin" and current["is_active"]:
            removing_last_admin = (next_role != "admin") or (not next_active)
            if removing_last_admin and _active_admin_count(con) <= 1:
                raise ValueError("cannot remove last active admin")

        updates=[]
        args=[]
        if role is not None:
            updates.append("role=?"); args.append(role)
        if display_name is not None:
            updates.append("display_name=?"); args.append(display_name)
        if is_active is not None:
            updates.append("is_active=?"); args.append(1 if is_active else 0)
        if password is not None:
            updates.append("password_hash=?"); args.append(hash_password(password))

        if updates:
            args.append(user_id)
            con.execute("UPDATE staff_users SET " + ",".join(updates) + " WHERE id=?", args)
            if role is not None or is_active is not None or password is not None:
                _revoke_user_sessions(con, user_id)
            if password is not None:
                _resolve_password_request(con, user_id)

        row = con.execute(
            "SELECT id,username,role,display_name,is_active,created_at FROM staff_users WHERE id=?",
            (user_id,),
        ).fetchone()
    return dict(row)


def change_own_password(user_id, current_password, new_password):
    """Verify the user's current password and revoke every previous session."""
    if not current_password:
        raise ValueError("current password is required")
    if len(new_password) < 12:
        raise ValueError("new password must be at least 12 characters")
    if current_password == new_password:
        raise ValueError("new password must differ from current password")
    init_db()
    with connect() as con:
        row = con.execute(
            "SELECT password_hash,is_active FROM staff_users WHERE id=?",
            (user_id,),
        ).fetchone()
        if not row or not row["is_active"] or not verify_password(current_password, row["password_hash"]):
            raise ValueError("current password is incorrect")
        con.execute(
            "UPDATE staff_users SET password_hash=? WHERE id=?",
            (hash_password(new_password), user_id),
        )
        _revoke_user_sessions(con, user_id)
        _resolve_password_request(con, user_id)
    return True


def _resolve_password_request(con, user_id):
    con.execute(
        "UPDATE password_reset_requests SET resolved_at=? WHERE user_id=? AND resolved_at IS NULL",
        (datetime.now(timezone.utc).isoformat(), user_id),
    )


def request_password_reset(username):
    """One pending request per active account; never return account existence."""
    init_db()
    now = datetime.now(timezone.utc)
    with connect() as con:
        con.execute(
            """INSERT INTO password_reset_requests(user_id,requested_at)
            SELECT id,? FROM staff_users WHERE username=? AND is_active=1
            ON CONFLICT(user_id) DO UPDATE SET requested_at=excluded.requested_at,resolved_at=NULL
            WHERE password_reset_requests.resolved_at IS NOT NULL
              AND password_reset_requests.requested_at<?""",
            (now.isoformat(), username.strip().lower(), (now - timedelta(minutes=15)).isoformat()),
        )


def list_password_reset_requests():
    init_db()
    with connect() as con:
        rows = con.execute(
            """SELECT r.user_id,u.username,u.display_name,r.requested_at
            FROM password_reset_requests r JOIN staff_users u ON u.id=r.user_id
            WHERE r.resolved_at IS NULL AND u.is_active=1 ORDER BY r.requested_at"""
        ).fetchall()
    return [dict(row) for row in rows]


def recover_admin_password(username, new_password):
    """Server operator recovery only. Never expose through an HTTP route."""
    if len(new_password) < 12:
        raise ValueError("new password must be at least 12 characters")
    init_db()
    with connect() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT id FROM staff_users WHERE username=? AND role='admin' AND is_active=1",
            (username.strip().lower(),),
        ).fetchone()
        if not row:
            raise ValueError("active administrator not found")
        con.execute("UPDATE staff_users SET password_hash=? WHERE id=?",
                    (hash_password(new_password), row['id']))
        _revoke_user_sessions(con, row['id'])
        _resolve_password_request(con, row['id'])
