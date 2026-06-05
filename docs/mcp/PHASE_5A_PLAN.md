# Phase 5A — Relational Readiness Audit

Date: 2026-06-04

Status: Complete

## Goal

Create a deterministic readiness gate before Phase 5 graph intelligence.

This phase does not build graph infrastructure. It audits whether agent-visible payloads have stable entities, identifiers, and relationships needed for graph intelligence.

## Scope

**In scope:**
- Entity contract audit for vendors, employees, bank accounts, payments, approvers, documents, and company users
- Relationship contract audit for:
  - payment-to-vendor
  - employee-approved-payment
  - payment-to-document
  - vendor-to-bank-account
  - employee-to-vendor relationship evidence
  - vendor-to-vendor relationship evidence
- Critical blocker reporting
- Readiness score and readiness summary
- Recommended next steps for missing identifiers
- Non-mutating recommended action: `prepare_relational_data_contracts`
- LangGraph routing for Phase 5 readiness questions
- MCP tool exposure for standalone payload audits

**Out of scope:**
- Graph database setup
- PostgreSQL graph-style query implementation
- Schema migrations
- Laravel endpoint changes
- Alert/case creation
- Data writes or relationship persistence

## Data Flow

```text
Phase 5 readiness question
        ↓
transaction sample + vendor_risk + entity_relationship_risk + company_context
        ↓
app.relational_readiness.build_relational_readiness_audit()
        ↓
LangGraph response fields:
  - next_best_action
  - evidence_gaps
  - scope_limitations
  - readiness_summary
        ↓
Action gate returns non-mutating prepare_relational_data_contracts action
```

## Output Contract

`build_relational_readiness_audit()` returns:

```json
{
  "status": "blocked",
  "audit_type": "relational_readiness",
  "phase_5_ready": false,
  "readiness_score": 0.32,
  "entity_contracts": [],
  "relationship_contracts": [],
  "critical_blockers": [],
  "readiness_summary": {},
  "recommended_action": {
    "type": "prepare_relational_data_contracts",
    "label": "Prepare relational data contracts",
    "requires_approval": false
  },
  "recommended_next_steps": [],
  "scope_limitations": []
}
```

## Files Changed

- `app/relational_readiness.py` — deterministic readiness audit builder and response synthesis
- `app/graph.py` — routes Phase 5 readiness questions and publishes audit fields
- `mcp_servers/brevix_intelligence/tools/relational_readiness.py`
- `mcp_servers/brevix_intelligence/server.py` — registers `audit_relational_readiness_tool`
- `tests/test_relational_readiness.py`
- `tests/test_router.py`
- `mcp_servers/brevix_intelligence/tests/test_relational_readiness.py`
- `mcp_servers/brevix_intelligence/tests/test_server.py`

## Verification

Targeted run:

```bash
.venv/bin/python -m pytest tests/test_relational_readiness.py tests/test_router.py mcp_servers/brevix_intelligence/tests/test_relational_readiness.py mcp_servers/brevix_intelligence/tests/test_server.py
```

Result: 16 passed.

Full agent run:

```bash
.venv/bin/python -m pytest
```

Result: 526 passed.
