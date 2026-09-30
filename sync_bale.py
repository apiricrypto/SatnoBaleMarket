import asyncio
import os

from dotenv import load_dotenv
from bale import BaleClient

from main import MessageIn, save_message
from sync_state import get_checkpoint, save_checkpoint

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

MAX_CHATS = 30
MESSAGES_PER_CHAT = 50


def get_text(message):
    content = getattr(message, "content", None)
    if content:
        text = getattr(content, "text", None)
        if text and text.strip():
            return text.strip()
    return None


def get_source_key(peer):
    peer_type = getattr(peer, "type", "unknown")
    peer_id = getattr(peer, "id", "unknown")
    return f"bale:{peer_type}:{peer_id}"


async def main():
    token = os.getenv("BALE_TOKEN")
    if not token:
        raise SystemExit("BALE_TOKEN پیدا نشد.")

    total_read = 0
    total_text = 0
    total_saved = 0
    total_duplicates = 0
    sender_cache = {}

    async with BaleClient(token) as client:
        selected = []

        async for dialog in client.iter_dialogs(
            limit=500,
            page_size=50,
            resolve_names=True,
        ):
            title = getattr(dialog, "title", "") or ""
            if any(keyword.lower() in title.lower() for keyword in KEYWORDS):
                selected.append(dialog)

        print(f"Solar chats found: {len(selected)}")
        print(f"Syncing first {min(MAX_CHATS, len(selected))} chats...")

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

            try:
                messages = await client.get_messages(
                    peer,
                    limit=MESSAGES_PER_CHAT,
                    page_size=50,
                    load_mode=0,
                    offset_date=-1,
                )
            except Exception as exc:
                print("ERROR:", repr(exc))
                continue

            chat_read = 0
            chat_text = 0
            chat_saved = 0
            chat_duplicates = 0
            newest_cursor = None
            reached_checkpoint = False

            for message in messages:
                rid = str(getattr(message, "rid", "") or "")

                if newest_cursor is None and rid:
                    newest_cursor = rid

                if previous_cursor and rid == previous_cursor:
                    reached_checkpoint = True
                    break

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
                        try:
                            entity = await client.get_entity(sender_id)
                            username = str(getattr(entity, "username", "") or "").lstrip("@")
                            resolved_name = str(getattr(entity, "title", "") or "")
                            sender_cache[sender_id] = (resolved_name or sender_id, username or None)
                        except Exception:
                            sender_cache[sender_id] = (sender_id, None)
                    sender_name, sender_username = sender_cache[sender_id]
                    if sender_username:
                        sender_link = f"https://ble.ir/{sender_username}"

                data = MessageIn(
                    external_id=rid,
                    chat_name=title,
                    sender_name=sender_name,
                    sender_id=sender_id,
                    sender_username=sender_username,
                    sender_link=sender_link,
                    text=text,
                    sent_at=str(getattr(message, "date", "") or ""),
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

    print()
    print("=" * 60)
    print("SYNC COMPLETE")
    print("Messages read :", total_read)
    print("Text messages :", total_text)
    print("New saved     :", total_saved)
    print("Duplicates    :", total_duplicates)


if __name__ == "__main__":
    asyncio.run(main())
