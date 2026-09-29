import tempfile, unittest
from pathlib import Path
import db
from dedup import make_dedup_key
from sync_state import get_checkpoint, save_checkpoint
from sync_engine import apply_batch

OLD_SCHEMA = """
CREATE TABLE messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT, chat_name TEXT, sender_name TEXT,
 text TEXT NOT NULL, sent_at TEXT, category TEXT, brands TEXT, power_values TEXT,
 price_values TEXT, quantities TEXT, phones TEXT, locations TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(external_id, chat_name)
)
"""

class SyncDedupMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); db.DB_PATH=str(Path(self.tmp.name)/"market.db")
    def tearDown(self):
        import gc
        gc.collect()
        self.tmp.cleanup()
    def test_migration_preserves_legacy_duplicate_rows(self):
        with db.connect() as con:
            con.execute(OLD_SCHEMA)
            for _ in range(2):
                con.execute("INSERT INTO messages(chat_name,sender_name,text,sent_at) VALUES (?,?,?,?)", ("a","s","same","2026-09-29T10:00:00"))
        db.init_db()
        with db.connect() as con:
            rows=con.execute("SELECT dedup_key FROM messages ORDER BY id").fetchall()
        self.assertEqual(len(rows),2)
        self.assertEqual(sum(1 for r in rows if r[0] is not None),1)
    def test_external_id_dedup_is_stable_per_chat(self):
        a=make_dedup_key(external_id="42",chat_name="a",text="old")
        b=make_dedup_key(external_id="42",chat_name="a",text="edited")
        c=make_dedup_key(external_id="42",chat_name="b",text="edited")
        self.assertEqual(a,b); self.assertNotEqual(a,c)
    def test_checkpoint_round_trip(self):
        db.init_db(); self.assertIsNone(get_checkpoint("bale:chat:1")); save_checkpoint("bale:chat:1","9001"); self.assertEqual(get_checkpoint("bale:chat:1"),"9001")
    def test_failed_batch_does_not_advance_checkpoint(self):
        checkpoints=[]
        def save(m):
            if m["id"]==2: raise RuntimeError("boom")
            return m["id"]
        with self.assertRaises(RuntimeError):
            apply_batch(source_key="bale:chat:1",messages=[{"id":1},{"id":2}],next_cursor="2",save_fn=save,checkpoint_fn=lambda s,c:checkpoints.append((s,c)))
        self.assertEqual(checkpoints,[])
    def test_duplicate_count_is_reported(self):
        values=iter([1,None,3])
        r=apply_batch(source_key="x",messages=[{},{},{}],next_cursor="3",save_fn=lambda _:next(values),checkpoint_fn=lambda *_:None)
        self.assertEqual((r["inserted"],r["duplicates"]),(2,1))

