import os, sqlite3
from pathlib import Path
from dedup import make_dedup_key

DB_PATH = os.getenv("DATABASE_PATH", "satno_market.db")


class ClosingConnection(sqlite3.Connection):
    """SQLite connection that also closes when leaving a with block.

    sqlite3.Connection.__exit__ commits or rolls back but does not close the
    database handle. On Windows that leaves temporary test databases locked.
    """

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect():
    db = Path(DB_PATH)
    if db.parent != Path("."):
        db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db), factory=ClosingConnection)
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
          sender_username TEXT,
          sender_link TEXT,
          text TEXT NOT NULL,
          sent_at TEXT,
          category TEXT,
          brands TEXT,
          product_types TEXT,
          models TEXT,
          power_values TEXT,
          energy_values TEXT,
          price_values TEXT,
          currency_values TEXT,
          quantities TEXT,
          phones TEXT,
          locations TEXT,
          dedup_key TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(external_id, chat_name)
        )''')
        _ensure_column(con, "messages", "sender_id", "TEXT")
        _ensure_column(con, "messages", "sender_username", "TEXT")
        _ensure_column(con, "messages", "sender_link", "TEXT")
        _ensure_column(con, "messages", "product_types", "TEXT")
        _ensure_column(con, "messages", "models", "TEXT")
        _ensure_column(con, "messages", "energy_values", "TEXT")
        _ensure_column(con, "messages", "dedup_key", "TEXT")
        _ensure_column(con, "messages", "currency_values", "TEXT")
        _backfill_dedup_keys(con)
        con.execute("CREATE INDEX IF NOT EXISTS idx_messages_category ON messages(category)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at)")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_dedup_key ON messages(dedup_key) WHERE dedup_key IS NOT NULL")
        con.execute('''
        CREATE TABLE IF NOT EXISTS staff_users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'viewer',
          display_name TEXT,
          is_active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        con.execute("CREATE INDEX IF NOT EXISTS idx_staff_users_active ON staff_users(is_active)")
        con.execute('''
        CREATE TABLE IF NOT EXISTS staff_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          token_hash TEXT NOT NULL UNIQUE,
          expires_at TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          revoked_at TEXT,
          FOREIGN KEY(user_id) REFERENCES staff_users(id)
        )''')
        con.execute("CREATE INDEX IF NOT EXISTS idx_staff_sessions_user_id ON staff_sessions(user_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_staff_sessions_expires_at ON staff_sessions(expires_at)")
        con.execute('''
        CREATE TABLE IF NOT EXISTS source_registry (
          source_key TEXT PRIMARY KEY,
          title TEXT,
          peer_type TEXT,
          peer_id TEXT,
          score INTEGER DEFAULT 0,
          matched_terms TEXT,
          enabled INTEGER DEFAULT 1,
          discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
          last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        con.execute("CREATE INDEX IF NOT EXISTS idx_source_registry_enabled ON source_registry(enabled)")
        con.execute('''
        CREATE TABLE IF NOT EXISTS sync_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          chats_scanned INTEGER DEFAULT 0,
          messages_read INTEGER DEFAULT 0,
          messages_saved INTEGER DEFAULT 0,
          duplicates INTEGER DEFAULT 0,
          status TEXT DEFAULT 'running'
        )''')
        _ensure_column(con, "sync_runs", "dialogs_seen", "INTEGER DEFAULT 0")
        _ensure_column(con, "sync_runs", "error_code", "TEXT")
        _ensure_column(con, "sync_runs", "error_detail", "TEXT")
        con.execute('''
        CREATE TABLE IF NOT EXISTS backfill_state (
          source_key TEXT PRIMARY KEY,
          oldest_cursor TEXT,
          messages_scanned INTEGER DEFAULT 0,
          messages_saved INTEGER DEFAULT 0,
          completed INTEGER DEFAULT 0,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        con.execute('''
        CREATE TABLE IF NOT EXISTS sync_state (
          source_key TEXT PRIMARY KEY,
          cursor TEXT,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        con.execute('''
        CREATE TABLE IF NOT EXISTS sender_directory (
          sender_id TEXT PRIMARY KEY,
          sender_name TEXT,
          sender_username TEXT,
          sender_link TEXT,
          resolved_at TEXT,
          last_error TEXT,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        con.execute("CREATE INDEX IF NOT EXISTS idx_sender_directory_username ON sender_directory(sender_username)")
        con.execute('''
        CREATE TABLE IF NOT EXISTS lead_reviews (
          message_id INTEGER PRIMARY KEY,
          review_status TEXT NOT NULL DEFAULT 'unreviewed',
          reviewed_category TEXT,
          product TEXT,
          brand TEXT,
          model TEXT,
          power TEXT,
          capacity TEXT,
          price TEXT,
          currency TEXT,
          location TEXT,
          contact TEXT,
          notes TEXT,
          reviewed_by TEXT,
          reviewed_at TEXT,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(message_id) REFERENCES messages(id)
        )''')
        con.execute("CREATE INDEX IF NOT EXISTS idx_lead_reviews_status ON lead_reviews(review_status)")
        con.execute('''
        CREATE TABLE IF NOT EXISTS crm_lead_outbox (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          message_id INTEGER NOT NULL,
          idempotency_key TEXT NOT NULL UNIQUE,
          requested_by TEXT,
          payload TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'queued',
          last_error TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          sent_at TEXT,
          FOREIGN KEY(message_id) REFERENCES messages(id)
        )''')
        _ensure_column(con, "crm_lead_outbox", "attempts", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(con, "crm_lead_outbox", "last_attempt_at", "TEXT")
        _ensure_column(con, "crm_lead_outbox", "next_retry_at", "TEXT")
        _ensure_column(con, "crm_lead_outbox", "crm_lead_id", "TEXT")
        _ensure_column(con, "crm_lead_outbox", "crm_status", "TEXT")
        _ensure_column(con, "crm_lead_outbox", "crm_request_id", "TEXT")
        _ensure_column(con, "crm_lead_outbox", "duplicate", "INTEGER")
        _ensure_column(con, "crm_lead_outbox", "last_http_status", "INTEGER")
        _ensure_column(con, "crm_lead_outbox", "receipt", "TEXT")
        con.execute("CREATE INDEX IF NOT EXISTS idx_crm_lead_outbox_status ON crm_lead_outbox(status)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_crm_lead_outbox_retry ON crm_lead_outbox(status,next_retry_at)")
