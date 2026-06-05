# Phase 4B — Duplicate Payment Review Workflow

Date: 2026-05-31

Status: Complete

## Goal

Convert deterministic duplicate-payment findings into a guided reviewer workflow.

This phase is advisory and non-mutating. It does not create alerts, cases, emails, vendor communications, transaction changes, or remediation records.

## Scope

**In scope:**
- Deterministic workflow builder for existing duplicate-payment findings
- Review priority based on severity, confidence, duplicate count, and amount exposure
- Vendor and transaction ID aggregation from finding evidence
- Evidence requests and evidence gaps
- Reviewer next steps
- Escalation criteria
- Non-mutating recommended action: `review_duplicate_payment_evidence`
- LangGraph response fields for workflow-aware UI handling
- MCP tool exposure for standalone clients

**Out of scope:**
- `transaction_detail` lookup
- Invoice or document retrieval
- Vendor outreach
- Alert/case creation
- Automated refund, void, or remediation actions

## Data Flow

```text
Fraud request
        ↓
deterministic duplicate payment analysis
        ↓
converted AgentFinding records
        ↓
app.duplicate_payment_workflow.build_duplicate_payment_review_workflow()
        ↓
LangGraph response fields:
  - recommended_workflow
  - next_best_action
  - evidence_gaps
  - scope_limitations
  - readiness_summary
        ↓
Action gate returns non-mutating review_duplicate_payment_evidence action
```

## Output Contract

`build_duplicate_payment_review_workflow()` returns:

```json
{
  "status": "ok",
  "workflow_type": "duplicate_payment_review",
  "review_priority": "high",
  "duplicate_count": 1,
  "vendors": ["ABC Supply"],
  "transaction_ids": ["txn-1", "txn-2"],
  "total_amount_exposure": 1840.22,
  "highest_confidence": 0.85,
  "evidence_requests": [],
  "evidence_gaps": [],
  "next_steps": [],
  "escalation_criteria": [],
  "recommended_action": {
    "type": "review_duplicate_payment_evidence",
    "label": "Review urgent duplicate payment evidence",
    "requires_approval": false
  },
  "readiness_summary": {},
  "scope_limitations": []
}
```

## Files Changed

- `app/duplicate_payment_workflow.py` — deterministic workflow builder
- `app/graph.py` — publishes duplicate-payment workflow response fields and non-mutating recommended action
- `mcp_servers/brevix_intelligence/tools/workflows.py` — adds `create_duplicate_payment_review()`
- `mcp_servers/brevix_intelligence/server.py` — registers `create_duplicate_payment_review_tool`
- `tests/test_duplicate_payment_workflow.py`
- `tests/test_graph.py`
- `mcp_servers/brevix_intelligence/tests/test_workflows.py`
- `mcp_servers/brevix_intelligence/tests/test_server.py`

## Verification

Targeted run:

```bash
.venv/bin/python -m pytest tests/test_duplicate_payment_workflow.py tests/test_graph.py mcp_servers/brevix_intelligence/tests/test_workflows.py mcp_servers/brevix_intelligence/tests/test_server.py
```

Result: 11 passed.

Full agent run:

```bash
.venv/bin/python -m pytest
```

Result: 506 passed.
