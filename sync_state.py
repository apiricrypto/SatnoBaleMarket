from db import connect

def get_checkpoint(source_key):
    with connect() as con:
        row = con.execute("SELECT cursor FROM sync_state WHERE source_key=?", (source_key,)).fetchone()
    return row["cursor"] if row else None

def save_checkpoint(source_key, cursor):
    value = None if cursor is None else str(cursor)
    with connect() as con:
        con.execute("INSERT INTO sync_state(source_key,cursor,updated_at) VALUES (?,?,CURRENT_TIMESTAMP) ON CONFLICT(source_key) DO UPDATE SET cursor=excluded.cursor, updated_at=CURRENT_TIMESTAMP", (source_key, value))
    return value
