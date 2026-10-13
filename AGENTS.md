# SATNO Bale Market — Agent Instructions

Read README.md and the relevant source/tests before changing behavior. The current maintained branch is `feature/staff-v05`; inspect branch state before editing.

## Local skills
- Product/search/collector work: `.agents/skills/satno-bale-market/SKILL.md`.
- Interface and forms: `frontend-design`; company identity: `satno-brand`.
- Browser/RTL regression: `webapp-testing`.
- MCP integrations: `mcp-builder`.
Load only applicable skills, preserving project conventions.

## Product boundaries
Preserve Persian RTL, Jalali presentation, explicit Rial/Toman units, raw message text and source references. Normalize Arabic/Persian letter variants and spacing for search without destroying originals. Preserve RBAC, sessions and the last active administrator. Keep CRM live delivery disabled until explicitly authorized and verified; test connector changes with loopback fixtures. Never commit Bale session data, tokens, passwords, customer data or production databases.

## Verification
For runtime changes run `python -m unittest discover -s tests -v`. The existing Windows checks are `scripts/test-v05-windows.ps1` and `scripts/test-crm-adapter-windows.ps1`. Verify `/health` and key user flows when the app runs. For skill-only changes check YAML name/description, local references and source hashes; do not claim runtime tests were executed if they were not.

Skills are versioned instructions, not installed external plugins or scheduled jobs. Prefer existing dependencies and free tooling. Check quotas before metered calls; do not buy or upgrade services without authorization.
