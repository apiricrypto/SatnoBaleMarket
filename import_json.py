import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import init_db
from app.main import MessageIn, save_message

if len(sys.argv) < 2:
    raise SystemExit("Usage: python scripts/import_json.py path/to/messages.json")

init_db()
items=json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
count=0
for item in items:
    mid,_=save_message(MessageIn(**item))
    if mid: count+=1
print(f"Imported {count} new messages.")
