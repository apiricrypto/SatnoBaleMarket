import asyncio
import os

from dotenv import load_dotenv
from bale import BaleClient

from db import connect, init_db

load_dotenv(".env.local")

async def main():
    token=os.getenv("BALE_TOKEN")
    if not token:
        raise SystemExit("BALE_TOKEN پیدا نشد.")
    init_db()
    with connect() as con:
        rows=con.execute("""
            SELECT DISTINCT sender_id
            FROM messages
            WHERE sender_id IS NOT NULL AND sender_id != ''
              AND (sender_username IS NULL OR sender_username = '')
        """).fetchall()
    print("Senders to resolve:", len(rows))
    resolved=0
    async with BaleClient(token) as client:
        for row in rows:
            sender_id=str(row[0])
            try:
                entity=await client.get_entity(sender_id)
                username=str(getattr(entity,"username","") or "").lstrip("@")
                name=str(getattr(entity,"title","") or "") or sender_id
                link=f"https://ble.ir/{username}" if username else None
                with connect() as con:
                    con.execute(
                        "UPDATE messages SET sender_name=?,sender_username=?,sender_link=? WHERE sender_id=?",
                        (name,username or None,link,sender_id),
                    )
                resolved += 1
            except Exception as exc:
                print("SKIP:", sender_id, type(exc).__name__)
    print("Resolved:", resolved)

if __name__ == "__main__":
    asyncio.run(main())
