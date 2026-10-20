# Email password recovery — SATNO Bale Market

Implemented for **admin, sales and viewer** using the same recovery flow. This release does not register real email addresses automatically, configure production SMTP, stop the web task, or send messages to real users from the development environment.

## Where to find SMTP details

- **cPanel:** Email Accounts → Connect Devices (next to the sending mailbox) → Secure SSL/TLS Settings.
- **Plesk:** Mail → select mailbox → Mail Client Setup / Manual Setup.
- Other mail service: SMTP / mail client settings, or ask hosting support for authenticated outbound SMTP settings.

Collect outgoing server hostname, port, SSL/TLS mode, SMTP username and sending mailbox address. The sender is a domain mailbox used by the application; it is separate from the administrator's recovery recipient. The public application URL is the actual address users enter in the browser. Never copy the mailbox password or a reset link/token into chat, Git, screenshots, logs or a public support ticket.

## Server configuration

Add to the existing private `.env.local`, preserving all Bale/CRM/Sync settings:

```dotenv
SATNO_PUBLIC_BASE_URL=https://market.example.com
SATNO_SMTP_HOST=smtp.example.com
SATNO_SMTP_PORT=587
SATNO_SMTP_SECURITY=starttls
SATNO_SMTP_USERNAME=recovery@example.com
SATNO_SMTP_FROM=recovery@example.com
SATNO_SMTP_PASSWORD=REPLACE_PRIVATELY_ON_SERVER
SATNO_RECOVERY_ALLOW_HTTP=0
```

Use the provider's actual settings; port 465 normally uses `SATNO_SMTP_SECURITY=ssl`. Both modes verify server certificates and never authenticate before successful TLS. No paid dependency or mail API is required. Credentials are read server-side only. Do not use browser/VITE variables.

The public base URL is configured explicitly, never derived from incoming Host/forwarded headers. HTTPS is required except loopback tests. For a specifically accepted LAN-only HTTP installation, `SATNO_RECOVERY_ALLOW_HTTP=1` is an explicit operator opt-in; do not silently enable it. Use the real application origin and port, without a path/query/fragment.

Until all settings exist, the recovery page clearly says email sending is not configured and disables requests. `/api/auth/recovery-status` exposes only an enabled boolean, not SMTP details or account existence. A configured transport can still fail remotely: delivery failures produce only a generic server warning, without credentials, recipient or token.

## Register recovery emails

Administrators can assign/edit an optional recovery email in `/admin/users`, including their own account, or supply `--email` with `create_staff_user.py`. Addresses are normalized and unique across users. Ordinary sales/viewer accounts cannot list or change the administration email directory. A public recovery request never changes a registered email.

To register the requested administrator address on the actual server after code upgrade/migration and backup, use the operator tool with explicit production database path:

```powershell
# Inspect selection only — no database writes:
.\.venv\Scripts\python.exe tools\set_admin_email.py --database C:\Satno\SatnoBaleMarket-v05\satno_market.db --email YOUR_ADMIN_RECOVERY_EMAIL

# Apply to that administrator after checking the selection:
.\.venv\Scripts\python.exe tools\set_admin_email.py --database C:\Satno\SatnoBaleMarket-v05\satno_market.db --email YOUR_ADMIN_RECOVERY_EMAIL --apply
```

If more than one active administrator exists, the tool refuses to choose: add `--username EXACT_ADMIN_USERNAME`. It does not create a database, select a temporary inherited DATABASE_PATH, change passwords/roles or disable users. Real recipient addresses are intentionally absent from this repository. The user-supplied administrator address still needs this explicit server-side assignment; it has not been written to production by this cloud work.

## Recovery behavior

1. `/login` links to `/forgot-password`. The user enters the registered email.
2. The HTTP response is identical for known, unknown, inactive and throttled addresses. A background task sends mail only for an active matching account. It never returns a token/account ID to the browser requesting recovery.
3. The email contains `/reset-password#token=...`, a 256-bit random token valid for 30 minutes. The fragment is not sent to web access logs; the page removes it from the address bar immediately and keeps it in memory only. Reloading requires reopening the email link. Recovery pages use no-store/no-referrer and a local-only script CSP.
4. The user enters and confirms a new password (12–512 characters, different from the current password). Opening a link does not consume it or change a password. No automatic login follows reset.
5. Successful reset atomically updates the PBKDF2 hash, consumes all outstanding recovery links for the account, and revokes every session. The same token cannot be reused. Users log in with the new password.

Tokens are stored only as SHA-256 hashes and are bound to the current email and active account. A new recovery link invalidates older links. Failed delivery invalidates its token. Email changes, account/role changes, administrator password resets and authenticated own-password changes invalidate pending links. The last-active-admin protection remains intact.

Rate reservations are atomic and persisted in SQLite, keyed by hashed normalized email and client IP: one request/minute and three/15 minutes per address, thirty/hour per IP. Throttling never changes the login password or disables the account. Uvicorn's actual client address is used; application code does not trust arbitrary X-Forwarded-For headers. Request keys older than a day and tokens expired more than a day are pruned during request handling; no Task Scheduler job is added.

Session issuance rechecks the password hash/active state under the same write-order boundary as reset. Authenticated own-password changes are also serialized, preventing an in-flight request with old credentials from undoing a concurrent recovery.

## Additive migration and installation

Baseline production last reported by the operator: `91a4717`. Database initialization adds nullable `staff_users.email`, a case-insensitive unique non-null email index, `staff_password_resets` and `staff_reset_requests`. Existing users/passwords/sessions/messages/queues remain intact. No email is guessed from names, ads or role. All old users initially have no recovery address until assigned.

Before installing: back up the production database via SQLite backup and save current code/config/task settings. After fetching the reviewed commit, stop only the existing web task, switch code, run the existing initialization against the explicit production database and restart web. Configure private SMTP/origin values and assign the selected admin address. Verify health/login, new recovery assets/pages, the enabled status and an explicitly designated operator test account/inbox before announcing real delivery working. Do not change hourly Sync, source settings or CRM delivery. Do not paste SMTP passwords in commands visible to chat. This release's cloud tests do not prove production DNS/firewall/authentication or inbox delivery.

Previous code tolerates the additional nullable column/tables; a code rollback can preserve newly collected operational data. Never restore an older database over concurrently running Sync.

## Validation — 2026-10-20

- Full unittest discovery: **203 passed**.
- Recovery suite: real loopback STARTTLS delivery with certificate validation, all three roles, hashed/expired/single-use links, email rebinding and password changes, generic responses, persisted/concurrent rate limits, simultaneous consumption, both authentication races, no cleartext authentication/verified SSL context, email/RBAC/migration and explicit operator database/account selection.
- `python tools/verify_password_recovery.py --artifacts /tmp/recovery-ui`: real local TLS SMTP → browser reset → old password/session rejection for admin/sales/viewer; confirmation mismatch, token reuse, email management, screenshots at 375/768/1440; no browser errors or raw token in access logs.
- Existing `tools/verify_ui.py` regression: eight pages at 375/768/1440, business/contact/queue flows, login/logout/password/admin reset/RBAC/source deletion passed without page overflow or console errors.
- Screenshots in `docs/auth-recovery-evidence/` contain synthetic accounts only. No SMTP test server/backdoor is added to production app startup. The test fixture binds only to loopback and uses temporary certificates; its runner requires development Playwright/Chromium/OpenSSL, not a new production dependency. On a test host without OpenSSL the real-TLS unittest is explicitly skipped; the other recovery tests still run.

## Compatibility with local server recovery

The integrated release preserves server commit `c9a71c8`: public username requests, the administrator request queue, and `reset_admin_password.py --database` remain available alongside email recovery. The public endpoint accepts exactly one identifier: `email` returns the generic email response (200); `username` records the generic administrator request (202), including when SMTP is unavailable. Password changes resolve pending administrator requests and invalidate outstanding email links and sessions, including emergency server recovery. The original server regression tests are retained in `tests/test_admin_password_recovery.py`.
