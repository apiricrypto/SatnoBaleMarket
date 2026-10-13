---
name: webapp-testing
description: Test SATNO web applications end-to-end with browser automation. Use for SATNO CRM, Bale Market dashboards, Tender Radar admin UI, WordPress/PrestaShop flows, regression checks, responsive/RTL validation, form testing, navigation testing, screenshot verification, console/network error inspection, and release readiness.
---

# Web Application Testing for SATNO

## Objective
Verify real user workflows in SATNO web applications using repeatable browser-based tests.

## Preferred approach
Use Playwright or the environment's browser/computer-use tooling when available.

## Test workflow
1. Confirm the app URL/environment and whether authentication is required.
2. Inspect the rendered UI before guessing selectors.
3. Use stable selectors:
   - role/name
   - labels
   - test IDs
   - semantic attributes
4. Avoid brittle CSS selectors tied to generated class names.
5. Execute realistic user flows.
6. Capture screenshots for visual/RTL issues where useful.
7. Inspect browser console and failed network requests.
8. Record exact reproduction steps for failures.

## SATNO regression checklist
Where relevant test:
- Persian/RTL layout
- Jalali date rendering/input
- Rial/Toman formatting
- navigation drawer/menu
- login/auth flows
- forms and validation
- CRUD workflows
- search/filter/sort
- mobile viewport behavior
- dashboard metrics
- file/report export
- CRM integrations
- Tender Radar intake
- Bale Market lead intake

## Release gate
Do not call a build ready when:
- critical console errors remain
- primary workflows fail
- mobile or RTL layout is broken
- data mutations produce inconsistent results
- test environment differs materially from the intended deployment and this difference is not documented

## Reporting
For each test run provide:
- environment tested
- flows tested
- pass/fail status
- screenshots or evidence when useful
- console/network errors
- exact blocker severity
- recommended next action
