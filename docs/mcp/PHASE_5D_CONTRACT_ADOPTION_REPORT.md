# Phase 5D — Contract Adoption Report

Date: 2026-06-04

Status: Complete

## Goal

Turn the Phase 5C smoke gate into an actionable Laravel/API adoption report.

This phase remains read-only. It does not create graph infrastructure, database migrations, Laravel endpoints, alerts, cases, records, or data writes.

## What Shipped

- `app/relational_contract_adoption.py` maps Phase 5 readiness blockers to the Laravel agent-tool payloads that need contract changes.
- `scripts/smoke_relational_contract.py` now includes `adoption_report` in JSON output and prints endpoint-level API tasks in the console report.
- `mcp_servers/brevix_intelligence/tools/relational_readiness.py` exposes a reusable `build_relational_contract_adoption()` helper.
- `mcp_servers/brevix_intelligence/server.py` registers `build_relational_contract_adoption_report_tool`.

## Report Contract

The adoption report returns:

- `report_type`: `relational_contract_adoption`
- `status`: `ready` or `blocked`
- `phase_5_ready`
- `readiness_score`
- `blocking_endpoint_count`
- `endpoint_requirements`
- `api_remediation_tasks`
- `acceptance_checks`
- `recommended_action.type`: `update_laravel_relational_payloads`
- `scope_limitations`

## Endpoint Mapping

The report maps blockers to these agent-tool payloads:

- `company_context`
- `transaction_lookup`
- `vendor_risk`
- `entity_relationship_risk`

The highest-priority payload remains `transaction_lookup`, because it is the core source for payment, vendor, approver, document, bank-account, company, and company-user anchors.

## Expected Use

Run the smoke gate after Laravel/API payload changes:

```bash
.venv/bin/python scripts/smoke_relational_contract.py \
  --base-url "$BREVIX_LARAVEL_BASE_URL" \
  --tool-key "$BREVIX_LARAVEL_AGENT_TOOL_KEY" \
  --company-id "$COMPANY_ID" \
  --user-id "$USER_ID" \
  --json-output reports/relational_contract_smoke.json
```

If the gate fails, use `adoption_report.api_remediation_tasks` to identify the endpoint and missing stable identifiers.

## Verification

Targeted run:

```bash
.venv/bin/python -m pytest tests/test_relational_contract_adoption.py tests/test_relational_contract_smoke.py mcp_servers/brevix_intelligence/tests/test_relational_readiness.py mcp_servers/brevix_intelligence/tests/test_server.py
```

Full agent run:

```bash
.venv/bin/python -m pytest
```
