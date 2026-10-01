import asyncio
import os
from dotenv import load_dotenv
from bale import BaleClient

from db import connect, init_db
from main import MessageIn, save_message
from time_utils import canonical_sent_at

load_dotenv(".env.local")

MAX_SOURCES=int(os.getenv("BALE_BACKFILL_MAX_SOURCES","48"))
PER_SOURCE=int(os.getenv("BALE_BACKFILL_PER_SOURCE","1000"))
PAGE_SIZE=int(os.getenv("BALE_BACKFILL_PAGE_SIZE","50"))

def get_text(message):
    content=getattr(message,"content",None)
    text=getattr(content,"text",None) if content else None
    return text.strip() if text and text.strip() else None

def source_key(peer):
    return f"bale:{getattr(peer,'type','unknown')}:{getattr(peer,'id','unknown')}"

async def main():
    token=os.getenv("BALE_TOKEN")
    if not token: raise SystemExit("BALE_TOKEN پیدا نشد.")
    init_db()
    with connect() as con:
        active={r["source_key"]:dict(r) for r in con.execute("SELECT * FROM source_registry WHERE enabled=1 ORDER BY score DESC LIMIT ?",(MAX_SOURCES,))}
    print("Active sources:",len(active),"| History target:",PER_SOURCE)
    total_scanned=total_saved=0
    sender_cache={}
    async with BaleClient(token) as client:
        dialogs={}
        async for dialog in client.iter_dialogs(limit=500,page_size=50,resolve_names=True):
            peer=getattr(dialog,"peer",None)
            if peer is not None and source_key(peer) in active:
                dialogs[source_key(peer)]=dialog
        for key,source in active.items():
            dialog=dialogs.get(key)
            if not dialog:
                print("MISSING:",source["title"]); continue
            peer=getattr(dialog,"peer",None)
            title=getattr(dialog,"title","") or source["title"] or ""
            scanned=saved=0
            oldest=None
            try:
                async for message in client.iter_messages(peer,limit=PER_SOURCE,offset_date=-1,load_mode=2,page_size=PAGE_SIZE):
                    scanned+=1
                    rid=str(getattr(message,"rid","") or "")
                    if rid: oldest=rid
                    text=get_text(message)
                    if not text: continue
                    sid=str(getattr(message,"sender_id","") or "")
                    sname=sid; username=None; link=None
                    if sid:
                        if sid not in sender_cache:
                            try:
                                entity=await client.get_entity(sid)
                                u=str(getattr(entity,"username","") or "").lstrip("@")
                                n=str(getattr(entity,"title","") or "") or sid
                                sender_cache[sid]=(n,u or None)
                            except Exception:
                                sender_cache[sid]=(sid,None)
                        sname,username=sender_cache[sid]
                        if username: link=f"https://ble.ir/{username}"
                    mid,_=save_message(MessageIn(external_id=rid,chat_name=title,sender_name=sname,sender_id=sid,sender_username=username,sender_link=link,text=text,sent_at=canonical_sent_at(getattr(message,"date",""))))
                    if mid is not None: saved+=1
            except Exception as exc:
                print("ERROR:",title,type(exc).__name__,str(exc)[:120]); continue
            with connect() as con:
                con.execute("""INSERT INTO backfill_state(source_key,oldest_cursor,messages_scanned,messages_saved,completed,updated_at)
                    VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
                    ON CONFLICT(source_key) DO UPDATE SET oldest_cursor=excluded.oldest_cursor,messages_scanned=excluded.messages_scanned,
                    messages_saved=backfill_state.messages_saved+excluded.messages_saved,completed=excluded.completed,updated_at=CURRENT_TIMESTAMP""",
                    (key,oldest,scanned,saved,1 if scanned<PER_SOURCE else 0))
            total_scanned+=scanned; total_saved+=saved
            print("HISTORY:",title,"| scanned:",scanned,"new:",saved)
    print("="*60)
    print("HISTORY INDEX COMPLETE")
    print("Messages scanned:",total_scanned)
    print("New saved       :",total_saved)

if __name__=="__main__":
    asyncio.run(main())
