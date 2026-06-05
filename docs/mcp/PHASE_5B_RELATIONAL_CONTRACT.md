# Phase 5B — Relational Payload Contract

Date: 2026-06-04

Status: Complete

## Goal

Codify the stable payload contracts required before Phase 5 graph intelligence can begin.

This phase adds contract documentation and tests only. It does not create graph infrastructure, database migrations, Laravel endpoints, alerts, cases, or data writes.

## Core Rule

Graph intelligence may not depend on display names, inferred relationships, or optional free-text fields. Every graph entity and relationship must have stable identifiers in the payloads visible to the agent.

## Required Entity Contracts

### Payments

Source: `transaction_lookup.transactions[]`

Required fields:
- `id`
- `company_id`
- `vendor_id`
- `amount`
- `date`
- `approved_by`
- `document_id`
- `bank_account_id`
- `company_user_id`

Notes:
- `id` is treated as the payment/transaction identifier until a dedicated `payment_id` exists.
- `vendor` may remain as display text, but it must not be the only vendor anchor.
- `approved_by` must be a stable approver or employee/user identifier.
- `document_id` must link to the evidence/document record used for payment support.
- `bank_account_id` must identify the payment routing account, not only a masked account label.

### Vendors

Sources:
- `transaction_lookup.transactions[]`
- `vendor_risk`
- `entity_relationship_risk`

Required fields:
- `vendor_id`
- `vendor_name`

Notes:
- `vendor_name` is display text only.
- Payment-to-vendor relationships require `transaction.vendor_id`.

### Employees

Source: `entity_relationship_risk.supporting_evidence[]`

Required fields:
- `employee_id`

Notes:
- Employee relationship edges must not rely on names or email strings alone.

### Bank Accounts

Sources:
- `transaction_lookup.transactions[]`
- `entity_relationship_risk.supporting_evidence[]`

Required fields:
- `bank_account_id`

Notes:
- `account_id` can be accepted as an equivalent source field only if it is stable and scoped.
- `account_last4` is display context only and cannot be used as the graph key.

### Approvers

Source: `transaction_lookup.transactions[]`

Required fields:
- `approved_by`

Notes:
- `approved_by` should resolve to a stable employee, user, or company-user identifier.

### Documents

Sources:
- `transaction_lookup.transactions[]`
- document evidence payloads

Required fields:
- `document_id`

Notes:
- `document_id` must link payments to uploaded invoices, statements, approvals, notices, or other source evidence.

### Company Users

Sources:
- `company_context`
- `transaction_lookup.transactions[]`

Required fields:
- `company_id`
- `company_user_id` or `user_id`

## Required Relationship Contracts

### Payment To Vendor

Required fields:
- `payment.id`
- `payment.vendor_id`

### Employee Approved Payment

Required fields:
- `payment.id`
- `payment.approved_by`

### Payment To Document

Required fields:
- `payment.id`
- `payment.document_id`

### Vendor Uses Bank Account

Required fields:
- `vendor_id`
- `bank_account_id`

## Optional Relationship Contracts

These relationships are useful for richer graph intelligence but should not block initial Phase 5 readiness if the core contracts above are present.

### Employee Shares Address With Vendor

Required fields when present:
- `employee_id`
- `vendor_id`
- `relationship_type`

### Vendor Related To Vendor

Required fields when present:
- `vendor_id`
- `related_vendor_id`

## Phase 5B Acceptance Criteria

Phase 5B is complete when:
- A contract document defines required stable identifiers.
- Contract tests fail if any required payment identifier is absent.
- Contract tests fail if vendor relationships rely only on vendor display names.
- Contract tests fail if approval or document identifiers are absent.
- Contract tests prove a complete payload passes the Phase 5 readiness audit.

## Next Step

After Phase 5B, the next development phase should resolve the data-source gaps in Laravel/API payloads. Phase 5 graph intelligence should remain blocked until those payload contracts pass against production-shaped data.
