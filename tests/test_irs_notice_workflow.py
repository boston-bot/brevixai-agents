from __future__ import annotations

from app.irs_notice_workflow import build_irs_notice_workflow


def test_collection_notice_workflow_builds_urgent_review_contract() -> None:
    workflow = build_irs_notice_workflow(
        {
            "notice_type": "CP504",
            "deadline_days": 10,
            "risk_level": "critical",
            "key_amount": "12,500.00",
            "summary": "Intent to levy state tax refund for a balance due.",
            "irm_search_topic": "levy notice intent to levy balance due collection",
            "results": [{"irm_reference": "5.11.1.1"}],
        }
    )

    assert workflow["workflow_type"] == "irs_notice_review"
    assert workflow["notice_type"] == "CP504"
    assert workflow["issue_family"] == "collection"
    assert workflow["review_priority"] == "critical"
    assert workflow["deadline_urgency"] == "high"
    assert workflow["source_references"] == ["5.11.1.1"]
    assert workflow["recommended_action"]["type"] == "prepare_irs_notice_review"
    assert any(item["requirement_key"] == "collection_status_records" for item in workflow["evidence_requests"])
    assert any("deadline is within 10 days" in item.lower() for item in workflow["escalation_criteria"])


def test_underreporter_notice_workflow_requests_income_support() -> None:
    workflow = build_irs_notice_workflow(
        {
            "notice_type": "CP2000",
            "deadline_days": 30,
            "risk_level": "medium",
            "summary": "Proposed change because income may be underreported.",
            "results": [{"reference": "4.19.3.1"}],
        }
    )

    assert workflow["issue_family"] == "underreporter"
    assert workflow["review_priority"] == "medium"
    assert any(item["requirement_key"] == "income_support" for item in workflow["evidence_requests"])
    assert workflow["readiness_summary"]["missing_evidence_count"] >= 1


def test_notice_workflow_flags_missing_irm_support() -> None:
    workflow = build_irs_notice_workflow(
        {
            "notice_type": "Unknown",
            "deadline_days": None,
            "risk_level": "medium",
            "results": [],
        }
    )

    assert workflow["source_references"] == []
    assert any("No source-backed IRM section" in item for item in workflow["escalation_criteria"])
