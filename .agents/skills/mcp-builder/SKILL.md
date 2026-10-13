---
name: mcp-builder
description: Design and implement MCP servers and tool integrations for SATNO systems. Use when connecting ChatGPT/Codex or agents to SATNO CRM, Bale Market, Tender Radar, WordPress, PrestaShop, databases, internal APIs, VoIP, reporting services, or other external systems through MCP-compatible tools.
---

# MCP Builder for SATNO

## Objective
Create secure, minimal, well-scoped MCP integrations that expose useful SATNO operations to agents.

## Design process
1. Define the exact workflow the agent must perform.
2. Identify the source system and authentication method.
3. Separate read actions from write actions.
4. Design the smallest useful tool surface.
5. Use explicit input schemas and deterministic outputs.
6. Add validation, permission checks, and meaningful errors.
7. Keep secrets outside source control.
8. Document setup, environment variables, and test procedures.

## Tool design principles
Each tool should:
- do one clear job
- have concise, descriptive names
- accept typed inputs
- return structured machine-readable results
- distinguish not-found, permission, validation, and upstream errors
- avoid destructive side effects unless explicitly required

## Security
- Never embed passwords, tokens, OTP values, API keys, or database credentials in code or SKILL.md files.
- Prefer least-privilege service accounts.
- Require explicit confirmation for destructive or externally visible writes where appropriate.
- Log actions without leaking sensitive values.
- Validate all external inputs before using them in queries, shell commands, or filesystem operations.

## SATNO integration priorities
Potential MCP domains include:
- SATNO CRM contacts, leads, projects, finance, and staff workflows
- Bale Market lead/message search and ingestion
- Tender Radar opportunities and CRM queue
- WordPress content/admin operations
- PrestaShop catalog/content operations
- report/PDF generation
- internal engineering calculators
- VoIP support-agent lookups where authorized

## Development workflow
1. Create a local minimal server.
2. Implement one read-only tool first.
3. Add tests with representative inputs and failure cases.
4. Connect the MCP client and verify discovery/calling.
5. Add write tools only after read path is stable.
6. Document versioning and deployment.

## Completion report
Return:
- MCP server structure
- tools exposed
- auth model
- required environment variables
- test results
- deployment steps
- known security or operational limitations
