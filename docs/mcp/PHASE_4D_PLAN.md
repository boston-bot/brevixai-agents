# Phase 4D — Payroll Tax Review Workflow

Date: 2026-06-04

Status: Complete

## Goal

Convert source-backed IRS payroll tax procedural payloads into a guided reviewer workflow.

This phase is advisory and non-mutating. It does not create alerts, cases, emails, IRS submissions, payroll changes, payment changes, or correspondence.

## Scope

**In scope:**
- Deterministic workflow builder for IRS payroll tax procedural payloads
- Payroll tax, employment tax, Form 941, EFTPS deposit, and trust fund recovery penalty detection
- Review priority based on issue type, deadline, amount exposure, and risk level when present
- Source IRM reference extraction
- Recommended record and tax period summaries
- Responsible-person review flag for TFRP issues
- Evidence requests and evidence gaps
- Reviewer next steps
- Escalation criteria
- Non-mutating recommended action: `review_payroll_tax_evidence`
- LangGraph response fields for workflow-aware UI handling
- MCP tool exposure for standalone clients

**Out of scope:**
- Payroll ledger retrieval
- EFTPS account lookup
- IRS account transcript retrieval
- Tax return file retrieval
- Responsible-person interviews
- Alert/case creation
- IRS correspondence or submissions
- Payroll or payment changes

## Data Flow

```text
IRS payroll/TFRP procedural request
        ↓
irs_collection_risk or irs_records_checklist
        ↓
app.payroll_tax_workflow.build_payroll_tax_review_workflow()
        ↓
LangGraph response fields:
  - recommended_workflow
  - next_best_action
  - evidence_gaps
  - scope_limitations
  - readiness_summary
        ↓
Action gate returns non-mutating review_payroll_tax_evidence action
```

## Output Contract

`build_payroll_tax_review_workflow()` returns:

```json
{
  "status": "ok",
  "workflow_type": "payroll_tax_review",
  "issue_type": "trust_fund_recovery_penalty",
  "review_priority": "high",
  "responsible_person_review_required": true,
  "source_references": ["5.7.1.1"],
  "recommended_records": ["IRS notice", "account transcript", "EFTPS payment history"],
  "tax_periods": ["2025-Q4"],
  "evidence_requests": [],
  "evidence_gaps": [],
  "next_steps": [],
  "escalation_criteria": [],
  "recommended_action": {
    "type": "review_payroll_tax_evidence",
    "label": "Urgent review trust fund payroll tax evidence",
    "requires_approval": false
  },
  "readiness_summary": {},
  "scope_limitations": []
}
```

## Files Changed

- `app/payroll_tax_workflow.py` — deterministic workflow builder
- `app/irs_procedural.py` — payroll/TFRP routing support and workflow answer synthesis
- `app/graph.py` — publishes payroll tax workflow fields for IRS procedural runs
- `mcp_servers/brevix_intelligence/tools/workflows.py` — adds `create_payroll_tax_review()`
- `mcp_servers/brevix_intelligence/server.py` — registers `create_payroll_tax_review_tool`
- `tests/test_payroll_tax_workflow.py`
- `tests/test_router.py`
- `mcp_servers/brevix_intelligence/tests/test_workflows.py`
- `mcp_servers/brevix_intelligence/tests/test_server.py`

## Verification

Targeted run:

```bash
.venv/bin/python -m pytest tests/test_payroll_tax_workflow.py tests/test_router.py mcp_servers/brevix_intelligence/tests/test_workflows.py mcp_servers/brevix_intelligence/tests/test_server.py
```

Result: 19 passed.

Full agent run:

```bash
.venv/bin/python -m pytest
```

Result: 520 passed.
