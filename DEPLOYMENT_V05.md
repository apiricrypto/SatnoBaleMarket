# SATNO Bale Market Intelligence v0.5 — Windows Production

## Current production

- Server: `192.168.1.192`
- Path: `C:\Satno\SatnoBaleMarket-v05`
- Port: `8000`
- Web task: `SATNO-BaleMarket-v05-Web`
- Sync task: `SATNO-BaleMarket-v05-Sync`

This document applies only to SATNO Bale Market. Do not stop, reconfigure or restart Farsicom, VoIP, DNS or unrelated services.

## Alpha 2.2 readiness install

CRM Alpha 2.1 must remain disconnected. Before installation, `SATNO_CRM_LEAD_URL` must be empty.

Run PowerShell as Administrator:

```powershell
cd C:\Satno\SatnoBaleMarket-v05
.\scripts\install-alpha22-readiness-windows.ps1
```

The installer:
1. requires a clean Git working tree;
2. refuses to proceed if a live CRM URL is configured;
3. records the current Git HEAD;
4. takes a SQLite online backup;
5. privately backs up `.env.local`;
6. fast-forwards `feature/staff-v05`;
7. installs declared Python dependencies;
8. runs the additive SQLite schema initializer;
9. runs compile/unit/regression/secret/branch validation;
10. runs the loopback mock CRM adapter acceptance;
11. restarts only the two Bale Market scheduled tasks;
12. verifies `http://127.0.0.1:8000/health`.

The script prints a backup directory similar to:

```
C:\Satno\backup\bale-market-alpha22-YYYYMMDD-HHMMSS
```

Keep that path until the package is accepted.

## Post-install checks

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Get-ScheduledTaskInfo -TaskName "SATNO-BaleMarket-v05-Web"
Get-ScheduledTaskInfo -TaskName "SATNO-BaleMarket-v05-Sync"
```

Open:
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/review`
- `http://127.0.0.1:8000/sources/manage`
- `http://127.0.0.1:8000/crm/outbox`
- `http://127.0.0.1:8000/status`

Expected CRM readiness during Alpha 2.1:
- URL configured: no
- token configured: no, unless a server-only token has been staged intentionally
- live delivery: disabled
- existing outbox rows preserved

## Mock CRM acceptance

Run independently at any time:

```powershell
.\scripts\test-crm-adapter-windows.ps1
```

This starts only a loopback receiver on port 8099 with a synthetic in-process token and a temporary SQLite database. It does not contact SATNO CRM.

Expected output includes:
- valid first receipt;
- duplicate retry with same CRM Lead identity;
- no secret or raw payload printed.

## Rollback

Use the backup path printed by the installer:

```powershell
.\scripts\rollback-alpha22-readiness-windows.ps1 -BackupPath "C:\Satno\backup\bale-market-alpha22-YYYYMMDD-HHMMSS"
```

Rollback:
- stops only Bale Market scheduled tasks;
- checks out the recorded previous code HEAD;
- restores the previous SQLite database;
- restores the private `.env.local`;
- restarts Bale Market Web;
- verifies health.

It does not touch CRM, Farsicom, VoIP or other services.

## CRM Alpha 2.2 activation

Do not configure live delivery until the CRM team explicitly provides:
- deployed HTTPS `ingest_leads` endpoint;
- dedicated `SATNO_BALE_MARKET_INGEST_TOKEN` of at least 32 characters;
- disposable acceptance window.

Then set only on the server:

```
SATNO_CRM_LEAD_URL=https://<approved-host>/functions/v1/ingest_leads
SATNO_BALE_MARKET_INGEST_TOKEN=<server-only secret>
SATNO_CRM_MAX_ATTEMPTS=3
```

Never place the token in Git, browser configuration, screenshots, logs or chat.

The first live Alpha 2.2 acceptance must prove that ingestion creates only a quarantined Lead Inbox record and does not automatically create Company, Contact, Deal, Project, finance, procurement or inventory records.
