# Contacts: market → review → CRM outbox

This release extends the deployed `7758b7a` ad contact display. No database migration, new dependency, source/schedule change or production configuration change is needed.

## Operator workflow

1. Search the market and open **بررسی و آماده‌سازی CRM** on the relevant message.
2. Inspect the publisher profile separately from contact details inside the ad. The publisher may be an administrator and is never automatically treated as the contact owner.
3. Review the editable **تماس اصلی CRM** field. Its suggestions come from the ad; a telephone, email or explicit platform URL can be entered. All detected contacts remain alongside the primary contact. Save/queueing records the reviewing staff member.
4. Choose **قرار دادن در صف CRM**. This saves a selected review and a durable payload, without sending a request to CRM. Requeueing an unsent item refreshes its snapshot in the same row; sent rows remain immutable. A rejected/unselected review cannot be requeued or sent from an older queue item.
5. Inspect `/crm/outbox`: contact details come from the queued message snapshot, with the reviewed primary contact shown separately. A message link returns to review. Viewing the queue never sends anything.

## Existing CRM contract preserved

- `contact_phone`: a recognized phone from the reviewed contact, or from the original ad if no override was entered. A reviewed URL/email is never put into this field. Stale classifier-only phone values are not promoted.
- `contact_email`: a recognized reviewed email, otherwise an email explicitly in the ad.
- `contact_name`: no longer guessed from the publisher's display name.
- `raw_payload.message.sender_contact_role`: `publisher`; original source fields remain available.
- `raw_payload.extracted.ad_contacts`: every detected contact, including Bale, WhatsApp, websites, review-needed links and unlabelled handles, with provenance and `ownership_verified: false`.
- `raw_payload.review.contact` and `.ad_contacts`: the human-entered primary contact and its parsed details (`origin: reviewer_input`), with the existing reviewer/time audit fields.

No new top-level CRM fields are introduced. Stable source identity, receipts, bounded retry and idempotency remain intact. The receiving CRM may need its own UI to render links inside `raw_payload`; this repository does not change that external application.

## Verification and production boundary

Run `python -m unittest discover -s tests -v` and `python tools/verify_ui.py --artifacts /tmp/contact-crm-ui`. Tests use disposable databases and synthetic contacts. A real loopback HTTP receiver verifies phone, email, all link kinds, publisher separation and a valid stored receipt. Browser acceptance exercises review/queue contacts at 375/768/1440, repeated queueing, role checks, HTML escaping and disabled live delivery.

Production endpoint/token configuration and real CRM ingest have **not** been tested or enabled. Do not put credentials in chat. Enabling the real connection requires explicit authorization, the verified endpoint/contract, server-only credentials and a designated test lead. Previously queued payloads are not automatically rewritten; re-review and explicitly requeue unsent rows to adopt the new contact mapping. Installing application code is separate from enabling delivery.

## Upgrade checklist

Back up the production database using the SQLite backup API and save the current commit, launcher/config and web task export. Start from the user-confirmed `7758b7a`, fetch and pin the reviewed release commit, check for tracked local changes/untracked collisions and verify no Sync/source/dependency/schema files changed. Stop only the existing web task and ensure its listener has exited before switching code; restart through its existing launcher. Verify health/login, shared JS asset and market → review → queue with a designated lead. Keep CRM endpoint/token unchanged. On readiness failure stop only web and return to the recorded commit; never restore an older database over running Sync. The production rollout is performed by the server operator after its short web interruption is authorized.

## Acceptance result — 2026-10-17

- Full unittest discovery: **152 passed**; no failed tests.
- Chromium: eight pages at **375 / 768 / 1440**; no page/console errors or horizontal page overflow. Market → review → queue, snapshot links, editable primary contact, duplicate queueing and disabled live send verified.
- Existing login/logout, password change, administrator reset, role navigation and bulk source deletion acceptance passed.
- Real loopback HTTP contact delivery and valid CRM receipt passed. This is not a production CRM receipt.
- `git diff --check`, shared JavaScript syntax check and dependency consistency check passed. Existing FastAPI startup deprecation warning remains a maintenance item.
- Independent review completed; reviewer-contact provenance finding corrected and regression-tested.
- Synthetic screenshots: `docs/contact-evidence/crm-flow/`.
