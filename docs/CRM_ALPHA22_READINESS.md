# SATNO Bale Market — Alpha 2.2 CRM Connector Readiness

## Scope

This package keeps SATNO Bale Market operational as an independent product and prepares only the sender side of the future SATNO CRM Alpha 2.2 integration.

**No live CRM connection is enabled by this package.** Alpha 2.1 remains isolated from Bale Market.

Production environment currently expected:
- Windows Server: `192.168.1.192`
- Bale Market path: `C:\Satno\SatnoBaleMarket-v05`
- Dashboard: port `8000`
- Farsicom, VoIP and unrelated services are outside this package and must not be touched.

## CRM contract source

The sender adapter was derived from the CRM repository contract, not guessed:

- Repository: `apiricrypto/atomic-crm`
- Contract branch: `satno/lead-ingestion-contract-20260928`
- Acceptance document: `docs/satno/LEAD_INGESTION_ACCEPTANCE.md`
- Runtime validator: `supabase/functions/ingest_leads/contract.ts`
- Handler/receipt shape: `supabase/functions/ingest_leads/handler.ts`

Required sender behavior implemented here:
- POST JSON to the configured `ingest_leads` URL.
- Header: `x-satno-connector: bale_market`.
- Header: `Authorization: Bearer <dedicated server-only token>`.
- Required payload fields: `source_record_id`, `title`, `captured_at`, `raw_payload`.
- Only CRM-contract optional normalized fields are emitted.
- Unknown legacy top-level fields such as `contract_version`, `source`, `idempotency_key`, Deal IDs or assignment/status fields are not emitted.
- Sender validation mirrors the CRM size/date/amount/currency/priority limits.
- Local queue remains durable and idempotent.
- HTTP 200/201 alone is not success: the response must contain a valid receipt with CRM lead ID, source `bale_market`, matching `source_record_id`, status, creation timestamp, duplicate flag and request ID.
- Retry is bounded and exponential. Validation/authentication-type failures do not loop forever.
- No raw secret is returned by readiness/status APIs.

## Human review boundary

Automatic extraction remains reviewable and does not create CRM business records.

The review workflow supports:
- category: supplier/seller, stock/availability, buyer demand, inquiry/project;
- product;
- brand;
- model;
- power;
- capacity;
- price text and detected unit;
- explicitly reviewed CRM estimate amount + ISO currency;
- location;
- contact;
- priority;
- reviewer notes.

A new Lead can enter the local CRM outbox only after a staff member with Lead permission marks the message as `selected`.

This queue action does **not** create a Company, Contact, Deal or Project. The CRM ingestion contract places the item only in the quarantined Lead Inbox.

## Provenance

Each queued record carries:
- stable deterministic `source_record_id`;
- Bale chat/message identity retained in `raw_payload.message`;
- extracted fields retained in `raw_payload.extracted`;
- human review state retained in `raw_payload.review`;
- standardized `captured_at`.

Historical messages were stored before a full provider-object snapshot column existed. For those rows, `raw_payload` is reconstructed from the persisted Bale Market source fields and extraction state. It must not be described as a byte-for-byte original Bale provider object.

## Existing queue preservation

The existing `crm_lead_outbox` table is migrated in place. Existing rows, including queued legacy rows such as the previously observed `outbox_id=4`, are not deleted.

When a legacy queued item is explicitly re-queued after review, its existing row ID is preserved and its unsent payload is refreshed to the Alpha 2.2 sender contract. Sent rows are not overwritten.

## Source management

Administrators can now:
- add a Bale source manually by peer type/id;
- edit title, score, matched terms and enabled state;
- disable/enable a source;
- delete a source.

Deleting a source removes only its registry/checkpoint/backfill tracking state. It does not delete historical market messages already stored.

UI: `/sources/manage`

## Operational pages

- Dashboard: `/`
- Human review: `/review`
- Source management: `/sources/manage`
- CRM outbox/readiness: `/crm/outbox`
- Sync status: `/status`

## Secrets

Server-only:
- `SATNO_CRM_LEAD_URL`
- `SATNO_BALE_MARKET_INGEST_TOKEN`

For Alpha 2.1 / current production readiness, leave `SATNO_CRM_LEAD_URL` empty.

Do not use `VITE_` variables, browser storage, screenshots, Git, logs or request bodies for the token.

## Mock acceptance

Windows isolated acceptance:

```powershell
.\scripts\test-crm-adapter-windows.ps1
```

The test:
1. creates a random synthetic token in process memory;
2. starts a loopback-only mock `ingest_leads` receiver on port 8099;
3. creates a temporary SQLite database;
4. seeds a synthetic Bale message;
5. performs human-selection state;
6. queues and sends one event;
7. validates the receipt identity;
8. retries the same source event and proves duplicate response returns the same CRM lead identity;
9. prints no token or raw payload.

## Installation

Run as Administrator from the production checkout:

```powershell
.\scripts\install-alpha22-readiness-windows.ps1
```

The installer:
- refuses a dirty Git tree;
- refuses installation if a live CRM URL is already configured;
- takes a SQLite backup and private env backup;
- records the previous Git HEAD;
- fast-forwards only the Bale Market branch;
- runs schema migration;
- runs the full regression suite;
- runs the isolated mock CRM acceptance;
- restarts only SATNO Bale Market scheduled tasks;
- verifies port 8000 health.

It does not modify Farsicom, VoIP, DNS, CRM, or unrelated Windows services.

## Rollback

The installer prints the backup path. To rollback:

```powershell
.\scripts\rollback-alpha22-readiness-windows.ps1 -BackupPath "C:\Satno\backup\bale-market-alpha22-YYYYMMDD-HHMMSS"
```

Rollback restores:
- previous Git HEAD;
- previous SQLite database;
- previous `.env.local`;
- Bale Market Web task.

It does not change other server services.

## Alpha 2.2 activation gate

Do not enable live delivery until CRM Alpha 2.2 provides and accepts:
1. deployed HTTPS `ingest_leads` endpoint;
2. dedicated random Bale token, at least 32 characters;
3. disposable end-to-end acceptance;
4. source-token isolation test;
5. first create returns 201 with valid receipt;
6. duplicate returns 200 with same CRM lead identity;
7. no Company/Contact/Deal/Project/finance/inventory side effect;
8. agreed rate/retention/audit ownership.

Only then set the two server-side connector values and explicitly enable outbox processing.
