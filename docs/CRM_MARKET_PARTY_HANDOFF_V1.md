# SATNO Bale Market → CRM: reviewed market party v1

**Status: sender-side implemented; proposed receiver contract, not a live integration.** User-approved scope is the Bale Market producer/review/outbox. This document and its synthetic JSON are the handoff for the CRM Codex agent. No message, credential, company, contact or lead has been sent to a production CRM by this work.

## Business meaning

An ad is evidence of an advertised identity and commercial intent; it is neither proof of legal registration nor proof that every number belongs to that party. A publisher can be a group administrator. Keep these objects separate:

- Ad/source observation: one immutable source identity, raw text, group/channel, time and locally reviewable message ID.
- Party claim: company/business, person or unknown; declared name without transliteration/legal-name guessing.
- Roles: supplier prospect, buyer/customer prospect, or both. Roles are not mutually exclusive and are not qualification/approval levels.
- Primary contact: editable phone, email or explicit URL, with a separate relationship-verification state. Other contacts remain unverified observations.
- Human review/selection: a staff decision about the record, distinct from contact verification.

## Operator workflow implemented in Bale Market

1. Market shows conservative name/role suggestions. Names may use the explicit Persian company marker `شرکت`, or a short Persian business signature immediately before an address/contact block or near the end after contact details. Implicit signatures require business-name cues; product headings, slogans and addresses are excluded. Explicit company names take precedence, and ambiguous signatures remain for manual entry. Roles suggested from existing message category are editable, never authoritative.
2. Review shows labelled fields: declared name (200 chars), company/person/unknown, supplier/buyer/both, optional company representative name, primary contact, unverified/confirmed relationship and an evidence note (1000 chars).
3. Selection for queue requires a nonempty declared name, a known party type and at least one role. Draft/rejected reviews may remain incomplete. Names of people/representatives are entered by the reviewer, never copied from the publisher.
4. Contact confirmation requires the named party, a usable primary contact (not a group invite), and an evidence note. The server records `contact_verified_by`, `contact_verified_at`, and the exact `verified_contact`. The client cannot supply audit metadata. Confirmation applies to the primary contact only; it is not legal-company verification or validation of all advertised contacts. A primary contact edit without renewed explicit confirmation invalidates its old confirmation. Notes-only edits preserve the original verifier.
5. Queueing snapshots the reviewed record with all contacts and source provenance. Duplicate queue requests retain the same local outbox ID; an unsent snapshot is refreshed only on an explicit requeue. Sent snapshots are immutable. Rejection prevents requeue/send.
6. Outbox shows the saved party and intended intake, not a newly recomputed identity from an edited message. Staff can download the exact payload using **دریافت بستهٔ CRM**; viewer/no-session access is forbidden.

## Transport and payload

The existing envelope remains the `ingest_leads`-compatible shape: required `source_record_id`, `title`, `captured_at`, `raw_payload`, with existing optional `organization_name`, `contact_name`, `contact_phone`, `contact_email`, description, etc. **No unknown top-level field is added.** This does not mean the existing Lead receiver implements supplier intake.

Producer sample: [`crm-handoff/supplier-example.json`](crm-handoff/supplier-example.json). Every identifier, contact and company in that sample is synthetic. The actual producer `crm_connector.build_lead_payload` generated it, rather than a separate hand-written schema example.

New object: `raw_payload.business_context`:

| Field | Meaning |
|---|---|
| `schema` | Exact version identifier `satno.market-party.v1` |
| `intended_intake` | `supplier_intake`, `sales_lead_intake`, `dual_role_intake`; `needs_review` for incomplete drafts, which the UI cannot queue |
| `requested_action` | `resolve_or_create_after_review`; a routing request, not evidence that an entity already exists |
| `delivery_state` | `crm_contract_pending` in this producer release |
| `party.entity_type` | `company` or `person` for a selected record |
| `party.declared_name` | Reviewer-selected advertised name, not a verified legal name |
| `party.roles` | Canonical ordered subset of `['supplier','buyer']` |
| `party.contact_person` | Explicit reviewer-entered representative of a company; empty for individual parties |
| `party.name_origin`, `name_evidence` | `message_text` with the detected company-marker excerpt if unchanged; otherwise `reviewer_input` and no invented source excerpt |
| `party.contact_verification` | `unverified` or `confirmed`; applies only to `verified_contact` |
| `party.verification_note` | Reviewer evidence/notes; required for confirmation |
| `party.contact_verified_by`, `contact_verified_at`, `verified_contact` | Server-generated current confirmation audit, otherwise null |
| `source` | Local message ID, external ad ID, source name, sent time and publisher role |
| `review` | Selection, reviewing account/time, primary contact and verification scope/audit |

`raw_payload.extracted.ad_contacts` retains **all** message-derived contacts with `origin: message_text` and `ownership_verified: false`, even if the primary contact was confirmed. `raw_payload.review.ad_contacts` holds parsed reviewer contact data with `origin: reviewer_input`; confirmation is carried separately in business context. This avoids accidentally confirming every number/link in a multi-party ad.

Top-level mapping: a company maps to `organization_name`, and only an explicitly entered company representative maps to `contact_name`. A person maps to `contact_name` without inventing a company. Existing typed phone/email rules remain. URLs are never put in `contact_phone`. Raw message text and publisher are preserved separately. No public Bale ad URL is guessed from a numeric identifier; use stored source IDs and the Bale Market review screen.

## Required work on the CRM side — not implemented here

1. Inspect the actual CRM company/contact models and existing lead-intake contract before changing them. Agree the endpoint and receiver capability for this schema; do not blindly point it at the legacy sales-lead handler.
2. Authenticate a server-only connector credential (`x-satno-connector: bale_market` and Bearer header in the existing adapter). Validate schema, size limits, role enum, reviewer selection, source identity and contact types. Never treat sender-supplied UI labels as database IDs.
3. Route supplier intake to a supplier-prospect resolution workflow, buyer intake to a sales-lead/customer-prospect workflow, and dual-role intake to one party with both roles. A supplier advertisement alone must not create a sales opportunity. A buyer request alone is not a qualified deal.
4. Before creation, find possible existing parties using normalized names, domain and contact evidence. Shared admin phones, reused domains or merely similar Persian/Latin names are not automatic merge proof. Present ambiguous matches for a person to resolve. Preserve the source observation and decision trail whichever entity is chosen.
5. Resolve to an existing Company/Contact or create a prospect after the agreed review step. Do not create a named Contact just because an unnamed phone exists. Keep original labels alongside normalized fields. Do not overwrite trusted existing CRM facts with weaker scraped claims.
6. Keep company/entity dedup separate from message idempotency: repeated delivery of one `source_record_id` creates no extra intake; ads across several sources may be separate observations of the same resolved party. Keep every source reference.
7. Render clickable source and reviewed phone/Bale/WhatsApp/email/site details, clearly separating publisher, extracted claims and primary-contact confirmation. Display verification evidence and timestamps to authorized staff.
8. Agree receipts and failure behavior. The existing sender expects HTTP 200/201 plus `data.id`, `data.source: bale_market`, matching `source_record_id`, `status`, `created_at`, boolean `duplicate`, and `request_id`. Clarify whether `data.id` is an intake-record ID (recommended); it must not ambiguously mean Company ID for one route and sales Lead ID for another. If additional resolved entity IDs or receipt types are required, version and test both sides before activation.
9. Validate with isolated fixtures: supplier, buyer, dual role, individual supplier, anonymous publisher, shared phone, ambiguous company matches, repeated message delivery and multiple source ads. No production business records or live messaging during initial acceptance.

## Delivery gate and compatibility

New business packets are durably queued, but `send_outbox_item` returns `status: blocked`, `reason: business_contract_pending` **without network calls or consuming retry attempts**. This also guards an older queued packet when its current review was upgraded to a business profile. The outbox disables its send button accordingly. No environment variable silently enables this new contract in this release. After the receiving implementation and acceptance, a separate reviewed sender change must deliberately enable the agreed route/capability.

Legacy records without a business profile keep their existing adapter behavior. Existing queued payloads are never silently rewritten. Existing API clients that omit/null the business profile preserve a saved profile; they cannot downgrade its confirmation by attaching it to a new contact. The additive `lead_reviews.business_profile TEXT` migration is idempotent, leaves all existing rows intact and runs through existing database initialization. No Sync schedule, collector, source registry or CRM credentials change.

## Installation / rollback boundary

Current user-confirmed production baseline: `fd36c9e`. Before a separately authorized upgrade, back up the production SQLite database with its online backup API and save the current commit/configuration. Only the web task needs restart. This release adds one nullable review column; it does not require rewriting old ads or outbox rows. Previous application code tolerates the additional nullable column, so code rollback preserves operational data; do not restore an old database over a running Sync. Production migration and Windows execution have not been performed in the cloud environment.

## Acceptance evidence — 2026-10-17

- Full `python -m unittest discover -s tests -v`: **171 passed**, no failed tests.
- Added 19 business review tests covering conservative name suggestions, roles/types, server validation and forged-audit rejection, original verification attribution, changed-contact invalidation, schema idempotency/data preservation, typed payload routes, contract send gate, old packet/current-review gating, handoff authorization, reviewed-name search and immutable sent snapshots.
- Chromium acceptance: Login, Market, Sources, Review, Status, Users, Outbox, Password at **375 / 768 / 1440**; no page/console errors or horizontal page overflow. Verified profile prefills, role-specific queue actions, required confirmation evidence, safely escaped input, reviewer audit rendering, queue snapshot/JSON download and blocked contract delivery. Existing login/password/admin reset/RBAC/source bulk-delete flows passed.
- Independent code review found no remaining important/blocking issue. Its old-queue indicator discrepancy was corrected and regression-tested.
- Screenshots contain only synthetic data under `docs/contact-evidence/business-review/`.
- JavaScript syntax and `git diff --check` passed. Existing FastAPI `on_event` deprecation remains; no unrelated framework migration was included.
- No Windows Server deployment, production migration or real CRM entity creation performed in this environment. The receiver contract is proposed for the next CRM session, not claimed implemented by that separate project.


## Signature extraction correction — after `6cb8cd6`

Contact-footer business names no longer need the word `شرکت`. The candidate carries the original signature line as `name_evidence`; it remains an advertised claim and does not confirm ownership or legal identity. Unsupported forms still require human entry. Do not treat this rule-based parser as a universal company recognizer.

Landline contacts accept explicit telephone symbols (📞 / ☎ / 📠) as contact context in addition to text labels. Bare unlabelled numeric product IDs remain excluded. A hyphenated/unlabelled handle is not repaired or guessed into a Bale profile link.

Existing saved party names are preserved. An empty saved draft with a newly recognized suggestion offers **استفاده از نام پیشنهادی**; adoption is explicit and is persisted only on review/queue save. No saved verification is automatically inherited. Existing unsent outbox payloads still require explicit re-review/requeue to update.

This correction adds no dependency, database migration, Sync/source change or delivery-gate change. Unit regression total is **180 passed**, including nine signature tests and all previous business/contact/auth/Sync tests. The operator's two excerpts were checked locally without saving their contact data in the repository; committed fixtures and screenshots use synthetic details only. Browser acceptance includes signature suggestion adoption for an empty saved draft, both landline and mobile, queue persistence, mobile/desktop layout and the existing eight-page suite. Production remains at the user-confirmed `6cb8cd6` until a separately authorized code upgrade.
