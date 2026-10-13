---
name: satno-bale-market
description: Develop and maintain SATNO Bale Market Intelligence. Use for collecting Bale channel/group messages, classifying suppliers and buyers, extracting solar products/brands/provinces/prices, de-duplicating leads, building search/dashboard features, exporting reports, and preparing CRM lead integration.
---

# SATNO Bale Market Intelligence

## Objective
Turn Bale market messages into searchable, structured commercial intelligence for SATNO.

## Core entities
Classify messages where possible into:
- supplier / seller
- buyer / demand
- inventory / availability
- tender / inquiry / project
- general market information

Extract useful fields when present:
- product type
- brand/model
- quantity
- price
- province/city
- contact identity if legitimately present in the source data
- message date
- source channel/group
- message reference

## Engineering workflow
1. Preserve raw source references for traceability.
2. Normalize extracted fields without deleting original text.
3. De-duplicate repeated/forwarded messages.
4. Track classification confidence when uncertain.
5. Keep dashboards fast enough for day-to-day staff use.
6. Design CRM integration around stable lead identifiers.

## Deployment considerations
For an always-on Windows Server deployment:
- run the collector/dashboard as managed services
- keep credentials outside source control
- use structured logs
- define restart behavior
- separate development and production configuration

## Reporting
Prefer concise dashboards with filters by brand, province, product type, supply/demand, date, and lead status.
