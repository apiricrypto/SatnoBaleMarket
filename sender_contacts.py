"""Bounded, identity-checked Bale sender lookup. Never sends messages."""

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from bale import bale_pb2 as pb
from db import connect

LOOKUP_VERSION = 1
LOOKUP_TIMEOUT = 8


def public_username(value):
    value = str(value or "").strip().lstrip("@")
    return value.lower() if re.fullmatch(r"[A-Za-z0-9_]{1,64}", value) else None


@dataclass(frozen=True)
class Contact:
    sender_id: str
    name: str = ""
    username: str | None = None
    error: str | None = None
    source: str | None = None

    @property
    def link(self):
        username = public_username(self.username)
        return f"https://ble.ir/{username}" if username and not self.error else None


async def resolve_contact(client, sender_id):
    """No username/numeric search: request this exact user and validate identity."""
    sid = str(sender_id or "")
    if not sid.isascii() or not sid.isdecimal() or not 0 < int(sid) < 2**31:
        return Contact(sid, error="invalid_sender_id")
    sid = str(int(sid))

    async def lookup():
        request = pb.LoadUsersRequest()
        user_peer = request.peers.add()
        user_peer.uid = int(sid)
        user_peer.accessHash = 0
        response = await client.call(
            "bale.users.v1.Users", "LoadUsers", request, timeout=LOOKUP_TIMEOUT
        )
        users = list(getattr(response, "users", []) or [])
        user = next((u for u in users if str(u.id) == sid), None)
        if users and user is None:
            return Contact(sid, error="identity_mismatch")
        name = str(getattr(user, "name", "") or "")
        username = (
            public_username(user.nick.value)
            if user is not None and user.HasField("nick")
            else None
        )
        if username:
            return Contact(sid, name, username, source="load_users")
        request = pb.GetFullUserRequest()
        request.peer.uid = int(sid)
        request.peer.accessHash = getattr(user, "accessHash", 0) or 0
        response = await client.call(
            "bale.users.v1.Users", "GetFullUser", request, timeout=LOOKUP_TIMEOUT
        )
        full = getattr(response, "fullUser", None)
        # Do not use SDK-normalized IDs: it substitutes the requested ID for 0.
        if full is None or str(full.id) != sid:
            return Contact(sid, error="identity_mismatch")
        username = public_username(full.nick.value) if full.HasField("nick") else None
        return Contact(
            sid,
            str(full.name or name),
            username,
            None if username else "username_unavailable",
            "full_user",
        )

    try:
        return await asyncio.wait_for(lookup(), timeout=LOOKUP_TIMEOUT)
    except Exception as error:
        # Error text may contain tokens, RPC payloads or personal information.
        return Contact(sid, error=type(error).__name__)


def cached_contact(sender_id, now=None):
    with connect() as con:
        row = con.execute(
            "SELECT * FROM sender_directory WHERE sender_id=?", (str(sender_id),)
        ).fetchone()
    return _fresh_contact(row, now)


def _fresh_contact(row, now=None):
    if not row or row["lookup_version"] != LOOKUP_VERSION:
        return None
    try:
        updated = datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        contact = Contact(
            str(row["sender_id"]),
            row["sender_name"] or "",
            row["sender_username"],
            row["last_error"],
        )
        ttl = (
            timedelta(days=7)
            if contact.link
            else (
                timedelta(hours=6)
                if contact.error == "username_unavailable"
                else timedelta(minutes=15)
            )
        )
        age = (now or datetime.now(timezone.utc)) - updated
        return contact if timedelta(0) <= age < ttl else None
    except (ValueError, TypeError, AttributeError):
        return None


def save_contact(contact, now=None):
    now = (now or datetime.now(timezone.utc)).isoformat()
    username = public_username(contact.username) if contact.link else None
    with connect() as con:
        con.execute(
            """INSERT INTO sender_directory
            (sender_id,sender_name,sender_username,sender_link,resolved_at,last_error,updated_at,lookup_version)
            VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(sender_id) DO UPDATE SET
            sender_name=excluded.sender_name,sender_username=excluded.sender_username,
            sender_link=excluded.sender_link,resolved_at=excluded.resolved_at,
            last_error=excluded.last_error,updated_at=excluded.updated_at,lookup_version=excluded.lookup_version""",
            (
                contact.sender_id,
                contact.name or contact.sender_id,
                username,
                contact.link,
                now if contact.link else None,
                contact.error,
                now,
                LOOKUP_VERSION,
            ),
        )


def enrich_messages(rows):
    """Read-only overlay for historical records; never rewrite raw messages."""
    ids = list(dict.fromkeys(str(r.get("sender_id") or "") for r in rows))
    directory = {}
    if ids:
        for offset in range(0, len(ids), 500):
            batch = ids[offset : offset + 500]
            with connect() as con:
                entries = con.execute(
                    "SELECT * FROM sender_directory WHERE sender_id IN ("
                    + ",".join("?" for _ in batch)
                    + ")",
                    batch,
                ).fetchall()
            directory.update({r["sender_id"]: r for r in entries})
    for row in rows:
        entry = directory.get(str(row.get("sender_id") or ""))
        contact = _fresh_contact(entry)
        username = (
            public_username(contact.username) if contact and contact.link else None
        )
        row["sender_username"] = username
        row["sender_link"] = f"https://ble.ir/{username}" if username else None
        row["sender_clickable"] = bool(username)
        row["sender_contact_status"] = "public_username" if username else "unavailable"
        if username and entry["sender_name"]:
            row["sender_name"] = entry["sender_name"]
    return rows
