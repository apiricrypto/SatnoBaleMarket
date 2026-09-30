import asyncio
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from bale import BaleClient

from db import connect, init_db
from source_discovery import score_source

load_dotenv(".env.local")

DIALOG_LIMIT=int(os.getenv("BALE_DISCOVERY_DIALOG_LIMIT","500"))
SAMPLE_MESSAGES=int(os.getenv("BALE_DISCOVERY_SAMPLE_MESSAGES","20"))
THRESHOLD=int(os.getenv("BALE_DISCOVERY_THRESHOLD","4"))

def get_text(message):
    content=getattr(message,"content",None)
    text=getattr(content,"text",None) if content else None
    return text.strip() if text and text.strip() else None

def source_key(peer):
    return f"bale:{getattr(peer,'type','unknown')}:{getattr(peer,'id','unknown')}"

async def main():
    token=os.getenv("BALE_TOKEN")
    if not token:
        raise SystemExit("BALE_TOKEN پیدا نشد.")
    init_db()
    scanned=qualified=errors=0
    now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    async with BaleClient(token) as client:
        async for dialog in client.iter_dialogs(limit=DIALOG_LIMIT,page_size=50,resolve_names=True):
            scanned+=1
            title=getattr(dialog,"title","") or ""
            peer=getattr(dialog,"peer",None)
            if peer is None:
                continue
            texts=[]
            try:
                messages=await client.get_messages(peer,limit=SAMPLE_MESSAGES,page_size=min(20,SAMPLE_MESSAGES),load_mode=0,offset_date=-1)
                for message in messages:
                    text=get_text(message)
                    if text: texts.append(text)
            except Exception:
                errors+=1
            score,matched=score_source(title,texts)
            if score < THRESHOLD:
                continue
            qualified+=1
            key=source_key(peer)
            with connect() as con:
                con.execute("""INSERT INTO source_registry(source_key,title,peer_type,peer_id,score,matched_terms,enabled,discovered_at,last_seen_at)
                    VALUES(?,?,?,?,?,?,1,?,?)
                    ON CONFLICT(source_key) DO UPDATE SET title=excluded.title,peer_type=excluded.peer_type,peer_id=excluded.peer_id,
                    score=excluded.score,matched_terms=excluded.matched_terms,last_seen_at=excluded.last_seen_at""",
                    (key,title,str(getattr(peer,"type","unknown")),str(getattr(peer,"id","unknown")),score,json.dumps(matched,ensure_ascii=False),now,now))
            print(f"SOURCE score={score:02d} | {title}")
    print("="*60)
    print("DISCOVERY COMPLETE")
    print("Dialogs scanned :",scanned)
    print("Market sources  :",qualified)
    print("Read errors     :",errors)

if __name__=="__main__":
    asyncio.run(main())
