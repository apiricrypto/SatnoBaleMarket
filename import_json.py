import json, sys
from pathlib import Path
from db import init_db
from main import MessageIn, save_message

source = Path(sys.argv[1] if len(sys.argv) > 1 else "sample_messages.json")
if not source.exists():
    raise SystemExit(f"File not found: {source}")

init_db()
items=json.loads(source.read_text(encoding="utf-8"))
count=0
for item in items:
    mid,_=save_message(MessageIn(**item))
    if mid: count+=1
print(f"Imported {count} new messages from {source}.")
