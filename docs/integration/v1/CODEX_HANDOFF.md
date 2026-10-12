# Bale Market → CRM Integration v1 — Codex handoff

Status: implementation task; documentation only. CRM_INTEGRATION_ENABLED=false must remain the default. No production send or deployment is authorized by this handoff.

README on main currently describes Flat MVP v0.2, FastAPI and a flat layout. Reconcile the working v0.5 installation with this repository before implementing. Read all applicable AGENTS.md; inspect the existing adapter, database and send code before choosing filenames. Do not modify source discovery/search behavior as part of this task.

## Required behavior

- Export only operator-approved supplier_offer or buyer_request records; A/B/C grade alone does not authorize export.
- Preserve peer_type/peer_id/message_id as strings in a stable composite source_record_id; retain provenance and original message identity.
- Use a durable transactional outbox and immutable snapshots: schema_version=1.0, event_id UUID, source_system=bale_market, source_revision positive integer, title, summary, provenance, score and approval. Unknown values remain null or empty arrays. Retain explicit IRR/IRT currency when supplied.
- Negotiate the actual receiver route with CRM before enabling integration. Proposed POST /api/integrations/v1/opportunities with source-scoped Bearer authentication and Idempotency-Key=event_id. Never put credentials in frontend, repository, logs or fixtures.
- CRM commits the Inbox and receipt atomically. Confirmed requires event_id, receipt_id, inbox_id and a known response status created/duplicate/updated. Duplicate returns the original inbox_id. A successful HTTP response without a valid receipt is not confirmed. Inbox receipt does not mean a Lead was created.
- Same event_id/different payload is 409; same revision/different payload is 409; older revision is stale and requires review. Retry retains event_id and payload. Higher revisions must not overwrite CRM user's follow-up fields.
- Outbox states awaiting_approval, queued, sending, retry_wait, confirmed, failed and stale; worker lease 120 seconds; request timeout 30 seconds. Maximum 8 transient attempts; delays 5/15/60/300/900/3600/21600 seconds plus up to 20% jitter. Retry network/timeout/429/5xx; honor Retry-After. Stop on 401/403; do not automatically retry other 4xx.
- flag=false results in zero write HTTP requests. Recover ambiguous sends by receipt lookup or idempotent replay. UI distinguishes queued, confirmed, duplicate and failure, and provides CRM Inbox link.

## Acceptance tests

1. Approved offer and request export independently; unapproved A-grade record does not export.
2. Concurrent/repeated send and timeout after server commit create one Inbox record.
3. Crash/restart recovers lease; immutable event/payload is preserved.
4. Disabled flag generates no write requests; 401/403/409/422 and malformed 2xx never confirm.
5. Older revisions cannot overwrite newer records; similar text across distinct messages is not automatically merged.
6. Secrets and cross-organization/source receipts remain inaccessible.
7. Validate against test CRM and show the record there, not only a local success notification.

## Codex execution instruction

First report actual source/version, file paths and receiver contract differences. Implement mapper, durable outbox, worker and status UI following current patterns, with meaningful failing tests before changes. Preserve current functionality and keep live sending disabled. Report commit, tests, unresolved discrepancies and flags. Wait for the receiver contract to be stabilized before end-to-end adapter enablement. No ZIP download is needed: this file is the repository handoff.
