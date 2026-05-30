"""Tests for control weakness analysis data gating."""

from __future__ import annotations

from mcp_servers.brevix_intelligence.tools.control_weaknesses import _analyze_control_weaknesses


def analyze(transactions: list[dict]) -> list:
    return _analyze_control_weaknesses(
        transactions,
        min_amount=1000.0,
        approver_dominance_threshold=0.80,
    )


def test_absent_approval_and_document_fields_do_not_emit_findings() -> None:
    transactions = [
        {"id": "t1", "vendor": "Vendor A", "amount": 1500.0, "date": "2026-05-01"},
        {"id": "t2", "vendor": "Vendor B", "amount": 2500.0, "date": "2026-05-02"},
    ]

    assert analyze(transactions) == []


def test_missing_approval_emits_only_when_approval_field_is_supported() -> None:
    transactions = [
        {"id": "t1", "vendor": "Vendor A", "amount": 1500.0, "date": "2026-05-01", "approved_by": None},
        {"id": "t2", "vendor": "Vendor B", "amount": 2500.0, "date": "2026-05-02", "approved_by": ""},
    ]

    findings = analyze(transactions)

    assert [finding.risk_type for finding in findings] == ["missing_approval"]
    assert findings[0].metadata["unapproved_count"] == 2


def test_missing_documentation_emits_only_when_document_field_is_supported() -> None:
    transactions = [
        {"id": "t1", "vendor": "Vendor A", "amount": 1500.0, "date": "2026-05-01", "document_id": None},
        {"id": "t2", "vendor": "Vendor B", "amount": 2500.0, "date": "2026-05-02", "document_id": ""},
    ]

    findings = analyze(transactions)

    assert [finding.risk_type for finding in findings] == ["missing_documentation"]
    assert findings[0].metadata["undocumented_count"] == 2


def test_approval_concentration_still_emits_when_approval_data_is_supported() -> None:
    transactions = [
        {
            "id": f"t{i}",
            "vendor": f"Vendor {i}",
            "amount": 1500.0,
            "date": "2026-05-01",
            "approved_by": "approver-1",
        }
        for i in range(5)
    ]

    findings = analyze(transactions)

    assert [finding.risk_type for finding in findings] == ["approval_concentration"]
    assert findings[0].metadata["top_approver"] == "approver-1"


def test_below_threshold_transactions_are_not_used_to_infer_field_support() -> None:
    transactions = [
        {
            "id": "small",
            "vendor": "Vendor A",
            "amount": 50.0,
            "date": "2026-05-01",
            "approved_by": None,
            "document_id": None,
        },
        {"id": "large", "vendor": "Vendor B", "amount": 2500.0, "date": "2026-05-02"},
    ]

    assert analyze(transactions) == []
