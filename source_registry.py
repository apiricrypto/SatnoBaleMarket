from datetime import datetime, timezone

from db import connect, init_db


def _source_key(peer_type, peer_id):
    try:
        peer_type = int(peer_type)
        peer_id = int(peer_id)
    except (TypeError, ValueError):
        raise ValueError("peer_type and peer_id must be integers") from None
    if peer_type not in (1, 2):
        raise ValueError("peer_type must be 1 (user) or 2 (channel/group)")
    return f"bale:{peer_type}:{peer_id}", str(peer_type), str(peer_id)


def list_sources():
    init_db()
    with connect() as con:
        rows = con.execute(
            """SELECT source_key,title,peer_type,peer_id,score,matched_terms,enabled,
                      discovered_at,last_seen_at
               FROM source_registry
               ORDER BY enabled DESC, score DESC, title"""
        ).fetchall()
    return [dict(row) for row in rows]


def add_source(peer_type, peer_id, title=None, score=0, matched_terms=None, enabled=True):
    init_db()
    key, peer_type, peer_id = _source_key(peer_type, peer_id)
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        if con.execute("SELECT 1 FROM source_registry WHERE source_key=?", (key,)).fetchone():
            raise ValueError("source already exists")
        con.execute(
            """INSERT INTO source_registry
               (source_key,title,peer_type,peer_id,score,matched_terms,enabled,discovered_at,last_seen_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                key,
                (title or key).strip(),
                peer_type,
                peer_id,
                int(score or 0),
                matched_terms,
                1 if enabled else 0,
                now,
                now,
            ),
        )
        row = con.execute("SELECT * FROM source_registry WHERE source_key=?", (key,)).fetchone()
    return dict(row)


def update_source(source_key, title=None, score=None, matched_terms=None, enabled=None):
    init_db()
    updates = []
    args = []
    if title is not None:
        updates.append("title=?"); args.append(str(title).strip())
    if score is not None:
        updates.append("score=?"); args.append(int(score))
    if matched_terms is not None:
        updates.append("matched_terms=?"); args.append(matched_terms)
    if enabled is not None:
        updates.append("enabled=?"); args.append(1 if enabled else 0)
    if not updates:
        with connect() as con:
            row = con.execute("SELECT * FROM source_registry WHERE source_key=?", (source_key,)).fetchone()
        if not row:
            raise ValueError("source not found")
        return dict(row)
    args.append(source_key)
    with connect() as con:
        cur = con.execute(
            "UPDATE source_registry SET " + ",".join(updates) + " WHERE source_key=?",
            args,
        )
        if cur.rowcount != 1:
            raise ValueError("source not found")
        row = con.execute("SELECT * FROM source_registry WHERE source_key=?", (source_key,)).fetchone()
    return dict(row)


def delete_source(source_key):
    init_db()
    with connect() as con:
        cur = con.execute("DELETE FROM source_registry WHERE source_key=?", (source_key,))
        if cur.rowcount != 1:
            raise ValueError("source not found")
        con.execute("DELETE FROM sync_state WHERE source_key=?", (source_key,))
        con.execute("DELETE FROM backfill_state WHERE source_key=?", (source_key,))
    return True
