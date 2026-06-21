# Brevix Intelligence — MCP Status

## What Has Been Built

### Intelligence Layer (`mcp_servers/brevix_intelligence/`)

A deterministic financial analysis layer wired directly into the LangGraph agent. All tools are read-only, scoped by `company_id`, and return structured findings with confidence scores, evidence, and recommended next steps.

**Infrastructure**

| File | Purpose |
|---|---|
| `config.py` | Settings for thresholds and API connection, loaded from `.env` |
| `client.py` | Thin wrapper over `LaravelToolClient` for fetching transactions |
| `auth.py` | `company_id` validation and structured audit logging per tool call |
| `schemas/findings.py` | `Finding` and `ToolResult` Pydantic models |
| `schemas/evidence.py` | `EvidenceItem` model |

**Fraud Detection Tools**

| Tool | What it detects |
|---|---|
| `tools/duplicate_payments.py` | Same vendor, same or near-identical amount, within 30 days — scored by invoice number and memo similarity |
| `tools/vendor_concentration.py` | Any vendor receiving more than 30% of total spend |
| `tools/dormant_vendor.py` | Vendors inactive for 90+ days that suddenly get paid again |
| `tools/cash_burn.py` | Month-over-month outflow acceleration over the trailing 12 months |
| `tools/control_weaknesses.py` | Missing approvals, missing documentation, single-approver dominance |

**IRS Knowledge Tools**

`tools/irs_knowledge.py` is no longer a stub. It is a read-only adapter over Laravel-owned IRS/IRM endpoints backed by parsed RDS data. The Python MCP layer does not query RDS directly.

| Tool | What it does |
|---|---|
| `search_irm(topic)` | Searches parsed IRM content by keyword/topic |
| `get_irm_section(reference)` | Retrieves one IRM section by exact reference |
| `explain_notice_type(notice_code)` | Looks up source-backed procedural information for notices such as `CP504`, `LT11`, and `CP2000` |
| `extract_irs_notice(notice_text)` | Extracts structured notice fields from pasted IRS notice text and chains into source-backed IRM sections |
| `summarize_collection_risk(issue_type)` | Summarizes collection-process procedures for issues such as levies, liens, and trust fund recovery penalty |
| `recommend_records_to_gather(issue_type)` | Returns source-backed record/document checklist guidance |

Phase 2C adds guarded LangGraph routing for IRS procedural questions only and formats results through a deterministic synthesis layer that requires `irm_reference` citations and a no tax/legal advice disclaimer.

**Workflow Tools**

`tools/workflows.py` now includes Phase 4A IRS notice review, Phase 4B duplicate payment review, Phase 4C vendor verification, and Phase 4D payroll tax review workflow builders. Other workflow tools remain stubbed until their source findings and case contracts are ready.

| Tool | Status |
|---|---|
| `create_irs_notice_review(extraction_payload)` | Complete — deterministic reviewer workflow from extracted notice fields |
| `create_duplicate_payment_review(findings)` | Complete — deterministic reviewer workflow from duplicate-payment finding evidence |
| `create_vendor_verification_workflow(vendor_risk_payload, entity_relationship_payload)` | Complete — deterministic reviewer workflow from vendor risk evidence |
| `create_payroll_tax_review(procedural_payload, issue_type)` | Complete — deterministic reviewer workflow from IRS payroll tax procedural evidence |
| `create_missing_document_request(alert_id)` | Stubbed |

**Relational Readiness Tools**

| Tool | Status |
|---|---|
| `audit_relational_readiness(data_sources)` | Complete — deterministic Phase 5 readiness audit over agent-visible payload contracts |
| `build_relational_contract_adoption_report(data_sources)` | Complete — endpoint-level Laravel/API payload remediation report |
| `build_relational_graph_projection(data_sources)` | Complete — read-only graph-shaped projection gated by Phase 5 readiness |

**Tests**

- `tests/test_duplicate_payments.py` — 14 unit tests covering detection, edge cases, confidence scoring
- `tests/test_vendor_concentration.py` — 11 unit tests covering thresholds, severity, metadata
- `tests/test_irs_answer_quality.py` — answer-quality fixtures for citations, disclaimers, empty-result behavior, and exact section lookup
- `mcp_servers/brevix_intelligence/tests/test_irs_knowledge.py` — IRS MCP adapter delegation tests
- `tests/test_irs_notice_extraction.py` and `tests/test_irs_notice_workflow.py` — pasted notice routing, answer synthesis, and Phase 4A workflow contract tests
- `tests/test_duplicate_payment_workflow.py` — Phase 4B duplicate payment workflow contract tests
- `tests/test_vendor_verification_workflow.py` — Phase 4C vendor verification workflow contract tests
- `tests/test_payroll_tax_workflow.py` — Phase 4D payroll tax review workflow contract tests
- `tests/test_relational_readiness.py` — Phase 5A relational readiness audit contract tests
- `tests/test_relational_contracts.py` — Phase 5B stable identifier and relationship contract tests
- `tests/test_relational_contract_smoke.py` — Phase 5C Laravel payload contract gate tests
- `tests/test_relational_contract_adoption.py` — Phase 5D endpoint-level contract adoption report tests
- `tests/test_relational_graph_projection.py` — Phase 5E relational graph projection tests
- `tests/test_router.py` — includes Phase 5F graph-intelligence routing and integration tests
- `mcp_servers/brevix_intelligence/tests/test_relational_readiness.py` — MCP relational readiness delegation test
- `tests/fixtures/transactions.json` — Seeded fraud scenarios (duplicates, concentration, dormant vendor, missing approvals)

Latest full agent test run: 550 Python tests passing locally.

---

### Graph Integration (`app/graph.py`)

The five tools are wired directly into the existing LangGraph `fraud_analyzer_node`. No separate process or MCP server is required.

**How it works:**

1. When a user query routes to `fraud_pattern_search`, the graph makes one `transaction_lookup` call fetching up to 500 transactions over the trailing 12 months
2. All five analysis tools run in memory on that single result
3. Findings are merged with existing risk signals (risk summary, vendor risk, reconciliation risk, etc.)
4. The existing LLM explanation layer summarizes everything in plain English

**Router terms added:** `dormant`, `burn`, `control weakness`, `approval`, `missing approval`, `missing document`, `segregation`

---

### Laravel API (`brevixai-api` — `AgentToolController.php`)

Two changes made to the `/api/internal/agent-tools/company/{id}/transactions` endpoint:

| Change | Before | After |
|---|---|---|
| Transaction limit | 20 | 500 |
| Fields returned | `id`, `date`, `vendor`, `amount`, `type`, `category`, `status` | + `memo`, `invoice_number` |

`memo` and `invoice_number` were already in the `all_transactions` database view — they just weren't being selected or returned.

---

## What Has Not Been Built

### Control Weaknesses — Approval and Documentation Tracking

The `control_weaknesses` tool checks for `approved_by` and `document_id` on transactions. Neither field exists in the current schema:

- `approved_by` exists only on the `agent_action_approvals` table, not on transactions
- `document_id` does not exist anywhere

**What's needed:** A decision on whether to track approvals per transaction in the database. Options:
- Add an `approved_by` column to the transactions table (or view)
- Join `agent_action_approvals` to the transaction query in the Laravel API
- Accept that this check is out of scope until the data model supports it

Until then, the control weaknesses tool will not flag missing approvals or missing documentation — it can only detect approval concentration (single approver dominance) when approval data becomes available.

---

### Phase 2D — IRM Corpus Coverage and Lexical Ranking (Complete)

Full validation results are in `docs/mcp/PHASE_2C_VALIDATION.md` (Phase 2D results section).

Changes shipped in Phase 2D:

- **Deterministic IRM ranking** in `IrmKnowledgeService::searchSections()`: replaced `orderBy('irm_reference')` with a computed relevance score using `CASE WHEN` SQL expressions. Signals in descending weight: issue-family prefix boost (+60), exact reference match (+100), per-term title match (+10 each), per-term body match (+3 each). Prefix boost maps query phrases (levy/CP504/LT11, lien, trust fund/TFRP, CP2000) to the correct procedural IRM part prefixes (`5.11.*`, `5.12.*`, `5.7.*`, `4.19.*`, etc.).
- **Corpus coverage command**: `php artisan irm:coverage-check` verifies all required procedural prefixes (`4.19`, `5.7`, `5.11`, `5.12`, `5.14`, `5.19`, `8.25`, `20.1`) are present in the seeded corpus. `--json` flag for automation.
- **Relevance tests**: 7 new `IrmKnowledgeToolTest` tests assert that ranked top results land in the correct IRM prefix range for levy, CP504, LT11, CP2000, TFRP, and exact-reference lookups (19 Laravel tests total, all passing).
- **Smoke script prefix assertions**: `scripts/smoke_irs_knowledge.py` now asserts the top returned `irm_reference` matches the expected prefix group per case, not only that a result was returned.

Local smoke result (2026-05-31, fully seeded corpus, `reports/smoke_irs_knowledge_phase2d.json`):

| Case | Status | Top section |
|---|---|---|
| `levy_notice` | PASS | `5.11.*` |
| `cp504` | PASS | `5.11.*` |
| `lt11` | PASS | `5.11.*` |
| `cp2000` | PASS | `4.19.*` |
| `trust_fund_recovery_penalty` | PASS | `5.7.*` |
| `unknown_notice_code` | PASS | empty, safe response |

Deterministic ranking passed against the full local corpus. No `tsvector` or embeddings pass is needed before Phase 3.

---

### Phase 3 — IRS Notice Extraction (Complete)

Completed on 2026-05-31.

**What shipped:**

- Laravel-owned `POST /api/internal/agent-tools/irs/notice/extract` chains `IrsTaxNoticeService` extraction into `IrmKnowledgeService` source-backed IRM lookup.
- Python `LaravelToolClient.irs_notice_extract()` calls the new endpoint.
- MCP `extract_irs_notice_tool` exposes pasted notice extraction.
- LangGraph IRS routing sends long pasted notices or explicit notice-submission phrases to `irs_notice_extract`; short code questions still use `irs_notice_type`.
- Deterministic answer synthesis includes notice type, risk level, deadline, required action, amount at issue, IRM references, and disclaimer.

Still out of scope: PDF parsing/OCR, notice file uploads, notice persistence, and batch extraction.

See `docs/mcp/PHASE_3_PLAN.md` for the completed implementation plan.

---

### Phase 4A — IRS Notice Review Workflow (Complete)

Completed on 2026-05-31.

**Goal:** Convert extracted IRS notice fields into a reviewer-facing workflow without creating cases, alerts, correspondence, or IRS submissions.

**What shipped:**

- `app/irs_notice_workflow.py` builds deterministic workflows from notice extraction payloads.
- Workflow output includes `workflow_type`, notice family, review priority, deadline urgency, evidence requests, evidence gaps, next steps, escalation criteria, source IRM references, readiness summary, and a non-mutating `prepare_irs_notice_review` recommended action.
- LangGraph attaches workflow data to IRS notice extraction runs through `recommended_workflow`, `next_best_action`, `evidence_gaps`, `scope_limitations`, and `readiness_summary`.
- IRS notice extraction answers now include workflow next steps, evidence to gather, and escalation criteria.
- MCP `create_irs_notice_review_tool` exposes the workflow builder for standalone clients.
- `datasets/irs_answer_quality_fixtures.json` includes a pasted CP504 notice fixture that verifies extraction routing and workflow creation.

**Remaining Phase 4 work:** guided workflow for missing document requests.

---

### Phase 4B — Duplicate Payment Review Workflow (Complete)

Completed on 2026-05-31.

**Goal:** Convert existing deterministic duplicate-payment findings into a reviewer-facing workflow without looking up extra transaction detail or creating records.

**What shipped:**

- `app/duplicate_payment_workflow.py` builds deterministic workflows from converted duplicate-payment findings.
- Workflow output includes `workflow_type`, review priority, duplicate count, vendors, transaction IDs, total amount exposure, evidence requests, evidence gaps, next steps, escalation criteria, readiness summary, and a non-mutating `review_duplicate_payment_evidence` recommended action.
- LangGraph attaches workflow data to fraud-analysis runs with duplicate-payment findings through `recommended_workflow`, `next_best_action`, `evidence_gaps`, `scope_limitations`, and `readiness_summary`.
- The action gate now prefers workflow-specific `next_best_action` for non-IRS fraud flows before falling back to generic `review_findings`.
- MCP `create_duplicate_payment_review_tool` exposes the workflow builder for standalone clients.

See `docs/mcp/PHASE_4B_PLAN.md` for the completed implementation plan.

---

### Phase 4C — Vendor Verification Workflow (Complete)

Completed on 2026-06-03.

**Goal:** Convert existing deterministic vendor risk payloads into a reviewer-facing workflow without retrieving vendor records or creating records.

**What shipped:**

- `app/vendor_verification_workflow.py` builds deterministic workflows from vendor risk payloads, with optional entity relationship risk reinforcement.
- Workflow output includes `workflow_type`, review priority, vendor count, vendor names/IDs, highest vendor risk score, triggered rules, supporting evidence IDs, evidence requests, evidence gaps, next steps, escalation criteria, readiness summary, and a non-mutating `review_vendor_verification_evidence` recommended action.
- LangGraph attaches workflow data to fraud-analysis runs with elevated vendor risk through `recommended_workflow`, `next_best_action`, `evidence_gaps`, `scope_limitations`, and `readiness_summary`.
- When multiple workflows are present, the graph exposes the highest-priority workflow as primary while retaining each workflow under `tool_results`.
- MCP `create_vendor_verification_workflow_tool` exposes the workflow builder for standalone clients.

See `docs/mcp/PHASE_4C_PLAN.md` for the completed implementation plan.

---

### Phase 4D — Payroll Tax Review Workflow (Complete)

Completed on 2026-06-04.

**Goal:** Convert existing IRS payroll tax procedural payloads into a reviewer-facing workflow without creating cases, alerts, correspondence, IRS submissions, payroll changes, or payment changes.

**What shipped:**

- `app/payroll_tax_workflow.py` builds deterministic workflows from IRS collection-risk or records-checklist payloads for payroll tax, employment tax, Form 941, EFTPS deposit, and trust fund recovery penalty issues.
- Workflow output includes `workflow_type`, payroll issue type, review priority, responsible-person review flag, source IRM references, recommended records, tax periods, evidence requests, evidence gaps, next steps, escalation criteria, readiness summary, and a non-mutating `review_payroll_tax_evidence` recommended action.
- LangGraph attaches workflow data to IRS payroll/TFRP procedural runs through `recommended_workflow`, `next_best_action`, `evidence_gaps`, `scope_limitations`, and `readiness_summary`.
- IRS procedural answers for payroll/TFRP requests now include workflow next steps, evidence to gather, and escalation criteria while preserving source-backed IRM references and the no-advice disclaimer.
- MCP `create_payroll_tax_review_tool` exposes the workflow builder for standalone clients.

See `docs/mcp/PHASE_4D_PLAN.md` for the completed implementation plan.

---

### Phase 5 — Graph Intelligence

Not started. Deliberately deferred until relational data is clean and stable.

**Planned entities:** vendors, employees, bank accounts, payments, approvers, documents.

### Phase 5A — Relational Readiness Audit (Complete)

Completed on 2026-06-04.

**Goal:** Audit whether agent-visible payloads are ready for Phase 5 graph intelligence before building graph infrastructure.

**What shipped:**

- `app/relational_readiness.py` audits entity contracts for vendors, employees, bank accounts, payments, approvers, documents, and company users.
- Relationship readiness is checked for payment-to-vendor, employee-approved-payment, payment-to-document, vendor-to-bank-account, employee-to-vendor, and vendor-to-vendor relationships.
- The audit reports `phase_5_ready`, `readiness_score`, entity/relationship contract statuses, critical blockers, recommended next steps, readiness summary, scope limitations, and a non-mutating `prepare_relational_data_contracts` recommended action.
- LangGraph routes Phase 5 readiness questions to the deterministic audit instead of fraud analysis.
- MCP `audit_relational_readiness_tool` exposes the audit builder for standalone clients.

**Current result:** Phase 5 graph intelligence should remain blocked until stable identifiers are available for production payload contracts, especially approval, document, bank-account, employee, and vendor/payment relationship anchors.

---

### Phase 5B — Relational Payload Contract (Complete)

Completed on 2026-06-04.

**Goal:** Codify the stable identifiers and relationship anchors required before Phase 5 graph intelligence can begin.

**What shipped:**

- `docs/mcp/PHASE_5B_RELATIONAL_CONTRACT.md` defines required payload fields for payments, vendors, employees, bank accounts, approvers, documents, company users, and core relationships.
- The readiness audit now treats payment payloads with only `id`, `date`, and `amount` as partial, not graph-ready. Graph-ready payment payloads must include stable anchors such as `company_id`, `vendor_id`, `approved_by`, `document_id`, `bank_account_id`, and `company_user_id`.
- `tests/test_relational_contracts.py` verifies complete payloads pass, missing stable identifiers block Phase 5, vendor names alone are insufficient, and entity relationship evidence requires stable endpoints.

**Current result:** Phase 5 graph intelligence remains blocked until Laravel/API payloads satisfy the Phase 5B contract against production-shaped data.

---

### Phase 5C — Payload Contract Gate (Complete)

Completed on 2026-06-04.

**Goal:** Make the Phase 5B relational payload contract executable against real Laravel agent-tool payloads.

**What shipped:**

- `scripts/smoke_relational_contract.py` calls Laravel `company_context`, `transaction_lookup`, `vendor_risk`, and `entity_relationship_risk`, then runs the Phase 5A readiness audit over those payloads.
- The smoke gate exits nonzero unless all required calls succeed and `phase_5_ready` is true.
- `--allow-blocked` supports diagnostic reports while the contract is still blocked.
- `--json-output` writes detailed blocker reports for API-side follow-up.

**Current result:** This is the operational gate to run after Laravel/API payload changes. Phase 5 graph intelligence remains blocked until this smoke passes without `--allow-blocked`.

---

### Phase 5D — Contract Adoption Report (Complete)

Completed on 2026-06-04.

**Goal:** Turn Phase 5 readiness blockers into endpoint-level Laravel/API payload remediation tasks.

**What shipped:**

- `app/relational_contract_adoption.py` maps readiness blockers and smoke tool failures to the affected agent-tool payloads.
- `scripts/smoke_relational_contract.py` now includes `adoption_report` in JSON output and prints API remediation tasks.
- MCP `build_relational_contract_adoption_report_tool` exposes the same read-only report builder for standalone clients.
- The report returns endpoint requirements, missing fields, affected contracts, remediation actions, acceptance checks, scope limitations, and a non-mutating `update_laravel_relational_payloads` recommended action.

**Current result:** Laravel/API payload work can now use the smoke output as a concrete work order. Phase 5 graph intelligence remains blocked until the payload smoke passes without `--allow-blocked`.

---

### Phase 5E — Relational Graph Projection (Complete)

Completed on 2026-06-04.

**Goal:** Build the first read-only graph-shaped projection from Phase 5-ready payloads without adding graph infrastructure.

**What shipped:**

- `app/relational_graph_projection.py` builds deterministic graph nodes, edges, relationship insights, graph summaries, and a non-mutating `review_relational_graph_projection` recommended action.
- The projection is gated by the Phase 5 readiness audit. If `phase_5_ready` is false, it returns `status=blocked` with no nodes or edges.
- LangGraph attaches `tool_results["relational_graph_projection"]` only when the relational readiness audit passes.
- MCP `build_relational_graph_projection_tool` exposes the read-only projection builder for standalone clients.

**Current result:** The repo now has a PostgreSQL-first, payload-only graph projection contract ready for graph-ready payloads. Production graph intelligence still depends on Laravel payloads passing the Phase 5C smoke gate without `--allow-blocked`.

---

### Phase 5F — Production Graph Intelligence Activation (Complete)

Completed on 2026-06-04.

**Goal:** Promote the read-only relational graph projection into an explicit user-facing graph-intelligence path.

**What shipped:**

- Added a dedicated `relational_graph_intelligence` intent for graph and relationship prompts.
- Added routing for prompts about entity graphs, related vendors, shared bank accounts, employee/vendor overlap, approval relationships, and relationship insights.
- Added a graph-intelligence analysis branch that runs the Phase 5 readiness gate before projection.
- Blocked payloads return no graph nodes or edges and keep the `prepare_relational_data_contracts` recommended action.
- Ready payloads return `tool_results["relational_graph_projection"]`, first-class `relationship_insights`, and a non-mutating `review_relational_graph_projection` recommended action.
- Deterministic graph-intelligence answer synthesis states projection status and the no-write/no-alert safety boundary.

**Current result:** Graph-intelligence prompts now have a dedicated read-only path. The path is production-usable only when the Laravel smoke gate has already validated graph-ready payloads.

---

### Feedback Loop (Future)

The intelligence loop is designed to support:

1. User marks a finding as useful or not useful
2. Feedback is stored
3. Thresholds and confidence scoring improve over time

This is not yet built. No feedback storage or threshold tuning mechanism exists.

---

### `server.py` — MCP Stdio Server

`mcp_servers/brevix_intelligence/server.py` exists and is functional as a standalone MCP server (stdio transport). It is not currently used — the analysis tools are called directly from the graph instead. It is available if a future use case requires exposing these tools to a different client (e.g., a separate agent, a desktop tool, or a multi-server architecture).

The `mcp` Python package is now a project dependency, and CI imports the server and verifies that all Phase 1 MCP tools are registered.

---

## Configurable Thresholds

All detection thresholds are environment variables with sensible defaults. None require code changes to tune.

| Variable | Default | Controls |
|---|---|---|
| `MCP_DUPLICATE_AMOUNT_TOLERANCE` | `0.01` (1%) | How close two amounts must be to flag as duplicate |
| `MCP_DUPLICATE_DATE_WINDOW_DAYS` | `30` | How many days apart two payments can be and still be flagged |
| `MCP_VENDOR_CONCENTRATION_THRESHOLD` | `0.30` (30%) | Minimum share of total spend to flag a vendor |
| `MCP_DORMANT_VENDOR_DAYS` | `90` | Inactivity gap required before reactivation is flagged |
| `MCP_CONTROL_WEAKNESS_MIN_AMOUNT` | `1000.00` | Minimum transaction amount checked for approval/doc weakness |
| `MCP_CONTROL_WEAKNESS_APPROVER_DOMINANCE` | `0.80` (80%) | Share of approvals by one person before flagging concentration |
| `MCP_MAX_TRANSACTIONS` | `500` | Maximum transactions fetched per intelligence analysis run |
