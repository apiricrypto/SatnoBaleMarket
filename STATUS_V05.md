# SATNO Bale Market Intelligence v0.5 — Operational Status

Status: **Production operational**
Branch: `feature/staff-v05`
Validated HEAD: `34d54b4dae1af644d38e5653bc2fc4e3a48142cd`

## Production state

- Production path: `C:\Satno\SatnoBaleMarket-v05`
- Web service: Uvicorn / FastAPI on port 8000
- Login, Dashboard, Status and Admin Users pages verified
- Windows validation suite passed: 63 tests
- GitHub CI for the validated HEAD passed
- Scheduled Web and Sync tasks are configured
- Previous v0.4 installation and backup remain available for rollback

## Live Bale sync

Live sync is operational.

Most recent acceptance run:
- Messages read: 114
- Text messages: 62
- New saved: 62
- Duplicates: 0
- Source attempts: 53
- Source successes: 53
- Source failures: 0
- Discovery mode: dialogs
- Sync status: ok

A registry fallback also exists for the case where Bale returns zero dialogs while active sources are known.

## Staff security

- Passwords are PBKDF2-SHA256 hashes only
- Session tokens are stored only as SHA-256 hashes
- Roles: admin / sales / viewer
- Dashboard and data APIs require authentication
- User management is admin-only
- Last active admin cannot be disabled or demoted
- `.env.local`, Bale token, CRM token and SQLite runtime databases are not intended for Git tracking

## CRM

Lead export uses contract `satno.lead.v1` and an idempotent outbox.
If the actual SATNO CRM endpoint is not configured, Leads remain safely queued.

## Operating rule

Hourly development automation is disabled. From this point, changes should be maintenance or approved feature work only, with validation before production changes.
