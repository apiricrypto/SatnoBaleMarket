# Bale discovery hardening — staged rollout

## Scope
- A read-only diagnostic for the missing public channel `@partonorpars`.
- Safety fix: automatic discovery must **never** disable any previously registered sources because its dialog listing is incomplete.
- This patch **does not** claim to resolve the channel's Peer ID.
- This patch **does not** touch the CRM URL, credentials, tasks, the live DB or other server services.

## Known evidence
1. Bale `resolve("partonorpars")` and `resolve("@partonorpars")` raised `LookupError`.
2. An earlier full dialog iteration scanned 1422 items and found no matching title.
3. A bad result named `A` was a **user peer type 1**, id `533091513`, with a stale `query_text` association. It was not the channel.
4. The user has confirmed that the same Bale account is subscribed to the target.
5. Thus the real target Peer ID is **unknown**, and no guessed IDs may be registered.

## Testing (isolated environment)
```powershell
cd C:\Satno\SatnoBaleMarket-v05-test
git fetch origin
git switch fix/bale-discovery-hardening-20261013
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m py_compile discover_sources.py tools/diagnose_bale_discovery.py
```

Note: If the test working directory has local changes, stop and protect those changes before switching branches.

## Read-only field diagnostic (authorized account only)
```powershell
.\.venv\Scripts\python.exe tools/diagnose_bale_discovery.py
```
This prints counts and ONLY target-matching public titles/peer identifiers, never the token or message bodies. The 240-second ceiling applies to the entire diagnostic.

## Acceptance and release gates
- Unit tests pass in CI and in the dedicated test directory.
- Discovery no longer changes `enabled` for absent sources.
- Diagnostic confirms dialog totals, type distribution, title completeness, and named match count.
- A candidate is never added from `query_text` alone.
- If the target is absent again, investigate SDK protocol/account visibility from diagnostics; do not repeatedly search or claim it is resolved.
- Record test outputs; validate web health and Sync status on the dedicated test deployment before any production merge.

## Production safeguards
- **Do not** run this as a production upgrade without test approval.
- Back up DB and tracked runtime files, and keep CRM live sending disabled.
- Do not run `discover_sources.py` casually: it is a separate explicit registry-changing discovery command, even though it no longer disables absent sources.
- Never reset/clean local production files, stop non-Bale services, or expose `BALE_TOKEN`.
