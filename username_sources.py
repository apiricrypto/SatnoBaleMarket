"""Username-led source enrollment. No guessed Peer IDs or hidden additions."""
import re
from urllib.parse import urlparse

from db import connect, init_db

USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,63}$")

def canonical_username(value):
    value = str(value or "").strip()
    if "://" in value:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or (parsed.hostname or "").lower() not in ("ble.ir", "www.ble.ir"):
            raise ValueError("Only ble.ir public links are supported")
        value = parsed.path.strip("/")
        if "/" in value or parsed.query or parsed.fragment:
            raise ValueError("Use a single public username link")
    username = value.lstrip("@").strip().lower()
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("Invalid public username")
    return username


def enqueue_username(value, label=None, score=50):
    username = canonical_username(value)
    init_db()
    with connect() as con:
        existing = con.execute(
            "SELECT status FROM source_username_queue WHERE username=?", (username,)
        ).fetchone()
        if existing is not None:
            raise ValueError("username already submitted")
        con.execute(
            """INSERT INTO source_username_queue(username,label,score,status)
               VALUES(?,?,?,'pending')""",
            (username, (label or "").strip() or username, max(0, min(100, int(score)))),
        )
    return {"username": username, "status": "pending", "added_to_sync": False}


def list_username_queue():
    init_db()
    with connect() as con:
        return [dict(r) for r in con.execute(
            """SELECT username,label,score,status,error_code,resolved_peer_type,
                      resolved_peer_id,updated_at FROM source_username_queue ORDER BY username"""
        ).fetchall()]


def set_resolution_failure(username, reason):
    with connect() as con:
        con.execute(
            """UPDATE source_username_queue SET error_code=?,updated_at=CURRENT_TIMESTAMP
               WHERE username=? AND status='pending'""",
            (str(reason)[:100], username),
        )


def accept_verified_resolution(username, resolved_username, peer_type, peer_id, title):
    """Only a server-verified exact username can be promoted into the sync registry."""
    username = canonical_username(username)
    if canonical_username(resolved_username) != username:
        raise ValueError("Resolved username mismatch")
    peer_type, peer_id = int(peer_type), int(peer_id)
    if peer_type not in (1, 2) or peer_id <= 0:
        raise ValueError("Invalid verified Bale Peer")
    init_db()
    with connect() as con:
        row = con.execute(
            "SELECT * FROM source_username_queue WHERE username=? AND status='pending'", (username,)
        ).fetchone()
        if row is None:
            raise ValueError("Username not pending")
        key = f"bale:{peer_type}:{peer_id}"
        current = con.execute("SELECT 1 FROM source_registry WHERE source_key=?", (key,)).fetchone()
        if not current:
            con.execute(
                """INSERT INTO source_registry
                (source_key,title,peer_type,peer_id,score,enabled)
                VALUES(?,?,?,?,?,1)""",
                (key, title or row["label"], str(peer_type), str(peer_id), row["score"]),
            )
        con.execute(
            """UPDATE source_username_queue
               SET status='verified',error_code=NULL,resolved_peer_type=?,
                   resolved_peer_id=?,updated_at=CURRENT_TIMESTAMP WHERE username=?""",
            (str(peer_type), str(peer_id), username),
        )
    return {"username": username, "status": "verified", "peer_type": peer_type, "peer_id": peer_id}


def remove_username(value):
    username = canonical_username(value)
    init_db()
    with connect() as con:
        cur = con.execute("DELETE FROM source_username_queue WHERE username=?", (username,))
        if not cur.rowcount:
            raise ValueError("username not found")
    return {"removed": username}
