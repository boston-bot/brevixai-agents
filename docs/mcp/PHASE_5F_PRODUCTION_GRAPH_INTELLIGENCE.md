# Phase 5F — Production Graph Intelligence Activation

Date: 2026-06-04

Status: Complete

## Goal

Promote the read-only relational graph projection into an explicit user-facing graph intelligence path.

This phase does not create graph infrastructure. It does not create a graph database, database migrations, Laravel endpoints, alerts, cases, records, or data writes.

## What Shipped

- Added a dedicated `relational_graph_intelligence` intent for graph and relationship prompts.
- Added routing for prompts such as:
  - show entity graph
  - related vendors
  - vendors sharing bank accounts
  - employee/vendor overlap
  - approval relationships
  - relationship insights
- Added a dedicated graph-intelligence analysis branch in `app/graph.py`, separate from fraud analysis.
- The branch runs the Phase 5 readiness gate first.
- If readiness is blocked, the response returns no projection nodes or edges and recommends `prepare_relational_data_contracts`.
- If readiness passes, the response returns `tool_results["relational_graph_projection"]`, first-class `relationship_insights`, and non-mutating `review_relational_graph_projection`.
- Added deterministic graph-intelligence final-answer synthesis.

## Response Contract

Ready graph-intelligence responses include:

- `intent`: `relational_graph_intelligence`
- `tool_results["relational_readiness_audit"]`
- `tool_results["relational_graph_projection"]`
- `relationship_insights`
- `next_best_action.type`: `review_relational_graph_projection`
- `scope_limitations`
- `readiness_summary.graph_summary`

Blocked graph-intelligence responses include:

- `intent`: `relational_graph_intelligence`
- `tool_results["relational_readiness_audit"]`
- `tool_results["relational_graph_projection"].status`: `blocked`
- no projection nodes or edges
- `evidence_gaps`
- `next_best_action.type`: `prepare_relational_data_contracts`

## Safety Boundary

The graph-intelligence path is read-only and advisory.

It does not:

- rescore risk
- create alerts
- create cases
- write graph nodes or edges
- mutate accounting records
- send messages
- perform arbitrary SQL

## Verification

Targeted run:

```bash
.venv/bin/python -m pytest tests/test_router.py tests/test_relational_graph_projection.py tests/test_prompts.py tests/test_investigation_synthesis.py
```

Full agent run:

```bash
.venv/bin/python -m pytest
```
