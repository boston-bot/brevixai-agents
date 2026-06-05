# Phase 5E — Relational Graph Projection

Date: 2026-06-04

Status: Complete

## Goal

Build the first read-only graph-shaped projection from Phase 5-ready payloads.

This phase does not add graph infrastructure. It does not create a graph database, database migrations, Laravel endpoints, alerts, cases, records, or data writes.

## What Shipped

- `app/relational_graph_projection.py` builds deterministic nodes, edges, relationship insights, graph summaries, and a non-mutating review action.
- The projection is gated by `build_relational_readiness_audit()`. If `phase_5_ready` is false, it returns `status=blocked` with no nodes or edges.
- The existing relational readiness LangGraph path attaches `tool_results["relational_graph_projection"]` only when the readiness audit passes.
- MCP `build_relational_graph_projection_tool` exposes the same read-only projection builder for standalone clients.

## Projection Contract

The projection returns:

- `projection_type`: `relational_graph_projection`
- `status`: `ready` or `blocked`
- `phase_5_ready`
- `readiness_score`
- `nodes`
- `edges`
- `graph_summary`
- `relationship_insights`
- `recommended_action.type`: `review_relational_graph_projection`
- `scope_limitations`

## Node Types

- `company`
- `company_user`
- `payment`
- `vendor`
- `employee`
- `bank_account`
- `document`

## Edge Types

- `payment_to_vendor`
- `employee_approved_payment`
- `payment_to_document`
- `vendor_uses_bank_account`
- `employee_shares_address_with_vendor`
- `vendor_related_to_vendor`

The projection also includes company/user scope edges for review context.

## Relationship Insights

Initial deterministic insights include:

- vendors sharing a bank account
- employee-to-vendor relationship edges
- vendor-to-vendor related-party edges

These are evidence summaries only. They do not rescore risk or create alerts/cases.

## Verification

Targeted run:

```bash
.venv/bin/python -m pytest tests/test_relational_graph_projection.py tests/test_router.py mcp_servers/brevix_intelligence/tests/test_relational_readiness.py mcp_servers/brevix_intelligence/tests/test_server.py
```

Full agent run:

```bash
.venv/bin/python -m pytest
```
