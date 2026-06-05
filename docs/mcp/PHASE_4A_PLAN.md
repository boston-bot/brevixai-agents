# Phase 4A — IRS Notice Review Workflow

Date: 2026-05-31

Status: Complete

## Goal

Convert the Phase 3 IRS notice extraction payload into a guided reviewer workflow.

This phase does not create cases, alerts, emails, correspondence, or IRS submissions. It turns extracted notice facts and retrieved IRM references into structured review guidance that the app can display or hand to a human reviewer.

## Scope

**In scope:**
- Deterministic workflow builder for extracted IRS notice payloads
- Notice family classification (`collection`, `underreporter`, `payroll_tax`, `general_notice`)
- Deadline urgency and review priority
- Evidence requests and evidence gaps
- Reviewer next steps
- Escalation criteria
- Source IRM reference propagation
- Non-mutating recommended action: `prepare_irs_notice_review`
- LangGraph response fields for workflow-aware UI handling
- MCP tool exposure for standalone clients

**Out of scope:**
- Creating alerts or cases
- Sending messages or IRS responses
- Upload parsing, OCR, or persistence
- Human approval execution flow
- Fraud workflow tools for non-IRS findings

## Data Flow

```text
User pastes IRS notice text
        ↓
irs_notice_extract
        ↓
Laravel extraction + IRM lookup
        ↓
app.irs_notice_workflow.build_irs_notice_workflow()
        ↓
LangGraph response fields:
  - recommended_workflow
  - next_best_action
  - evidence_gaps
  - scope_limitations
  - readiness_summary
        ↓
Deterministic final answer with workflow next steps, evidence, escalation criteria, IRM references, and disclaimer
```

## Output Contract

`build_irs_notice_workflow()` returns:

```json
{
  "status": "ok",
  "workflow_type": "irs_notice_review",
  "notice_type": "CP504",
  "issue_family": "collection",
  "review_priority": "critical",
  "deadline_urgency": "medium",
  "deadline_days": 30,
  "key_amount": 5000.0,
  "evidence_requests": [],
  "evidence_gaps": [],
  "next_steps": [],
  "escalation_criteria": [],
  "source_references": ["5.11.1.1"],
  "recommended_action": {
    "type": "prepare_irs_notice_review",
    "label": "Prepare urgent CP504 notice review",
    "requires_approval": false
  },
  "readiness_summary": {},
  "scope_limitations": []
}
```

## Files Changed

- `app/irs_notice_workflow.py` — deterministic workflow builder
- `app/irs_procedural.py` — attaches workflow details to notice extraction synthesis
- `app/graph.py` — publishes workflow response fields and non-mutating recommended action
- `app/main.py` — includes workflow fields in streaming completion payloads
- `mcp_servers/brevix_intelligence/tools/workflows.py` — adds `create_irs_notice_review()`
- `mcp_servers/brevix_intelligence/server.py` — registers `create_irs_notice_review_tool`
- `datasets/irs_answer_quality_fixtures.json` — adds pasted CP504 workflow fixture
- `tests/test_irs_notice_workflow.py`
- `tests/test_irs_notice_extraction.py`
- `tests/test_irs_answer_quality.py`
- `mcp_servers/brevix_intelligence/tests/test_workflows.py`
- `mcp_servers/brevix_intelligence/tests/test_server.py`

## Verification

Targeted run:

```bash
.venv/bin/python -m pytest tests/test_irs_notice_workflow.py tests/test_irs_notice_extraction.py mcp_servers/brevix_intelligence/tests/test_workflows.py mcp_servers/brevix_intelligence/tests/test_server.py
```

Result: 16 passed.

Full agent run:

```bash
.venv/bin/python -m pytest
```

Result: 499 passed.
