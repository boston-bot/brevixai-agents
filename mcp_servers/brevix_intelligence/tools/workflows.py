"""Workflow MCP tools — Phase 4 (not yet implemented).

These tools will convert alerts into guided investigations with step-by-step
evidence requests, escalation paths, and remediation workflows.

See the architecture plan (docs/brevix_mcp_architecture_plan.md) for full design.
"""

from __future__ import annotations


def create_duplicate_payment_review(alert_id: str) -> dict:
    raise NotImplementedError("Workflow tools are planned for Phase 4.")


def create_vendor_verification_workflow(vendor_id: str) -> dict:
    raise NotImplementedError("Workflow tools are planned for Phase 4.")


def create_payroll_tax_review(company_id: str) -> dict:
    raise NotImplementedError("Workflow tools are planned for Phase 4.")


def create_missing_document_request(alert_id: str) -> dict:
    raise NotImplementedError("Workflow tools are planned for Phase 4.")
