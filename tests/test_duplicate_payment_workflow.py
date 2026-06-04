from __future__ import annotations

from app.duplicate_payment_workflow import build_duplicate_payment_review_workflow


def duplicate_finding(
    *,
    vendor: str = "ABC Supply",
    amount: float = 1200.0,
    confidence: float = 0.85,
    severity: str = "high",
    invoice_number: str | None = "INV-100",
    memo: str | None = "April services",
) -> dict:
    return {
        "title": "Duplicate Payment",
        "severity": severity,
        "confidence": confidence,
        "summary": f"Possible duplicate payment to {vendor}.",
        "evidence": [
            {
                "transaction_id": "txn-1",
                "vendor": vendor,
                "amount": amount,
                "date": "2026-04-01",
                "invoice_number": invoice_number,
                "memo": memo,
            },
            {
                "transaction_id": "txn-2",
                "vendor": vendor,
                "amount": amount,
                "date": "2026-04-03",
                "invoice_number": invoice_number,
                "memo": memo,
            },
        ],
    }


def test_duplicate_payment_workflow_extracts_review_contract() -> None:
    workflow = build_duplicate_payment_review_workflow([duplicate_finding()])

    assert workflow["status"] == "ok"
    assert workflow["workflow_type"] == "duplicate_payment_review"
    assert workflow["review_priority"] == "high"
    assert workflow["duplicate_count"] == 1
    assert workflow["vendors"] == ["ABC Supply"]
    assert workflow["transaction_ids"] == ["txn-1", "txn-2"]
    assert workflow["total_amount_exposure"] == 1200.0
    assert workflow["recommended_action"]["type"] == "review_duplicate_payment_evidence"


def test_duplicate_payment_workflow_includes_required_evidence_requests() -> None:
    workflow = build_duplicate_payment_review_workflow([duplicate_finding()])
    keys = {item["requirement_key"] for item in workflow["evidence_requests"]}

    assert {
        "invoice_documentation",
        "payment_status",
        "void_or_refund_activity",
        "vendor_confirmation",
    }.issubset(keys)
    assert workflow["readiness_summary"]["missing_evidence_count"] == len(workflow["evidence_gaps"])


def test_duplicate_payment_workflow_aggregates_vendors_and_transactions() -> None:
    first = duplicate_finding(vendor="ABC Supply", amount=500.0, confidence=0.70, severity="medium")
    second = duplicate_finding(vendor="Northstar Consulting", amount=750.0, confidence=0.75, severity="medium")
    second["evidence"][0]["transaction_id"] = "txn-3"
    second["evidence"][1]["transaction_id"] = "txn-4"

    workflow = build_duplicate_payment_review_workflow([first, second])

    assert workflow["duplicate_count"] == 2
    assert workflow["vendors"] == ["ABC Supply", "Northstar Consulting"]
    assert workflow["transaction_ids"] == ["txn-1", "txn-2", "txn-3", "txn-4"]
    assert workflow["total_amount_exposure"] == 1250.0


def test_duplicate_payment_workflow_escalates_large_repeated_vendor_case() -> None:
    first = duplicate_finding(vendor="ABC Supply", amount=12000.0, confidence=0.92, severity="high")
    second = duplicate_finding(vendor="ABC Supply", amount=13000.0, confidence=0.80, severity="high")
    second["evidence"][0]["transaction_id"] = "txn-3"
    second["evidence"][1]["transaction_id"] = "txn-4"

    workflow = build_duplicate_payment_review_workflow([first, second])

    assert workflow["review_priority"] == "critical"
    assert any("confidence is 0.92" in item for item in workflow["escalation_criteria"])
    assert any("same invoice number or memo" in item for item in workflow["escalation_criteria"])
    assert any("$25,000.00" in item for item in workflow["escalation_criteria"])
    assert any("ABC Supply" in item for item in workflow["escalation_criteria"])


def test_duplicate_payment_workflow_handles_empty_findings() -> None:
    workflow = build_duplicate_payment_review_workflow([])

    assert workflow["status"] == "no_findings"
    assert workflow["review_priority"] == "info"
    assert workflow["duplicate_count"] == 0
    assert workflow["vendors"] == []
    assert workflow["transaction_ids"] == []
    assert workflow["next_steps"] == ["No duplicate payment findings were available for workflow review."]
