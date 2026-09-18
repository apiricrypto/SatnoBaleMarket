import os, sqlite3
from pathlib import Path

DB_PATH = os.getenv("DATABASE_PATH", "satno_market.db")

def connect():
    db = Path(DB_PATH)
    if db.parent != Path("."):
        db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute('''
        CREATE TABLE IF NOT EXISTS messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          external_id TEXT,
          chat_name TEXT,
          sender_name TEXT,
          text TEXT NOT NULL,
          sent_at TEXT,
          category TEXT,
          brands TEXT,
          power_values TEXT,
          price_values TEXT,
          quantities TEXT,
          phones TEXT,
          locations TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(external_id, chat_name)
        )''')
        con.execute("CREATE INDEX IF NOT EXISTS idx_messages_category ON messages(category)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at)")
