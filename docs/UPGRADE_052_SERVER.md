# Windows production upgrade review — UI/Auth 0.5.2

Observed installation: `C:\Satno\SatnoBaleMarket-v05`, Python `.venv\Scripts\python.exe`, web port 8000, launcher `run-web.cmd`, scheduled task `SATNO-BaleMarket-v05-Web`.

Observed current server commit: `150481018be411e5a440dffa5bc4b689d2f1b0fb`. The UI branch now merges that exact commit. Its Sync worker, singleton locking, registry-only polling, username verification, discovery guards, database schema and interval configuration are retained. The source-management UI retains production's atomic bulk-delete API, filtered selection and two-stage confirmation. It does not revert to sequential deletion.

## Approval scope

No production operations have been executed by the agent. Before executing the upgrade, obtain explicit approval for a short interruption of the web task and local backup/code updates. Review this sequence:

1. Record full HEAD and current branch. Check tracked/staged changes; stop if any exist. Preserve all untracked/ignored files, including launcher scripts, `.env.local`, certificate, backups, logs and the live Sync lock. Never use `git clean` or `reset --hard`.
2. Fetch and pin the approved UI branch commit. Verify `git merge-base --is-ancestor 150481018be411e5a440dffa5bc4b689d2f1b0fb <approved-sha>` succeeds. Check target tracked files do not collide with existing untracked files. Verify Sync-related files have no changes against the observed server commit.
3. Make a dated backup outside the checkout. Save HEAD/branch, the web task XML (without changing it), launcher/config/certificate/untracked files, and an online SQLite backup using Python `sqlite3.Connection.backup()` against the application's actual resolved database path. Do not copy only a live SQLite main file or treat a copied lock as a runtime lock. Keep backups private and do not paste credentials into chat.
4. Stop only `SATNO-BaleMarket-v05-Web`. Verify the process listening on port 8000 has exited; if not, identify its executable/command before terminating only the confirmed web process. Do not use blanket Python/taskkill commands.
5. Switch to the exact approved commit without discarding files. No dependency upgrade or schema command is required for this change: production requirements and database schema match the server baseline. The additional HTTPX dependency is for development/CI tests only.
6. Start only the same web task through its existing `run-web.cmd`. Verify `/health` reports `ok` and `0.5.2`; verify `/login` and `/assets/satno-logo.jpg`. Test login, logout and own-password change using a designated test account; do not alter a real staff password without that person's approval. Confirm existing sources remain unchanged and live CRM remains disabled.
7. If any readiness check fails, stop only the web task, switch back to the recorded original commit, start the web task and confirm `0.5.1`. Preserve newly written operational data; do not restore a stale database over a concurrently running Sync. Database restoration requires a separate decision.

Do not stop, disable, reconfigure or recreate `SATNO-BaleMarket-v05-Sync`; do not delete `satno_market.db.sync.lock`. Do not touch legacy disabled tasks, Issabel, Tender Radar or other services. The snapshot backup is a recovery checkpoint, not permission to modify production data.

## Local validation

Linux: 101 unittest cases passed. Browser acceptance passed at 375/768/1440 with independent temporary SQLite data and random credentials; no page/console errors or horizontal overflow. Updated screenshots are in `docs/ui-evidence`. PowerShell/server execution and production behavior remain unverified until the approved rollout is performed.
