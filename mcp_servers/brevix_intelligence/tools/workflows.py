"""Workflow MCP tools.

These tools will convert alerts into guided investigations with step-by-step
evidence requests, escalation paths, and remediation workflows.

See the architecture plan (docs/brevix_mcp_architecture_plan.md) for full design.
"""

from __future__ import annotations

from typing import Any

from app.duplicate_payment_workflow import build_duplicate_payment_review_workflow
from app.irs_notice_workflow import build_irs_notice_workflow
from app.payroll_tax_workflow import build_payroll_tax_review_workflow
from app.vendor_verification_workflow import build_vendor_verification_workflow


def create_irs_notice_review(extraction_payload: dict[str, Any]) -> dict[str, Any]:
    """Create a guided IRS notice review workflow from extracted notice fields."""
    return build_irs_notice_workflow(extraction_payload)


def create_duplicate_payment_review(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a guided duplicate payment review workflow from finding evidence."""
    return build_duplicate_payment_review_workflow(findings)


def create_vendor_verification_workflow(
    vendor_risk_payload: dict[str, Any],
    entity_relationship_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a guided vendor verification workflow from deterministic risk evidence."""
    return build_vendor_verification_workflow(vendor_risk_payload, entity_relationship_payload)


def create_payroll_tax_review(
    procedural_payload: dict[str, Any],
    issue_type: str | None = None,
) -> dict[str, Any]:
    """Create a guided payroll tax review workflow from IRS procedural evidence."""
    return build_payroll_tax_review_workflow(procedural_payload, issue_type=issue_type)


def create_missing_document_request(alert_id: str) -> dict:
    raise NotImplementedError("Workflow tools are planned for Phase 4.")
