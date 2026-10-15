"""Read-only transport probe for one authorized registered Bale source.

Does not touch SQLite or create any messages. Token and message contents
are never printed. Set BALE_PROBE_PEER_TYPE/ID (from existing registry).
"""
import asyncio
import os
import time

from dotenv import load_dotenv
from bale import BaleClient
from bale.peer import Peer

load_dotenv(".env.local")


async def check_step(label, operation, timeout):
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(operation(), timeout=timeout)
    except Exception as exc:
        print(f"{label}: FAIL {type(exc).__name__} ({time.monotonic()-start:.1f}s)")
        return None
    print(f"{label}: OK ({time.monotonic()-start:.1f}s)")
    return result


async def run():
    token = (os.getenv("BALE_TOKEN") or "").strip()
    if not token:
        print("BALE_TOKEN: MISSING")
        return
    peer_id_text = (os.getenv("BALE_PROBE_PEER_ID") or "").strip()
    peer_type_text = (os.getenv("BALE_PROBE_PEER_TYPE") or "2").strip()
    try:
        peer_id = int(peer_id_text)
        peer_type = int(peer_type_text)
        if peer_type not in (1, 2) or peer_id <= 0:
            raise ValueError
    except ValueError:
        print("PEER_INPUT: MISSING_OR_INVALID")
        return

    try:
        async with asyncio.timeout(40):
            async with BaleClient(token) as client:
                print("CLIENT_CONNECTION: OPEN")
                peer = Peer.channel(peer_id) if peer_type == 2 else Peer.user(peer_id)
                messages = await check_step(
                    "DIRECT_PEER_READ",
                    lambda: client.get_messages(peer, limit=1, page_size=1, load_mode=0, offset_date=-1),
                    20,
                )
                if messages is not None:
                    print("MESSAGE_COUNT:", len(messages))
    except Exception as exc:
        print("CLIENT_CONNECTION: FAIL", type(exc).__name__)
    print("PROBE_FINISHED")


if __name__ == "__main__":
    asyncio.run(run())
