# Username-led Bale source enrollment and direct registry-only Sync

## Design decisions
- Staff can enter a public username such as `@partonorpars` or exact `https://ble.ir/partonorpars` URL.
- The new `source_username_queue` persists pending entries with distinct status. Pending is **not** an enabled source.
- Verify action uses current Bale account `resolve` and `get_full` with bounded timeouts, then requires the **exact same username**. No heuristic candidate, previous `query_text`, or guessed Peer ID is accepted.
- Verified Peer is added to `source_registry`, unless it is already present. Active Sync scans only registry sources with `enabled=1`.
- `Sync` no longer iterates the full dialog list or imports keyword-matched unrelated groups.
- Per-chat message retrieval is bounded by `BALE_CHAT_TIMEOUT_SECONDS` (default 25). Outcomes report degraded when some/all peers fail. No new messages are falsely claimed on failures.

## Key limitation / blocker
`bale-sdk==0.1.1` currently returns `LookupError` for `partonorpars` and transport warnings like `unexpected server hello` on the production host. This change provides safe pending storage and bounded direct polling for **already verified numeric peers**, but it cannot manufacture a verified numeric Peer from an unresolved username. Need additional independent protocol/source verification before this one channel can join active scanning.

## Release safeguards
- This is an experimental branch. **Do not** enable production Sync yet; first verify direct fetch on the isolated test environment and inspect the last `sync_runs` status.
- Use dedicated local `DATABASE_PATH` and empty/isolated Bale credentials for UI tests. A real Bale account is necessary for live end-to-end identity verification.
- `Sync` stays disabled in Windows Task Scheduler unless the human explicitly enables it after successful live acceptance.
- Historical messages, CRM outbox and non-Bale server services must remain untouched.
- Do not use old numeric Peer field for `@username`; use the new dedicated username form. Existing numeric Peer UI remains advanced for confirmed IDs.
- Future interval selection should be done in the scheduler, not by broad automatic re-discovery; deploy only after the live Sync health is fixed and user chooses a cadence.
