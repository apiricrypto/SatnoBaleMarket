import os, sqlite3
from pathlib import Path
from dedup import make_dedup_key

DB_PATH = os.getenv("DATABASE_PATH", "satno_market.db")

def connect():
    db = Path(DB_PATH)
    if db.parent != Path("."):
        db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    return con

def _ensure_column(con, table, column, definition):
    columns = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

def _backfill_dedup_keys(con):
    rows = con.execute("SELECT id,external_id,chat_name,sender_name,sent_at,text FROM messages WHERE dedup_key IS NULL ORDER BY id").fetchall()
    used = {row[0] for row in con.execute("SELECT dedup_key FROM messages WHERE dedup_key IS NOT NULL")}
    for row in rows:
        key = make_dedup_key(
            external_id=row["external_id"], chat_name=row["chat_name"],
            sender_name=row["sender_name"], sent_at=row["sent_at"], text=row["text"]
        )
        if key in used:
            continue  # preserve legacy duplicate rows; leave duplicate key NULL
        con.execute("UPDATE messages SET dedup_key=? WHERE id=?", (key, row["id"]))
        used.add(key)

def init_db():
    with connect() as con:
        con.execute('''
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          external_id TEXT,
          chat_name TEXT,
          sender_name TEXT,
          sender_id TEXT,
          text TEXT NOT NULL,
          sent_at TEXT,
          category TEXT,
          brands TEXT,
          product_types TEXT,
          models TEXT,
          power_values TEXT,
          energy_values TEXT,
          price_values TEXT,
          quantities TEXT,
          phones TEXT,
          locations TEXT,
          dedup_key TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(external_id, chat_name)
        )''')
        _ensure_column(con, "messages", "sender_id", "TEXT")
        _ensure_column(con, "messages", "product_types", "TEXT")
        _ensure_column(con, "messages", "models", "TEXT")
        _ensure_column(con, "messages", "energy_values", "TEXT")
        _ensure_column(con, "messages", "dedup_key", "TEXT")
        _backfill_dedup_keys(con)
        con.execute("CREATE INDEX IF NOT EXISTS idx_messages_category ON messages(category)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at)")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_dedup_key ON messages(dedup_key) WHERE dedup_key IS NOT NULL")
        con.execute('''
        CREATE TABLE IF NOT EXISTS sync_state (
          source_key TEXT PRIMARY KEY,
          cursor TEXT,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
