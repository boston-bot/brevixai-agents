# Brevix AI — MCP Specialist Services Architecture Plan

## Overview

This document defines the initial implementation plan for introducing MCP (Model Context Protocol) specialist services into the `brevixai-agents` codebase.

The goal is to create an internal intelligence layer that enhances:

- fraud detection,
- financial anomaly monitoring,
- forensic accounting workflows,
- IRS procedural intelligence,
- document extraction,
- and investigation orchestration.

This architecture is designed specifically for Brevix AI's existing infrastructure:

- AWS EC2
- Laravel API (`brevixai-api`)
- LangGraph / LangChain (`brevixai-agents`)
- RDS PostgreSQL
- Existing orchestration framework

---

# Core Strategic Direction

Brevix AI should NOT attempt to become:

- an accounting suite,
- a bookkeeping platform,
- a CPA replacement,
- or an ERP.

Brevix AI should become:

> An AI-powered financial intelligence and continuous monitoring layer for small businesses.

The MCP layer exists to provide:

- deterministic fraud analysis,
- domain-specific intelligence,
- structured evidence retrieval,
- workflow generation,
- and explainable AI outputs.

---

# Initial Architecture

## Current Infrastructure

```text
AWS
│
├── EC2: brevixai-api
│   └── Laravel backend
│
├── EC2: brevixai-agents
│   └── LangGraph + LangChain
│   └── MCP server(s)
│
└── RDS PostgreSQL
    └── customer data
    └── transaction data
    └── findings
    └── documents
    └── IRS knowledge data
```

---

# Phase 1 Goal

Build ONE internal MCP server first.

DO NOT build multiple distributed MCP services initially.

The first MCP server should expose reusable intelligence tools to LangGraph agents.

Recommended name:

```text
brevix_intelligence
```

---

# Recommended Repository Structure

Inside `brevixai-agents`:

```text
brevixai-agents/
│
├── app/
│
├── mcp_servers/
│   └── brevix_intelligence/
│       ├── server.py
│       ├── config.py
│       ├── database.py
│       ├── auth.py
│       │
│       ├── tools/
│       │   ├── duplicate_payments.py
│       │   ├── vendor_concentration.py
│       │   ├── dormant_vendor.py
│       │   ├── cash_burn.py
│       │   ├── control_weaknesses.py
│       │   ├── irs_knowledge.py
│       │   └── workflows.py
│       │
│       ├── schemas/
│       │   ├── findings.py
│       │   └── evidence.py
│       │
│       └── tests/
│           ├── test_duplicate_payments.py
│           ├── test_vendor_concentration.py
│           └── fixtures/
│
└── requirements.txt
```

---

# Critical Design Principles

## 1. MCP Servers Must Be Read-Only Initially

The MCP layer must NEVER:

- modify accounting records,
- execute arbitrary SQL,
- or perform destructive operations.

All MCP tools should be:

- deterministic,
- scoped,
- auditable,
- evidence-based,
- and read-only.

---

## 2. LLMs Must NOT Perform Calculations

LLMs should ONLY:

- explain findings,
- summarize findings,
- prioritize findings,
- generate workflows,
- create narratives.

All calculations and fraud detection logic should be deterministic Python logic.

---

## 3. Every Finding Must Include Evidence

Every tool must return:

- risk type,
- severity,
- confidence score,
- evidence,
- and recommended next steps.

Example:

```json
{
  "risk_type": "duplicate_payment",
  "severity": "medium",
  "confidence": 0.82,
  "summary": "Two similar payments detected.",
  "evidence": [
    {
      "transaction_id": "txn_123",
      "vendor": "ABC Supply",
      "amount": 1840.22,
      "date": "2026-05-01"
    }
  ],
  "recommended_next_steps": [
    "Verify invoice documentation.",
    "Check for void/refund activity."
  ]
}
```

---

# Phase 1 — Fraud Intelligence MCP

## Objective

Build deterministic financial analysis tools.

These tools should identify:

- duplicate payments,
- suspicious vendor activity,
- cash burn anomalies,
- concentration risks,
- dormant vendor reactivation,
- control weaknesses.

---

# Initial MCP Tools

## Tool 1 — Duplicate Payments

File:

```text
tools/duplicate_payments.py
```

Purpose:

Detect likely duplicate vendor payments using:

- vendor similarity,
- amount similarity,
- invoice similarity,
- date proximity,
- memo similarity.

Tool Signature:

```python
detect_duplicate_payments(
    company_id: str,
    start_date: str,
    end_date: str
)
```

---

## Tool 2 — Vendor Concentration

File:

```text
tools/vendor_concentration.py
```

Purpose:

Identify vendors receiving unusually high percentages of company spend.

Tool Signature:

```python
analyze_vendor_concentration(
    company_id: str,
    start_date: str,
    end_date: str
)
```

---

## Tool 3 — Dormant Vendor Reactivation

File:

```text
tools/dormant_vendor.py
```

Purpose:

Identify vendors with no activity for long periods that suddenly become active again.

Tool Signature:

```python
detect_dormant_vendor_reactivation(
    company_id: str
)
```

---

## Tool 4 — Cash Burn Analysis

File:

```text
tools/cash_burn.py
```

Purpose:

Analyze:

- cash outflow acceleration,
- runway deterioration,
- unusual operational spend increases.

Tool Signature:

```python
calculate_cash_burn(
    company_id: str
)
```

---

## Tool 5 — Control Weaknesses

File:

```text
tools/control_weaknesses.py
```

Purpose:

Identify operational weaknesses such as:

- missing approvals,
- missing documentation,
- approval concentration,
- segregation of duties concerns.

Tool Signature:

```python
summarize_control_weaknesses(
    company_id: str
)
```

---

# Phase 2 — IRS Knowledge MCP

## Objective

Create structured IRS procedural intelligence.

This system does NOT provide legal advice.

It provides:

- procedural guidance,
- notice interpretation,
- records recommendations,
- collection process intelligence,
- and risk explanations.

---

# IRS Data Sources

Potential ingestion targets:

- IRM (Internal Revenue Manual)
- IRS notices
- IRS FAQs
- publicly available procedural guidance

---

# Recommended IRS MCP Tools

```python
search_irm(topic: str)

explain_notice_type(notice_code: str)

summarize_collection_risk(issue_type: str)

recommend_records_to_gather(issue_type: str)
```

---

# IRS Knowledge Architecture

Recommended PostgreSQL tables:

```text
irs_documents
irs_chunks
irs_embeddings
irs_topics
irs_notice_types
irs_risk_categories
```

---

# Phase 3 — Document Extraction MCP

## Objective

Extract structured financial data from uploaded documents.

---

# Supported Documents

- bank statements,
- checks,
- invoices,
- payroll reports,
- IRS notices,
- receipts,
- vendor forms,
- financial PDFs.

---

# Recommended Tools

```python
extract_bank_statement_transactions(document_id)

extract_invoice_fields(document_id)

extract_check_payee_and_amount(document_id)

extract_irs_notice_fields(document_id)
```

---

# Suggested Extraction Stack

Recommended technologies:

- OCR:
  - Tesseract
  - AWS Textract

- PDF parsing:
  - pdfplumber
  - pymupdf

- Table extraction:
  - camelot
  - tabula-py

---

# Phase 4 — Workflow MCP

## Objective

Convert alerts into guided investigations.

Instead of:

> "Possible duplicate payment detected."

Brevix should produce:

- investigation steps,
- evidence requests,
- escalation paths,
- and remediation workflows.

---

# Example Workflow Tools

```python
create_duplicate_payment_review(findings)

create_vendor_verification_workflow(vendor_risk_payload, entity_relationship_payload)

create_payroll_tax_review(procedural_payload, issue_type)

create_missing_document_request(alert_id)

create_irs_notice_review(extraction_payload)
```

Phase 4A implements `create_irs_notice_review(extraction_payload)` as the first workflow tool. It consumes the Phase 3 IRS notice extraction payload and returns reviewer-facing evidence requests, next steps, escalation criteria, deadline urgency, and a non-mutating recommended action.

Phase 4B implements `create_duplicate_payment_review(findings)`. It consumes deterministic duplicate-payment findings and returns reviewer-facing evidence requests, next steps, escalation criteria, vendor and transaction summaries, amount exposure, and a non-mutating recommended action.

Phase 4C implements `create_vendor_verification_workflow(vendor_risk_payload, entity_relationship_payload)`. It consumes deterministic vendor risk data with optional entity relationship reinforcement and returns reviewer-facing evidence requests, next steps, escalation criteria, vendor summaries, supporting evidence IDs, and a non-mutating recommended action.

Phase 4D implements `create_payroll_tax_review(procedural_payload, issue_type)`. It consumes source-backed IRS procedural payloads for payroll tax, employment tax, Form 941, EFTPS deposit, and trust fund recovery penalty issues. It returns reviewer-facing evidence requests, next steps, escalation criteria, source IRM references, responsible-person review signals, and a non-mutating recommended action.

---

# Phase 5 — Graph Intelligence MCP

## IMPORTANT

Do NOT implement graph intelligence first.

Graph intelligence depends on:

- clean entities,
- normalized data,
- stable identifiers,
- consistent relationships.

---

# Recommended Initial Graph Entities

```text
vendors
employees
bank_accounts
payments
approvers
documents
company_users
```

---

# Potential Future Relationships

```text
employee -> approved -> payment

vendor -> uses -> bank_account

employee -> shares -> address_with_vendor

vendor -> related_to -> another_vendor
```

---

# Graph Technology Recommendation

## Initial Recommendation

Stay inside PostgreSQL first.

Possible future upgrades:

- Neo4j
- Memgraph
- Apache AGE

Do NOT add graph infrastructure until relational intelligence is functioning well.

Phase 5A implements `audit_relational_readiness(data_sources)` as the readiness gate before graph intelligence. It audits agent-visible payload contracts for stable entity identifiers and relationship anchors, reports blockers, and returns a non-mutating `prepare_relational_data_contracts` recommended action. It does not create graph infrastructure or write relationships.

Phase 5B codifies the relational payload contract in `docs/mcp/PHASE_5B_RELATIONAL_CONTRACT.md` and adds contract tests. Payment payloads are graph-ready only when stable identifiers are present for company, vendor, approver, document, bank account, company user, date, amount, and transaction/payment id. Vendor display names and free-text relationship hints are not sufficient graph anchors.

Phase 5C adds `scripts/smoke_relational_contract.py` as the executable payload gate against Laravel agent-tool responses. Phase 5 graph intelligence remains blocked until this smoke passes without `--allow-blocked`.

Phase 5D adds `app/relational_contract_adoption.py` and `build_relational_contract_adoption_report_tool` to convert readiness blockers and smoke tool failures into endpoint-level Laravel/API remediation tasks. This keeps the next work item focused on stable payload adoption; graph intelligence remains blocked until the payload smoke passes without `--allow-blocked`.

Phase 5E adds `app/relational_graph_projection.py` and `build_relational_graph_projection_tool` as the first PostgreSQL-first, payload-only graph projection. It is strictly gated by the Phase 5 readiness audit: blocked payloads return no nodes or edges, and ready payloads produce deterministic nodes, edges, relationship insights, and a non-mutating review action. No graph database or graph infrastructure is created.

Phase 5F promotes the projection into a dedicated `relational_graph_intelligence` LangGraph path for relationship prompts such as entity graph, related vendors, shared bank accounts, employee/vendor overlap, and approval relationships. The path runs the readiness gate first, blocks with no nodes or edges when payload contracts fail, and surfaces first-class `relationship_insights` plus a non-mutating review action when ready.

---

# LangGraph Integration

The LangGraph orchestration layer should consume MCP tools using:

```python
langchain-mcp-adapters
```

The orchestration flow should resemble:

```text
User Request
    ↓
LangGraph Agent
    ↓
MCP Tool Call
    ↓
Deterministic Findings
    ↓
LLM Explanation Layer
    ↓
Structured User Output
```

---

# Security Requirements

## Required Controls

### Company Isolation

Every tool must require:

```python
company_id
```

No cross-company access is permitted.

---

### Logging

All MCP calls should be logged with:

- timestamp,
- user ID,
- company ID,
- tool name,
- execution time,
- result status.

---

### No Arbitrary SQL

MCP tools must NEVER expose unrestricted SQL execution.

Only scoped, deterministic queries are allowed.

---

# AWS Deployment Strategy

## Phase 1 Deployment

Deploy MCP server locally on the same EC2 instance as:

```text
brevixai-agents
```

Transport recommendation:

```text
stdio
```

Do NOT over-engineer initial deployment.

---

# Future Deployment Strategy

Possible future architecture:

```text
brevix_intelligence_mcp
irs_knowledge_mcp
document_extraction_mcp
workflow_mcp
graph_intelligence_mcp
```

Potential future transport:

```text
HTTP / Streamable HTTP
```

---

# Suggested Initial Sprint

## Sprint: Brevix Intelligence MCP v1

### Objectives

1. Create initial MCP server.
2. Add read-only PostgreSQL connection.
3. Add authentication middleware.
4. Build deterministic fraud tools.
5. Integrate LangGraph MCP adapters.
6. Add seeded fraud test fixtures.
7. Return structured JSON findings.

---

# Acceptance Criteria

## Infrastructure

- MCP server boots successfully.
- LangGraph can access MCP tools.
- PostgreSQL connectivity functions.
- Company isolation enforced.

---

## Fraud Tools

- Duplicate payment detection functions.
- Vendor concentration analysis functions.
- Dormant vendor detection functions.
- Cash burn analysis functions.

---

## Outputs

- All findings include evidence.
- Findings include confidence scoring.
- Findings include recommended next steps.
- Findings are JSON structured.

---

# Long-Term Strategic Direction

Brevix AI should evolve into:

> A Financial Security Operations Center (FinSecOps) platform for small businesses.

Core value:

- continuous monitoring,
- fraud intelligence,
- operational risk awareness,
- IRS procedural intelligence,
- and guided investigations.

The MCP layer becomes the specialized intelligence infrastructure powering that ecosystem.
