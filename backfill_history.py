import asyncio
import os
from dotenv import load_dotenv
from bale import BaleClient

from backfill_engine import BATCH_SIZE, DEFAULT_PER_SOURCE, next_budget, oldest_rid, should_complete
from db import connect, init_db
from main import MessageIn, save_message
from time_utils import canonical_sent_at

load_dotenv(".env.local")

MAX_SOURCES=int(os.getenv("BALE_BACKFILL_MAX_SOURCES","48"))

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
    with connect() as con:
        active={r["source_key"]:dict(r) for r in con.execute("SELECT * FROM source_registry WHERE enabled=1 ORDER BY score DESC LIMIT ?",(MAX_SOURCES,))}
    print("Active sources:",len(active),"| Per-source target:",DEFAULT_PER_SOURCE)
    total_scanned=total_saved=0
    sender_cache={}
    async with BaleClient(token) as client:
        dialogs={}
        async for dialog in client.iter_dialogs(limit=500,page_size=50,resolve_names=True):
            peer=getattr(dialog,"peer",None)
            if peer is not None:
                key=source_key(peer)
                if key in active:
                    dialogs[key]=dialog
        for key,source in active.items():
            dialog=dialogs.get(key)
            if dialog is None:
                print("MISSING:",source["title"]); continue
            peer=getattr(dialog,"peer",None)
            title=getattr(dialog,"title","") or source["title"] or ""
            with connect() as con:
                state=con.execute("SELECT * FROM backfill_state WHERE source_key=?",(key,)).fetchone()
            scanned=int(state["messages_scanned"]) if state else 0
            saved=int(state["messages_saved"]) if state else 0
            cursor=state["oldest_cursor"] if state else None
            completed=bool(state["completed"]) if state else False
            # Repair premature completion created by the first backfill implementation.
            if completed and scanned < DEFAULT_PER_SOURCE:
                completed=False
                with connect() as con:
                    con.execute("UPDATE backfill_state SET completed=0 WHERE source_key=?",(key,))
            budget=next_budget(scanned)
            if completed or budget<=0:
                print("DONE:",title,"| scanned:",scanned,"saved:",saved); continue
            request=min(BATCH_SIZE,budget)
            kwargs=dict(limit=request,page_size=min(50,request),load_mode=0,offset_date=-1)
            # The first pass intentionally overlaps recent history; dedup protects existing rows.
            # Subsequent passes use the SDK cursor when available.
            if cursor:
                kwargs["offset_id"]=cursor
            try:
                messages=await client.get_messages(peer,**kwargs)
            except TypeError:
                # Some bale-sdk builds do not expose offset_id; fail safely instead of advancing state.
                print("CURSOR_UNSUPPORTED:",title); continue
            except Exception as exc:
                print("ERROR:",title,type(exc).__name__); continue
            batch_saved=0
            for message in messages:
                text=get_text(message)
                if not text: continue
                sid=str(getattr(message,"sender_id","") or "")
                sname=sid; username=None; link=None
                if sid:
                    if sid not in sender_cache:
                        try:
                            entity=await client.get_entity(sid)
                            username0=str(getattr(entity,"username","") or "").lstrip("@")
                            name0=str(getattr(entity,"title","") or "") or sid
                            sender_cache[sid]=(name0,username0 or None)
                        except Exception:
                            sender_cache[sid]=(sid,None)
                    sname,username=sender_cache[sid]
                    if username: link=f"https://ble.ir/{username}"
                mid,_=save_message(MessageIn(
                    external_id=str(getattr(message,"rid","") or ""),
                    chat_name=title,sender_name=sname,sender_id=sid,
                    sender_username=username,sender_link=link,text=text,
                    sent_at=canonical_sent_at(getattr(message,"date","")),
                ))
                if mid is not None: batch_saved+=1
            new_cursor=oldest_rid(messages) or cursor
            new_scanned=scanned+len(messages); new_saved=saved+batch_saved
            done=should_complete(len(messages),request,new_scanned,DEFAULT_PER_SOURCE)
            with connect() as con:
                con.execute("""INSERT INTO backfill_state(source_key,oldest_cursor,messages_scanned,messages_saved,completed,updated_at)
                    VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                    ON CONFLICT(source_key) DO UPDATE SET oldest_cursor=excluded.oldest_cursor,messages_scanned=excluded.messages_scanned,
                    messages_saved=excluded.messages_saved,completed=excluded.completed,updated_at=CURRENT_TIMESTAMP""",
                    (key,new_cursor,new_scanned,new_saved,1 if done else 0))
            total_scanned+=len(messages);total_saved+=batch_saved
            print("BACKFILL:",title,"| batch:",len(messages),"new:",batch_saved,"total:",new_scanned,"/",DEFAULT_PER_SOURCE)
    print("="*60)
    print("BACKFILL PASS COMPLETE")
    print("Messages scanned:",total_scanned)
    print("New saved       :",total_saved)

if __name__=="__main__":
    asyncio.run(main())
