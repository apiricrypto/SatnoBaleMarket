---
name: frontend-design
description: Design and refine distinctive, production-quality frontend interfaces for SATNO projects. Use for SATNO CRM, Bale Market dashboards, Tender Radar interfaces, WordPress/PrestaShop pages, admin panels, landing pages, responsive layouts, RTL/Persian UX, and any request involving frontend visual design or interface polish.
---

# Frontend Design for SATNO

## Objective
Create professional, distinctive, responsive interfaces that feel specific to the SATNO product and audience rather than generic AI-generated SaaS templates.

## Design context
Before implementing:
1. Identify the product, primary users, and job of the screen.
2. Reuse existing SATNO visual identity and product conventions when applicable.
3. For Persian-first products, design RTL intentionally rather than mirroring an LTR layout as an afterthought.
4. Avoid decorative patterns that do not encode useful information.

## Visual principles
- Use strong hierarchy, restrained decoration, and clear information architecture.
- Prefer deliberate typography and spacing over excessive cards, shadows, gradients, and badges.
- Avoid generic "AI dashboard" styling.
- Let one or two elements carry visual character; keep the rest disciplined.
- Optimize for real data density when building operational dashboards.

## SATNO-specific guidance
For SATNO interfaces:
- Persian is the default user-facing language unless explicitly overridden.
- RTL alignment must be verified at component level.
- Jalali dates and Rial/Toman formatting should visually align with Persian content.
- Mobile behavior is required, especially for field staff and managers.
- Buttons and labels should describe the exact action in clear Persian.

## Workflow
1. Inspect the existing design system/components before adding new patterns.
2. Define a compact design direction: typography, spacing, palette, layout, and interaction behavior.
3. Build the smallest coherent visual change.
4. Verify desktop, tablet, and mobile layouts.
5. Verify keyboard focus, contrast, reduced-motion behavior, and error/empty states.
6. Take screenshots when the environment supports it and critique the result visually.
7. Refine any element that looks copied, templated, or inconsistent with the rest of the product.

## Output
For implementation work, report:
- design decisions
- changed components/files
- responsive/RTL considerations
- accessibility checks
- known visual inconsistencies remaining
