"""Read-only Bale SDK transport and dialog diagnostic.

Run: python tools/diagnose_bale_discovery.py
Does not modify SQLite, registry, or Bale account.
"""
import asyncio
import os
from collections import Counter
from dotenv import load_dotenv
from bale import BaleClient

load_dotenv(".env.local")

TARGET_USERNAME = "partonorpars"
TITLE_TERMS = ("پرتو", "نور پارس", "partonorpars")
MAX_DIALOGS = 3000

def normalize(s):
    return str(s or "").casefold().replace("ي", "ی").replace("ك", "ک").replace("\u200c", "").replace(" ", "")

def describe(dialog):
    peer = getattr(dialog, "peer", None)
    return {
        "title": str(getattr(dialog, "title", "") or "")[:120],
        "username": str(getattr(dialog, "username", "") or "")[:120],
        "peer_type": getattr(peer, "type", None),
        "peer_id": getattr(peer, "id", None),
    }

async def diagnostic():
    token = (os.getenv("BALE_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("BALE_TOKEN missing in server environment")
    stats = Counter()
    matches = []
    async with BaleClient(token) as client:
        # Probe public username separately. Resolve failures must not be
        # presented as evidence that the channel does not exist.
        for raw in (TARGET_USERNAME, "@" + TARGET_USERNAME):
            try:
                result = await asyncio.wait_for(client.resolve(raw), timeout=8)
                peer = getattr(result, "peer", None)
                print("RESOLVE", raw, "type=", getattr(peer, "type", None),
                      "id=", getattr(peer, "id", None))
            except Exception as exc:
                print("RESOLVE", raw, "error=", type(exc).__name__)
        async for dialog in client.iter_dialogs(
            limit=MAX_DIALOGS, page_size=50, resolve_names=True
        ):
            stats["total"] += 1
            d = describe(dialog)
            stats["type_" + str(d["peer_type"])] += 1
            if not d["title"]:
                stats["empty_title"] += 1
            if d["username"]:
                stats["with_username"] += 1
            probe = normalize(d["title"] + " " + d["username"])
            if any(normalize(term) in probe for term in TITLE_TERMS):
                matches.append(d)
        print("STATS", dict(sorted(stats.items())))
        print("MATCH_COUNT", len(matches))
        for row in matches[:20]:
            print("MATCH", row)
        if not matches:
            print("OUTCOME NOT_FOUND_IN_SDK_OUTPUT")
            print("NOTE Not proof of non-membership; inspect SDK transport, pagination and account context.")

def main():
    try:
        asyncio.run(asyncio.wait_for(diagnostic(), timeout=240))
    except Exception as exc:
        print("DIAGNOSTIC_ERROR", type(exc).__name__)
        raise SystemExit(1)

if __name__ == "__main__":
    main()
