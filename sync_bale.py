import asyncio
import os

from dotenv import load_dotenv
from bale import BaleClient
from bale.peer import Peer
from types import SimpleNamespace

from main import MessageIn, save_message
from db import connect, init_db
from sync_state import get_checkpoint, save_checkpoint
from time_utils import canonical_sent_at

load_dotenv(".env.local")

KEYWORDS = [
    "solar",
    "pv",
    "سولار",
    "خورشیدی",
    "پنل",
    "اینورتر",
    "سانورتر",
    "باتری",
    "نیروگاه",
    "تجهیزات",
]

MAX_CHATS = int(os.getenv("BALE_MAX_CHATS", "500"))
MESSAGES_PER_CHAT = int(os.getenv("BALE_MESSAGES_PER_CHAT", "200"))
OVERLAP_AFTER_CHECKPOINT = int(os.getenv("BALE_SYNC_OVERLAP_MESSAGES", "50"))

def load_cached_sender(sender_id):
    if not sender_id:
        return None
    with connect() as con:
        row = con.execute(
            "SELECT sender_name,sender_username,sender_link FROM sender_directory WHERE sender_id=?",
            (sender_id,),
        ).fetchone()
    if not row:
        return None
    return (row["sender_name"] or sender_id, row["sender_username"], row["sender_link"])

def save_resolved_sender(sender_id, name, username, link, error=None):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        con.execute(
            """
            INSERT INTO sender_directory(sender_id,sender_name,sender_username,sender_link,resolved_at,last_error,updated_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(sender_id) DO UPDATE SET
              sender_name=excluded.sender_name,
              sender_username=excluded.sender_username,
              sender_link=excluded.sender_link,
              resolved_at=excluded.resolved_at,
              last_error=excluded.last_error,
              updated_at=excluded.updated_at
            """,
            (sender_id, name, username, link, now if not error else None, error, now),
        )


def classify_sync_health(dialogs_seen, registry_count, selected_count):
    if dialogs_seen == 0 and registry_count > 0:
        return (
            "degraded",
            "bale_no_dialogs",
            "Bale client returned zero dialogs while active sources exist. "
            "Check Bale transport/protocol compatibility or token validity.",
        )
    if dialogs_seen > 0 and registry_count > 0 and selected_count == 0:
        return (
            "degraded",
            "bale_no_source_matches",
            "Bale dialogs were returned, but none matched the active source registry or market keywords.",
        )
    return ("ok", None, None)


def registry_row_to_target(row):
    try:
        peer_type = int(row["peer_type"])
        peer_id = int(row["peer_id"])
    except (TypeError, ValueError, KeyError):
        return None
    if peer_type == 1:
        peer = Peer.user(peer_id)
    elif peer_type == 2:
        peer = Peer.channel(peer_id)
    else:
        peer = Peer(peer_id, peer_type, 1)
    return SimpleNamespace(title=row["title"] or row["source_key"], peer=peer)


def load_registry_targets():
    with connect() as con:
        rows = con.execute(
            """SELECT source_key,title,peer_type,peer_id
               FROM source_registry
               WHERE enabled=1
               ORDER BY score DESC, title"""
        ).fetchall()
    targets = []
    for row in rows:
        target = registry_row_to_target(row)
        if target is not None:
            targets.append(target)
    return targets


def get_text(message):
    """Extract searchable text from both text posts and media captions."""
    content = getattr(message, "content", None)
    if not content:
        return None
    text = getattr(content, "text", None)
    if text and str(text).strip():
        return str(text).strip()
    media = getattr(content, "media", None)
    caption = getattr(media, "caption", None) if media is not None else None
    if caption and str(caption).strip():
        return str(caption).strip()
    return None


def get_source_key(peer):
    peer_type = getattr(peer, "type", "unknown")
    peer_id = getattr(peer, "id", "unknown")
    return f"bale:{peer_type}:{peer_id}"


async def main():
    init_db()
    from datetime import datetime, timezone
    started_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with connect() as con:
        run_id=con.execute("INSERT INTO sync_runs(started_at) VALUES (?)",(started_at,)).lastrowid
    token = os.getenv("BALE_TOKEN")
    if not token:
        raise SystemExit("BALE_TOKEN پیدا نشد.")

    total_read = 0
    total_text = 0
    total_saved = 0
    total_duplicates = 0
    sender_cache = {}
    dialogs_seen = 0
    chats_scanned = 0
    registry_count = 0
    sync_status = "ok"
    error_code = None
    error_detail = None
    discovery_mode = "dialogs"
    source_attempts = 0
    source_successes = 0
    source_failures = 0

    async with BaleClient(token) as client:
        selected = []
        with connect() as con:
            registry_rows=con.execute(
                "SELECT source_key,COALESCE(score,0) AS score FROM source_registry WHERE enabled=1"
            ).fetchall()
        registry_scores={r["source_key"]: int(r["score"] or 0) for r in registry_rows}
        registry_keys=set(registry_scores)
        registry_count = len(registry_keys)

        async for dialog in client.iter_dialogs(
            limit=500,
            page_size=50,
            resolve_names=True,
        ):
            dialogs_seen += 1
            title = getattr(dialog, "title", "") or ""
            peer = getattr(dialog, "peer", None)
            key = get_source_key(peer) if peer is not None else ""
            if key in registry_keys or any(keyword.lower() in title.lower() for keyword in KEYWORDS):
                selected.append(dialog)

        # Explicit source score is an operator-controlled priority. Registered
        # sources always sort ahead of keyword-only discoveries; higher scores
        # are scanned first when BALE_MAX_CHATS limits the run.
        selected.sort(
            key=lambda d: (
                1 if get_source_key(getattr(d, "peer", None)) in registry_keys else 0,
                registry_scores.get(get_source_key(getattr(d, "peer", None)), 0),
            ),
            reverse=True,
        )

        if dialogs_seen == 0 and registry_count > 0:
            fallback = load_registry_targets()
            if fallback:
                selected = fallback
                discovery_mode = "registry-fallback"

        print(f"Dialogs seen: {dialogs_seen}")
        print(f"Discovery mode: {discovery_mode}")
        print(f"Market sources found: {len(selected)}")
        print(f"Syncing first {min(MAX_CHATS, len(selected))} chats...")
        chats_scanned = min(MAX_CHATS, len(selected))

        sync_status, error_code, error_detail = classify_sync_health(
            dialogs_seen, registry_count, len(selected) if discovery_mode == "dialogs" else 0
        )

        for dialog in selected[:MAX_CHATS]:
            title = getattr(dialog, "title", "") or ""
            peer = getattr(dialog, "peer", None)

            if peer is None:
                continue

            source_key = get_source_key(peer)
            previous_cursor = get_checkpoint(source_key)

            print()
            print("=" * 60)
            print("CHAT:", title)
            print("Checkpoint:", previous_cursor or "FIRST SYNC")

            source_attempts += 1
            try:
                messages = await client.get_messages(
                    peer,
                    limit=MESSAGES_PER_CHAT,
                    page_size=50,
                    load_mode=0,
                    offset_date=-1,
                )
            except Exception as exc:
                source_failures += 1
                print("ERROR:", repr(exc))
                continue

            source_successes += 1
            chat_read = 0
            chat_text = 0
            chat_saved = 0
            chat_duplicates = 0
            newest_cursor = None
            reached_checkpoint = False
            overlap_remaining = 0

            for message in messages:
                rid = str(getattr(message, "rid", "") or "")

                if newest_cursor is None and rid:
                    newest_cursor = rid

                if previous_cursor and rid == previous_cursor and not reached_checkpoint:
                    reached_checkpoint = True
                    overlap_remaining = OVERLAP_AFTER_CHECKPOINT
                    continue
                if reached_checkpoint:
                    if overlap_remaining <= 0:
                        break
                    overlap_remaining -= 1

                total_read += 1
                chat_read += 1

                text = get_text(message)
                if not text:
                    continue

                total_text += 1
                chat_text += 1

                sender_id = str(getattr(message, "sender_id", "") or "")
                sender_name = sender_id
                sender_username = None
                sender_link = None
                if sender_id:
                    if sender_id not in sender_cache:
                        cached = load_cached_sender(sender_id)
                        if cached:
                            sender_cache[sender_id] = cached
                        else:
                            try:
                                entity = await client.get_entity(sender_id)
                                username = str(getattr(entity, "username", "") or "").lstrip("@")
                                resolved_name = str(getattr(entity, "title", "") or "") or sender_id
                                link = f"https://ble.ir/{username}" if username else None
                                sender_cache[sender_id] = (resolved_name, username or None, link)
                                save_resolved_sender(sender_id, resolved_name, username or None, link)
                            except Exception as exc:
                                sender_cache[sender_id] = (sender_id, None, None)
                                save_resolved_sender(sender_id, sender_id, None, None, type(exc).__name__)
                    sender_name, sender_username, sender_link = sender_cache[sender_id]

                data = MessageIn(
                    external_id=rid,
                    chat_name=title,
                    sender_name=sender_name,
                    sender_id=sender_id,
                    sender_username=sender_username,
                    sender_link=sender_link,
                    text=text,
                    sent_at=canonical_sent_at(getattr(message, "date", "")),
                )

                mid, analysis = save_message(data)

                if mid is not None:
                    total_saved += 1
                    chat_saved += 1
                    print(
                        "NEW:",
                        analysis["category"],
                        "|",
                        text[:100].replace("\n", " "),
                    )
                else:
                    total_duplicates += 1
                    chat_duplicates += 1

            if newest_cursor:
                save_checkpoint(source_key, newest_cursor)

            print(
                f"Read: {chat_read} | "
                f"Text: {chat_text} | "
                f"New: {chat_saved} | "
                f"Duplicate: {chat_duplicates} | "
                f"Checkpoint hit: {reached_checkpoint}"
            )

        if discovery_mode == "registry-fallback":
            if source_successes > 0:
                sync_status = "ok"
                error_code = None
                error_detail = None
            else:
                sync_status = "degraded"
                error_code = "bale_registry_fallback_failed"
                error_detail = (
                    f"LoadDialogs returned zero dialogs and direct registry fallback "
                    f"failed for {source_failures}/{source_attempts} sources."
                )

    print()
    print("=" * 60)
    print("SYNC COMPLETE")
    print("Messages read :", total_read)
    print("Text messages :", total_text)
    print("New saved     :", total_saved)
    print("Duplicates    :", total_duplicates)
    print("Source attempts:", source_attempts)
    print("Source success :", source_successes)
    print("Source failures:", source_failures)
    print("Discovery mode :", discovery_mode)
    print("Sync status   :", sync_status)
    if error_code:
        print("Sync warning  :", error_code)
    finished_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with connect() as con:
        con.execute(
            """UPDATE sync_runs
               SET finished_at=?,chats_scanned=?,messages_read=?,messages_saved=?,duplicates=?,
                   dialogs_seen=?,status=?,error_code=?,error_detail=?
               WHERE id=?""",
            (
                finished_at,chats_scanned,total_read,total_saved,total_duplicates,
                dialogs_seen,sync_status,error_code,error_detail,run_id
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
