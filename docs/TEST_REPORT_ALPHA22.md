# SATNO Bale Market — Alpha 2.2 Readiness Test Report

Date: 2026-10-06

## Objective

Validate SATNO Bale Market as an independent operational product and prepare its sender adapter for future SATNO CRM Alpha 2.2 ingestion without making a live CRM connection.

## Contract evidence

Implementation was based on the actual CRM repository package:
- repository: `apiricrypto/atomic-crm`;
- branch: `satno/lead-ingestion-contract-20260928`;
- acceptance: `docs/satno/LEAD_INGESTION_ACCEPTANCE.md`;
- validator: `supabase/functions/ingest_leads/contract.ts`;
- handler/receipt contract: `supabase/functions/ingest_leads/handler.ts`;
- authentication: `supabase/functions/ingest_leads/authentication.ts`.

The sender does not use the former `satno.lead.v1` top-level body.

## Automated evidence

GitHub Actions workflow: `v0.5 Staff CI`

Validated code baseline:
- commit `caebc2017fc4ab0bc6cb547a292c5dda3c9ef859`;
- Python 3.12 job: success;
- Python 3.13 job: success;
- compile: success;
- full unittest discovery: success on both jobs.

The suite includes the real in-process mock `ingest_leads` HTTP receiver and therefore exercises actual HTTP request/receipt handling without a real CRM.

## Tested behaviors

### Market intelligence
- existing supplier/seller, stock/availability, buyer demand and inquiry/project classification remains compatible;
- currency-unit extraction added alongside existing product/brand/model/power/capacity/price/location/contact extraction;
- search includes currency-unit text.

### Human review
- review state is persisted with reviewer and timestamp;
- category/product/brand/model/power/capacity/price/currency/location/contact/priority/notes are editable;
- CRM normalized estimate requires amount + ISO currency as a pair;
- a new outbox item cannot be created until the message is marked `selected`.

### Manual Bale sources
- add by peer type/id;
- duplicate source rejection;
- edit title/score/matched terms/enabled state;
- delete source;
- source deletion clears only its sync/backfill state and does not erase message history.

### CRM sender contract
- only CRM-approved top-level fields are emitted;
- stable string `source_record_id`;
- timezone-aware `captured_at`;
- `raw_payload` object preserved for quarantine;
- legacy `contract_version`, top-level `source` and `idempotency_key` are absent;
- dedicated `x-satno-connector: bale_market` header;
- dedicated Bearer token;
- sender-side request/raw-payload/amount/currency/priority validation;
- existing outbox row is preserved when a legacy queued item is refreshed;
- local queue is idempotent by source record.

### Receipt and retry
- HTTP 201 + valid receipt marks sent;
- HTTP 200 alone does not mark success;
- source mismatch is rejected;
- source_record_id mismatch is rejected;
- CRM Lead ID and request ID are persisted;
- duplicate flag is persisted;
- retry attempts are bounded;
- transient failures become retry/dead according to attempt limit;
- auth/validation HTTP failures are not retried indefinitely.

### Mock receiver
The committed test receiver:
- requires `x-satno-connector: bale_market`;
- requires Bearer auth;
- returns 201 for first event;
- returns 200 + duplicate=true for repeat event;
- returns the same CRM Lead identity for the duplicate;
- logs neither token nor payload content.

## Secret handling

Verified design:
- real Bale token stays server-side;
- future CRM token stays server-side;
- readiness API exposes only configured/not-configured booleans;
- outbox API omits request payload and receipt body;
- `.env.local` and SQLite runtime DB remain Git-blocked;
- example JSON contains synthetic data only.

## Existing queue

Schema migration is additive. It does not recreate `crm_lead_outbox`.

The previously observed queued `outbox_id=4` is therefore preserved by installation. A legacy queued payload is updated only when that message is explicitly re-queued after review.

## Not claimed / intentionally not tested

- No request was sent to SATNO CRM Alpha 2.1.
- No production CRM token was created, read or stored.
- No real `ingest_leads` deployment was contacted.
- No CRM Company, Contact, Deal or Project creation was tested from Bale Market because the ingestion boundary is quarantine-only.
- No CRM Alpha 2.2 production activation is claimed.

## Windows package

Prepared:
- `scripts/install-alpha22-readiness-windows.ps1`;
- `scripts/rollback-alpha22-readiness-windows.ps1`;
- `scripts/test-crm-adapter-windows.ps1`.

The production installer is guarded to refuse a configured live CRM URL during Alpha 2.1 and restarts only Bale Market scheduled tasks.

## Result

**Code/contract readiness: PASS**

**Mock receiver integration: PASS in automated unittest suite**

**Live CRM integration: NOT ENABLED by design**

Final production acceptance requires running the guarded Windows installer on `192.168.1.192` and then the local health/UI checks. That action changes only SATNO Bale Market and is reversible with the generated backup path.
