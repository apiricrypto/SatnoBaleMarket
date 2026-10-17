import os
import tempfile
from pathlib import Path
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from bale import bale_pb2 as pb
from bale.peer import Resolver, PeerCache
import db
from sender_contacts import (
    Contact,
    resolve_contact,
    save_contact,
    cached_contact,
    enrich_messages,
)


class SenderContactsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = db.DB_PATH
        db.DB_PATH = os.path.join(self.tmp.name, "contacts.db")
        db.init_db()

    def tearDown(self):
        db.DB_PATH = self.previous
        self.tmp.cleanup()

    def client(self, uid=123, username="sample_member", full_username=None):
        response = pb.LoadUsersResponse()
        user = response.users.add()
        user.id = uid
        user.accessHash = 99
        user.name = "Sample member"
        if username is not None:
            user.nick.value = username
        full = pb.GetFullUserResponse()
        full.fullUser.id = uid
        full.fullUser.name = "Sample member"
        if full_username is not None:
            full.fullUser.nick.value = full_username

        async def rpc(service, method, request, **kwargs):
            if method == "LoadUsers":
                return response
            if method == "GetFullUser":
                return full
            raise AssertionError("Unexpected RPC")

        client = SimpleNamespace(call=AsyncMock(side_effect=rpc), full_response=full)
        client.resolver = Resolver(client, PeerCache())
        return client

    async def test_reads_public_username_from_raw_load_users_without_search(self):
        contact = await resolve_contact(self.client(), "123")
        self.assertEqual(contact.link, "https://ble.ir/sample_member")
        self.assertEqual(contact.sender_id, "123")
        self.assertEqual(contact.source, "load_users")

    async def test_full_profile_fallback_when_load_users_omits_nick(self):
        contact = await resolve_contact(
            self.client(username=None, full_username="@member_full"), "123"
        )
        self.assertEqual(contact.link, "https://ble.ir/member_full")
        self.assertEqual(contact.source, "full_user")

    async def test_mismatched_identity_cannot_create_link(self):
        contact = await resolve_contact(self.client(uid=999), "123")
        self.assertIsNone(contact.link)
        self.assertEqual(contact.error, "identity_mismatch")

    async def test_mismatched_full_profile_cannot_create_link(self):
        client = self.client(username=None)
        client.full_response.fullUser.id = 999
        client.full_response.fullUser.nick.value = "wrong_person"
        self.assertIsNone((await resolve_contact(client, "123")).link)

    async def test_missing_full_profile_id_cannot_be_inferred_from_request(self):
        client = self.client(username=None, full_username="member")
        client.full_response.fullUser.id = 0
        self.assertIsNone((await resolve_contact(client, "123")).link)

    async def test_invalid_username_never_becomes_url(self):
        client = self.client(username="evil/path?redirect=1")
        client.full_response.fullUser.nick.value = "https://evil.invalid"
        self.assertIsNone((await resolve_contact(client, "123")).link)

    async def test_errors_do_not_expose_credentials_or_escape(self):
        client = self.client()
        client.call.side_effect = RuntimeError("secret token should not escape")
        contact = await resolve_contact(client, "123")
        self.assertEqual(contact.error, "RuntimeError")
        self.assertIsNone(contact.link)

    async def test_invalid_id_does_not_trigger_rpc(self):
        client = self.client()
        self.assertIsNone((await resolve_contact(client, "@someone")).link)
        client.call.assert_not_awaited()

    async def test_sync_saves_group_sender_with_bounded_resolution(self):
        import sync_bale
        from source_registry import add_source

        add_source(2, 900, "Test group", enabled=True)
        with db.connect() as con:
            run_id = con.execute(
                "INSERT INTO sync_runs(started_at) VALUES('2026-10-17T00:00:00Z')"
            ).lastrowid
        client = self.client()
        client.get_messages = AsyncMock(
            return_value=[
                SimpleNamespace(
                    rid="test-contact-1",
                    sender_id=123,
                    date="2026-10-17T00:00:00Z",
                    content=SimpleNamespace(text="فروش پنل خورشیدی"),
                )
            ]
        )
        with patch.object(sync_bale, "BaleClient") as factory, patch.dict(
            os.environ, {"BALE_TOKEN": "test-only"}
        ):
            factory.return_value.__aenter__.return_value = client
            factory.return_value.__aexit__.return_value = False
            await sync_bale._sync_once(run_id)
        with db.connect() as con:
            row = con.execute("SELECT sender_link FROM messages").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "https://ble.ir/sample_member")

    async def test_sync_limits_lookups_and_still_saves_all_messages(self):
        import sync_bale
        from source_registry import add_source

        add_source(2, 900, "Test group", enabled=True)
        with db.connect() as con:
            run_id = con.execute(
                "INSERT INTO sync_runs(started_at) VALUES('2026-10-17T00:00:00Z')"
            ).lastrowid
        client = self.client()
        client.get_messages = AsyncMock(
            return_value=[
                SimpleNamespace(
                    rid="contact-budget-" + str(i),
                    sender_id=100 + i,
                    date="2026-10-17T00:00:00Z",
                    content=SimpleNamespace(text="فروش پنل " + str(i)),
                )
                for i in range(12)
            ]
        )

        async def lookup(client, sid):
            return Contact(sid, "Sample", "member_" + sid)

        with patch.object(sync_bale, "BaleClient") as factory, patch.object(
            sync_bale, "resolve_contact", side_effect=lookup
        ) as resolver, patch.dict(os.environ, {"BALE_TOKEN": "test-only"}):
            factory.return_value.__aenter__.return_value = client
            factory.return_value.__aexit__.return_value = False
            await sync_bale._sync_once(run_id)
        with db.connect() as con:
            count = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        self.assertEqual(count, 12)
        self.assertEqual(resolver.await_count, 10)

    async def test_group_probe_defaults_to_read_only_database(self):
        import hashlib
        import backfill_senders
        from main import save_message, MessageIn

        save_message(
            MessageIn(text="Demo message", sender_id="123", chat_name="Test group")
        )
        before = hashlib.sha256(Path(db.DB_PATH).read_bytes()).hexdigest()
        args = SimpleNamespace(
            database=db.DB_PATH,
            group="Test group",
            limit=3,
            apply=False,
            expected_username=None,
        )
        with patch.object(backfill_senders, "BaleClient") as factory, patch.dict(
            os.environ, {"BALE_TOKEN": "test-only"}
        ):
            factory.return_value.__aenter__.return_value = self.client()
            factory.return_value.__aexit__.return_value = False
            await backfill_senders.probe(args)
        after = hashlib.sha256(Path(db.DB_PATH).read_bytes()).hexdigest()
        self.assertEqual(before, after)
        with db.connect() as con:
            self.assertEqual(
                con.execute("SELECT COUNT(*) FROM sender_directory").fetchone()[0], 0
            )

    def test_recent_negative_cache_expires_and_legacy_cache_is_not_trusted(self):
        now = datetime.now(timezone.utc)
        contact = Contact("123", "Sample", error="username_unavailable")
        save_contact(contact, now=now)
        self.assertIsNotNone(cached_contact("123", now=now + timedelta(minutes=5)))
        self.assertIsNone(cached_contact("123", now=now + timedelta(hours=7)))
        with db.connect() as con:
            con.execute("UPDATE sender_directory SET lookup_version=0")
        self.assertIsNone(cached_contact("123", now=now))

    def test_verified_directory_enriches_old_messages_without_rewriting_them(self):
        from main import save_message, MessageIn, list_messages

        mid, _ = save_message(
            MessageIn(
                text="فروش پنل",
                sender_id="123",
                sender_link="https://ble.ir/wrong",
                sender_username="wrong",
            )
        )
        save_contact(Contact("123", "Sample", "member"))
        result = list_messages(limit=10, user={"role": "viewer"})
        self.assertEqual(result[0]["sender_link"], "https://ble.ir/member")
        self.assertTrue(result[0]["sender_clickable"])
        with db.connect() as con:
            self.assertEqual(
                con.execute(
                    "SELECT sender_username FROM messages WHERE id=?", (mid,)
                ).fetchone()[0],
                "wrong",
            )

    def test_expired_positive_link_is_not_displayed(self):
        save_contact(
            Contact("123", "Sample", "member"),
            now=datetime.now(timezone.utc) - timedelta(days=8),
        )
        rows = [{"sender_id": "123"}]
        enrich_messages(rows)
        self.assertIsNone(rows[0]["sender_link"])

    def test_failed_results_retry_after_fifteen_minutes(self):
        now = datetime.now(timezone.utc)
        save_contact(Contact("123", error="TimeoutError"), now=now)
        self.assertIsNotNone(cached_contact("123", now=now + timedelta(minutes=5)))
        self.assertIsNone(cached_contact("123", now=now + timedelta(minutes=16)))

    def test_cached_contact_is_searchable_on_historical_messages(self):
        from main import save_message, MessageIn, list_messages

        save_message(MessageIn(text="فروش پنل", sender_id="123"))
        save_contact(Contact("123", "Sample", "member"))
        self.assertEqual(
            len(list_messages(sender_id="@member", limit=10, user={"role": "viewer"})),
            1,
        )
        self.assertEqual(
            len(list_messages(q="member", limit=10, user={"role": "viewer"})), 1
        )

    def test_old_and_expired_username_filters_cannot_match_current_identity(self):
        from main import save_message, MessageIn, list_messages

        save_message(
            MessageIn(text="Demo", sender_id="123", sender_username="old_member")
        )
        save_contact(Contact("123", "Sample", "new_member"))
        self.assertEqual(
            list_messages(sender_id="@old_member", limit=10, user={"role": "viewer"}),
            [],
        )
        save_contact(
            Contact("123", "Sample", "new_member"),
            now=datetime.now(timezone.utc) - timedelta(days=8),
        )
        self.assertEqual(
            list_messages(sender_id="@new_member", limit=10, user={"role": "viewer"}),
            [],
        )

    def test_contact_overlay_handles_more_than_one_query_batch(self):
        rows = [{"sender_id": str(i)} for i in range(601)]
        save_contact(Contact("600", "Sample", "member"))
        enrich_messages(rows)
        self.assertEqual(rows[-1]["sender_link"], "https://ble.ir/member")
        self.assertIsNone(rows[0]["sender_link"])

    def test_no_verified_contact_means_no_guessed_numeric_or_legacy_link(self):
        rows = [
            {
                "sender_id": "123",
                "sender_username": "unverified",
                "sender_link": "https://ble.ir/unverified",
            }
        ]
        enrich_messages(rows)
        self.assertFalse(rows[0]["sender_clickable"])
        self.assertIsNone(rows[0]["sender_link"])


if __name__ == "__main__":
    unittest.main()
