"""Read-only contact probe by default. --apply explicitly updates sender cache only.

An explicit database and group prevent accidental use of an inherited test DB.
Never runs Sync, sends messages, or rewrites historical message records.
"""

import argparse
import asyncio
import os
from pathlib import Path
import sqlite3

from dotenv import load_dotenv
from bale import BaleClient
import db
from sender_contacts import public_username, resolve_contact, save_contact


def selected_senders(database, group, limit):
    con = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT sender_id FROM messages WHERE chat_name=? AND sender_id IS NOT NULL ORDER BY id DESC LIMIT 500",
            (group,),
        ).fetchall()
    finally:
        con.close()
    return list(
        dict.fromkeys(
            str(r[0])
            for r in rows
            if str(r[0]).isascii() and str(r[0]).isdecimal() and int(r[0]) > 0
        )
    )[:limit]


async def probe(args):
    database = Path(args.database).resolve(strict=True)
    ids = selected_senders(database, args.group, args.limit)
    print("DATABASE:", database)
    print("MODE:", "APPLY_CACHE" if args.apply else "READ_ONLY")
    print("SAMPLES:", len(ids))
    if not ids:
        raise RuntimeError("No sender IDs in the exact selected group")
    load_dotenv(Path.cwd() / ".env.local")
    token = (os.getenv("BALE_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(
            "BALE_TOKEN missing; configure on this machine, never paste into chat"
        )
    contacts = []
    async with BaleClient(token) as client:
        for index, sid in enumerate(ids, 1):
            contact = await resolve_contact(client, sid)
            contacts.append(contact)
            print(
                "SAMPLE",
                index,
                "STATUS:",
                contact.error or "public_username",
                "SOURCE:",
                contact.source or "-",
            )
            if contact.link:
                print("LINK:", contact.link)
                if args.expected_username:
                    print(
                        "MATCHES_EXPECTED:", contact.username == args.expected_username
                    )
    if args.apply:
        # Explicit opt-in: additive schema migration and cache update only.
        db.DB_PATH = str(database)
        db.init_db()
        for contact in contacts:
            save_contact(contact)
        print("CACHE_UPDATED:", len(contacts))
    else:
        print("NO_DATABASE_WRITES")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--group", required=True, help="Exact stored group title")
    parser.add_argument("--limit", type=int, choices=range(1, 11), default=3)
    parser.add_argument("--expected-username", type=public_username)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write cache after approved rollout; default is read-only",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(probe(parse_args()), timeout=120))
    except KeyboardInterrupt:
        raise SystemExit("PROBE_CANCELLED")
    except Exception as error:
        print("PROBE_FAILED:", type(error).__name__)
        raise SystemExit(1)
