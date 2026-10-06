# SATNO Bale Market Intelligence v0.5 — Operational Status

Status: **Production operational; CRM Alpha 2.2 sender package ready for guarded install**

Branch: `feature/staff-v05`

## Production state

- Windows Server: `192.168.1.192`
- Production path: `C:\Satno\SatnoBaleMarket-v05`
- Web service: Uvicorn / FastAPI on port 8000
- Login, Dashboard, Status and Admin Users are operational
- Scheduled Web and Sync tasks are configured
- Live Bale sync is operational
- Previous v0.4 installation/backups remain available for rollback
- Hourly development automation remains disabled

## Live Bale sync

Last operator acceptance before the Alpha 2.2 readiness package:
- Messages read: 114
- Text messages: 62
- New saved: 62
- Duplicates: 0
- Source attempts: 53
- Source successes: 53
- Source failures: 0
- Discovery mode: dialogs
- Sync status: ok

A source-registry fallback is also available when Bale returns zero dialogs.

## Market intelligence

The system separates:
- supplier / seller;
- stock / availability / sale;
- buyer demand;
- inquiry / project;
- other.

Reviewable extraction includes:
- product type;
- brand;
- model;
- power;
- capacity;
- price text;
- detected currency unit;
- location;
- contact.

Search, filters, sender provenance and message provenance are retained.

## Human lead review

New operational workflow:
1. message is collected and classified;
2. extracted fields remain editable/reviewable;
3. staff records review status and notes;
4. only a `selected` record can enter the local CRM outbox;
5. queueing alone never creates CRM Company, Contact, Deal or Project rows.

Pages:
- `/review`
- `/crm/outbox`

## Bale source management

Administrators can manually:
- add a source;
- edit title/score/matched terms;
- enable or disable;
- delete a source.

Page: `/sources/manage`

Deleting a source does not erase historical collected messages.

## CRM Alpha 2.2 sender preparation

The old `satno.lead.v1` body is superseded.

The adapter now follows the CRM `ingest_leads` acceptance contract:
- `POST application/json`;
- `x-satno-connector: bale_market`;
- dedicated server-only Bearer token;
- stable string `source_record_id`;
- `title`;
- timezone-aware `captured_at`;
- quarantined `raw_payload`;
- only contract-approved optional normalized fields.

The local outbox is migrated in place. Existing queued rows are preserved.
Legacy unsent payloads are refreshed only when explicitly re-queued.

Delivery success requires a validated CRM receipt containing:
- CRM Lead ID;
- source = `bale_market`;
- matching source_record_id;
- CRM status;
- created_at;
- duplicate flag;
- request_id.

HTTP 200/201 without a valid receipt is not considered success.

Retry is bounded and connection/error state is visible in `/crm/outbox`.

## Current CRM gate

Live CRM delivery is intentionally **disabled** for CRM Alpha 2.1.

Keep:
- `SATNO_CRM_LEAD_URL=`
- `SATNO_BALE_MARKET_INGEST_TOKEN` server-only and unset until the approved Alpha 2.2 acceptance window.

The Alpha 2.2 package does not deploy or modify SATNO CRM.

## Package documents

- `docs/CRM_ALPHA22_READINESS.md`
- `docs/TEST_REPORT_ALPHA22.md`
- `docs/sample-bale-lead-alpha22.json`
- `scripts/install-alpha22-readiness-windows.ps1`
- `scripts/rollback-alpha22-readiness-windows.ps1`
- `scripts/test-crm-adapter-windows.ps1`

## Service isolation

The install/rollback package is scoped to SATNO Bale Market only.
Farsicom, VoIP, DNS and unrelated services are outside its actions.
