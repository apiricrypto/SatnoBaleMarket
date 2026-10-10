import asyncio
import os

from bale import BaleClient
from dotenv import load_dotenv

from main import MessageIn, save_message
from sync_bale import (
    canonical_sent_at,
    get_text,
    load_cached_sender,
    load_registry_targets,
    save_resolved_sender,
)

load_dotenv(".env.local")

LIMIT_PER_SOURCE = int(os.getenv("BALE_REPAIR_MESSAGES_PER_SOURCE", "300"))


async def main():
    token = (os.getenv("BALE_TOKEN") or "").strip()
    if not token:
        raise SystemExit("BALE_TOKEN پیدا نشد.")

    targets = load_registry_targets()
    if not targets:
        raise SystemExit("هیچ منبع فعال ثبت نشده است.")

    total_read = 0
    total_text = 0
    total_saved = 0
    total_duplicates = 0
    sender_cache = {}

    async with BaleClient(token) as client:
        for dialog in targets:
            title = getattr(dialog, "title", "") or ""
            peer = getattr(dialog, "peer", None)
            if peer is None:
                continue
            try:
                messages = await client.get_messages(
                    peer,
                    limit=LIMIT_PER_SOURCE,
                    page_size=50,
                    load_mode=0,
                    offset_date=-1,
                )
            except Exception as exc:
                print("SOURCE ERROR:", title, type(exc).__name__)
                continue

            source_saved = 0
            for message in messages:
                total_read += 1
                text = get_text(message)
                if not text:
                    continue
                total_text += 1

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

                rid = str(getattr(message, "rid", "") or "")
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
                mid, _ = save_message(data)
                if mid is not None:
                    total_saved += 1
                    source_saved += 1
                else:
                    total_duplicates += 1
            print(f"{title}: repaired/new={source_saved}")

    print("REPAIR COMPLETE")
    print("Messages read :", total_read)
    print("Text/captions :", total_text)
    print("New saved     :", total_saved)
    print("Duplicates    :", total_duplicates)


if __name__ == "__main__":
    asyncio.run(main())
