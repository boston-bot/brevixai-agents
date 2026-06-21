# Phase 5C — Payload Contract Gate

Date: 2026-06-04

Status: Complete

## Goal

Make the Phase 5B relational payload contract executable against real Laravel agent-tool payloads.

This phase remains read-only. It does not create graph infrastructure, database migrations, Laravel endpoints, alerts, cases, or data writes.

## What Shipped

- `scripts/smoke_relational_contract.py` calls the Laravel agent-tool API and runs the Phase 5A readiness audit against the returned payloads.
- The smoke gate fetches:
  - `company_context`
  - `transaction_lookup`
  - `vendor_risk`
  - `entity_relationship_risk`
- The gate exits nonzero unless:
  - all required calls succeed, and
  - `phase_5_ready` is true under the Phase 5B contract.
- `--allow-blocked` can be used when the goal is to generate a diagnostic report without failing the command.
- JSON output can be written with `--json-output`.

## Usage

Local or staging:

```bash
.venv/bin/python scripts/smoke_relational_contract.py \
  --base-url http://localhost:8000 \
  --tool-key "$BREVIX_LARAVEL_AGENT_TOOL_KEY" \
  --company-id "$COMPANY_ID" \
  --user-id "$USER_ID" \
  --json-output reports/relational_contract_smoke.json
```

Production safety check:

```bash
.venv/bin/python scripts/smoke_relational_contract.py \
  --production \
  --base-url "$BREVIX_LARAVEL_BASE_URL" \
  --tool-key "$BREVIX_LARAVEL_AGENT_TOOL_KEY" \
  --company-id "$COMPANY_ID" \
  --user-id "$USER_ID"
```

Diagnostic report while contracts are still blocked:

```bash
.venv/bin/python scripts/smoke_relational_contract.py \
  --company-id "$COMPANY_ID" \
  --user-id "$USER_ID" \
  --allow-blocked \
  --json-output reports/relational_contract_blockers.json
```

## Expected Current Result

The command should fail until Laravel/API payloads include the stable identifiers required by Phase 5B:

- `company_id`
- `company_user_id`
- `vendor_id`
- `approved_by`
- `document_id`
- `bank_account_id`
- payment `id`
- `date`
- `amount`

## Files Changed

- `scripts/smoke_relational_contract.py`
- `tests/test_relational_contract_smoke.py`
- `docs/mcp/PHASE_5C_PAYLOAD_CONTRACT_GATE.md`
- `docs/mcp/STATUS.md`

## Verification

Targeted run:

```bash
.venv/bin/python -m pytest tests/test_relational_contract_smoke.py tests/test_relational_contracts.py tests/test_relational_readiness.py
```

Result: 14 passed.

Full agent run:

```bash
.venv/bin/python -m pytest
```

Result: 536 passed.
