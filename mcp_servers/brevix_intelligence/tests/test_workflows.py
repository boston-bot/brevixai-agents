from __future__ import annotations

from mcp_servers.brevix_intelligence.tools.workflows import create_duplicate_payment_review, create_irs_notice_review


def test_create_irs_notice_review_delegates_to_workflow_builder() -> None:
    result = create_irs_notice_review(
        {
            "notice_type": "CP504",
            "deadline_days": 7,
            "risk_level": "critical",
            "summary": "Intent to levy for unpaid balance.",
            "results": [{"irm_reference": "5.11.1.1"}],
        }
    )

    assert result["workflow_type"] == "irs_notice_review"
    assert result["review_priority"] == "critical"
    assert result["recommended_action"]["type"] == "prepare_irs_notice_review"


def test_create_duplicate_payment_review_delegates_to_workflow_builder() -> None:
    result = create_duplicate_payment_review(
        [
            {
                "title": "Duplicate Payment",
                "severity": "high",
                "confidence": 0.85,
                "summary": "Possible duplicate payment.",
                "evidence": [
                    {"transaction_id": "txn-1", "vendor": "ABC Supply", "amount": 500.0, "date": "2026-04-01"},
                    {"transaction_id": "txn-2", "vendor": "ABC Supply", "amount": 500.0, "date": "2026-04-03"},
                ],
            }
        ]
    )

    assert result["workflow_type"] == "duplicate_payment_review"
    assert result["recommended_action"]["type"] == "review_duplicate_payment_evidence"
    assert result["transaction_ids"] == ["txn-1", "txn-2"]
