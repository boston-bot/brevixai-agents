# Phase 4C — Vendor Verification Workflow

Date: 2026-06-03

Status: Complete

## Goal

Convert deterministic vendor risk payloads into a guided reviewer workflow.

This phase is advisory and non-mutating. It does not create alerts, cases, emails, vendor records, payment changes, or verification records.

## Scope

**In scope:**
- Deterministic workflow builder for vendor risk payloads
- Optional entity relationship risk reinforcement
- Review priority based on vendor risk score, risk level, entity relationship score, and elevated vendor count
- Vendor name/id aggregation
- Triggered rule and supporting evidence summaries
- Evidence requests and evidence gaps
- Reviewer next steps
- Escalation criteria
- Non-mutating recommended action: `review_vendor_verification_evidence`
- LangGraph response fields for workflow-aware UI handling
- MCP tool exposure for standalone clients

**Out of scope:**
- Vendor master record retrieval
- W-9, bank document, or ownership document retrieval
- Vendor outreach
- Alert/case creation
- Vendor record or payment changes

## Data Flow

```text
Fraud/vendor risk request
        ↓
vendor_risk and optional entity_relationship_risk
        ↓
app.vendor_verification_workflow.build_vendor_verification_workflow()
        ↓
LangGraph response fields:
  - recommended_workflow
  - next_best_action
  - evidence_gaps
  - scope_limitations
  - readiness_summary
        ↓
Action gate returns non-mutating review_vendor_verification_evidence action
```

If multiple workflows are present, the graph exposes the highest-priority workflow as the primary `recommended_workflow` while retaining each workflow under `tool_results`.

## Output Contract

`build_vendor_verification_workflow()` returns:

```json
{
  "status": "ok",
  "workflow_type": "vendor_verification",
  "review_priority": "high",
  "vendor_count": 1,
  "vendors": ["Harbor Advisory LLC"],
  "vendor_ids": ["vendor-1"],
  "highest_vendor_risk_score": 84,
  "triggered_rules": ["high vendor risk"],
  "supporting_evidence_count": 2,
  "supporting_evidence_ids": ["vendor-1", "txn-1"],
  "evidence_requests": [],
  "evidence_gaps": [],
  "next_steps": [],
  "escalation_criteria": [],
  "recommended_action": {
    "type": "review_vendor_verification_evidence",
    "label": "Review urgent vendor verification evidence",
    "requires_approval": false
  },
  "readiness_summary": {},
  "scope_limitations": []
}
```

## Files Changed

- `app/vendor_verification_workflow.py` — deterministic workflow builder
- `app/graph.py` — publishes vendor verification workflow fields and primary workflow selection
- `mcp_servers/brevix_intelligence/tools/workflows.py` — adds `create_vendor_verification_workflow()`
- `mcp_servers/brevix_intelligence/server.py` — registers `create_vendor_verification_workflow_tool`
- `tests/test_vendor_verification_workflow.py`
- `tests/test_graph.py`
- `tests/test_investigation_synthesis.py`
- `mcp_servers/brevix_intelligence/tests/test_workflows.py`
- `mcp_servers/brevix_intelligence/tests/test_server.py`

## Verification

Targeted run:

```bash
.venv/bin/python -m pytest tests/test_vendor_verification_workflow.py tests/test_graph.py tests/test_investigation_synthesis.py mcp_servers/brevix_intelligence/tests/test_workflows.py mcp_servers/brevix_intelligence/tests/test_server.py
```

Result: 19 passed.

Full agent run:

```bash
.venv/bin/python -m pytest
```

Result: 513 passed.
