# Group sender contact lookup — development release

This change is not installed on the Windows production server. Production was last confirmed at `a2aeb02`.

## What was observed

The real production database contains messages from `PVsolar(Group)` with sender IDs but no stored usernames or links. Three live full-profile samples returned no username; they were not identified as the person shown in the user's screenshot. This does not prove that those users have no username. The screenshot independently shows one public username, but the mapping between that profile and a stored sender ID is not yet verified.

The old application passed a numeric sender ID as a string to `get_entity`. In installed bale-sdk 0.1.1 this searches a username, rather than requesting that user by ID. The SDK's `LoadUsers` cache also drops the `nick` field even though the raw response can carry it.

## Implemented behavior

- Request the exact user via typed `LoadUsersRequest`; inspect the raw `nick` only on a matching user ID. If missing, request the raw full-user response through the user-only RPC with the returned access hash and require an explicit matching ID (the SDK normalizer may substitute a missing ID).
- No fuzzy username search, fabricated numeric deep links, messages, contact additions or group membership changes.
- Public usernames are restricted to ASCII letters/digits/underscore before constructing `https://ble.ir/<username>`. The UI says “ارتباط با فرستنده در بله”; it promises a profile link, not automatic chat opening.
- Errors/unavailable usernames are distinguished from a verified public username. Raw RPC error text, tokens and message bodies are not logged by the probe.
- Cache versioning forces old ambiguous resolutions to be checked again. Positive TTL: 7 days; username unavailable: 6 hours; temporary error: 15 minutes. Expired links are not displayed.
- A single additive `sender_directory.lookup_version` column is initialized by the existing database setup. There is no message-table migration or rewrite.
- Historical messages receive a read-only cache overlay in the API, including username search. Original messages, IDs, text and source references remain in SQLite unchanged.
- Sync enrichment has an 8-second total limit per user and at most 10 lookups per run. Existing scheduling, checkpoints, registered sources, singleton lock, UTF-8 logging and CRM delivery controls are unchanged. Message collection continues when lookup fails.

## Read-only live verification before rollout

`backfill_senders.py` is now a bounded diagnostic by default. Explicit `--database` and exact `--group` are required, to avoid the inherited temporary `DATABASE_PATH` observed during manual diagnosis. It does not initialize the database in read-only mode. `--apply` explicitly migrates/updates the cache and must NOT be used on production until separately approved with a backup.

```powershell
# Once the diagnostic code is available in an isolated folder on the server:
# Use the server venv and the existing project configuration; never paste a token.
# Standard repository invocation in a development checkout:
.\.venv\Scripts\python.exe backfill_senders.py --database C:\Satno\SatnoBaleMarket-v05\satno_market.db --group 'PVsolar(Group)' --limit 3 --expected-username mousavi1385
```

Expected output: `MODE: READ_ONLY`, sample statuses and validated public links (when returned), then `NO_DATABASE_WRITES`. `MATCHES_EXPECTED: False` means only that the sampled sender differs from the expected username, not that lookup is wrong. The expected username is never assigned to a numeric sender ID merely because it was supplied on the CLI. A `LINK` must be opened by the operator and checked against the actual group sender before calling the real-world flow verified.

For server staging without checkout changes, fetch the approved commit and extract only `backfill_senders.py` and `sender_contacts.py` into a separate temporary folder. Launch via `runpy` with that folder prepended to `sys.path`, with the working directory kept at the production root so the existing `.env.local` can supply authentication. Do not replace the running source files, start a second Sync, change any task, or run `--apply` during this probe.

## Verification evidence

Local unit/regression suite: 120 tests passed. This includes typed raw/full responses, wrong/missing/zero ID rejection, malicious username rejection, negative/error/positive TTL, legacy cache rejection, historic API search/overlay, read-only probe file hash preservation, Sync collection and bounded enrichment.

Real Chromium acceptance: Login, Dashboard, Sources, Review, Status, Users, Outbox and Password at widths 375/768/1440; contact link rendering uses explicitly synthetic data in a temporary database. No live profile navigation or chat sending is part of automated acceptance. Desktop/mobile examples are in `docs/contact-evidence`.

Live username extraction on the Windows account is pending; the cloud machine has no Bale credentials. Do not claim the screenshot user's ID was resolved or that all real group senders can be contacted until live evidence exists.
