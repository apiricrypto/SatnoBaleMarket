# SATNO Bale Market Intelligence v0.5 Staff Edition

## Scope
This branch is for isolated validation of v0.5. Do not replace the production v0.4 service or merge into `feature/classifier-v03` without explicit approval.

## Windows Server isolated test

Production v0.4 is expected to remain on port 8000. Test v0.5 on port 8005.

```powershell
cd C:\Satno
git clone https://github.com/apiricrypto/SatnoBaleMarket.git SatnoBaleMarket-v05-test
cd C:\Satno\SatnoBaleMarket-v05-test
git checkout feature/staff-v05

py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Copy-Item .env.example .env.local
```

Edit only `.env.local` on the server. Never commit it.

For isolated testing, use a separate database path:
```
DATABASE_PATH=C:\Satno\data\satno_market_v05_test.db
SESSION_COOKIE_SECURE=0
```

Create the first admin interactively:
```powershell
.\.venv\Scripts\python.exe create_staff_user.py admin --role admin --name "SATNO Admin"
```

Run tests:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Start v0.5 on a separate port:
```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8005
```

Health check:
```powershell
Invoke-RestMethod http://127.0.0.1:8005/health
```

Open:
- http://127.0.0.1:8005/login
- http://127.0.0.1:8005/status

## Security requirements
- Passwords are stored only as PBKDF2-SHA256 hashes with unique salts.
- Browser session tokens are random; only SHA-256 token hashes are stored in SQLite.
- Session cookie is HttpOnly and SameSite=Strict.
- For HTTPS production set `SESSION_COOKIE_SECURE=1`.
- `BALE_TOKEN`, `SATNO_CRM_API_TOKEN`, `.env.local`, session files and SQLite databases must remain server-side.
- Do not expose SQLite or environment files under a web root.

## RBAC
- viewer: read dashboard, messages, source/sync status.
- sales: viewer permissions + send Lead to SATNO CRM.
- admin: sales permissions + message write + staff user management.

## CRM behavior
`POST /api/leads/{message_id}/send` creates an idempotent `satno.lead.v1` payload and stores it in `crm_lead_outbox`.

If `SATNO_CRM_LEAD_URL` is empty, the Lead stays queued safely. When the endpoint is configured, the same API attempts server-side delivery. The CRM token is never sent to the browser.

## Production readiness checklist
1. All unit/regression tests pass on the Windows Server v0.5 test checkout.
2. Login, logout, expiry and role restrictions verified manually.
3. viewer cannot call write/admin/Lead endpoints.
4. sales can send Leads but cannot manage users.
5. admin can manage users; last active admin cannot be disabled/demoted.
6. Source/Sync status page reflects real data.
7. Sender resolution cache works during a Bale sync.
8. CRM integration tested against the actual SATNO CRM endpoint, or deliberately left in queue-only mode.
9. HTTPS is available and `SESSION_COOKIE_SECURE=1`.
10. Backup current production database and service configuration.
11. Only after explicit approval: deploy v0.5 and configure `market.satnoco.ir`.

## Rollback
v0.5 must be deployed separately from v0.4 until acceptance. If a v0.5 validation fails, stop only the v0.5 process and keep the v0.4 service/branch untouched.
