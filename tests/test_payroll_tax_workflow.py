from __future__ import annotations

from app.payroll_tax_workflow import build_payroll_tax_review_workflow, is_payroll_tax_issue


def test_payroll_tax_workflow_builds_tfrp_review_contract() -> None:
    workflow = build_payroll_tax_review_workflow(
        {
            "status": "ok",
            "issue_type": "trust fund recovery penalty",
            "risk_level": "high",
            "key_amount": "42,500.00",
            "deadline_days": 10,
            "tax_periods": ["2025-Q4", "2026-Q1"],
            "recommended_records": ["IRS notice", "account transcript", "EFTPS payment history"],
            "results": [
                {
                    "irm_reference": "5.7.1.1",
                    "title": "Trust fund recovery penalty",
                    "summary": "Source-backed TFRP procedural context.",
                }
            ],
        }
    )

    assert workflow["status"] == "ok"
    assert workflow["workflow_type"] == "payroll_tax_review"
    assert workflow["issue_type"] == "trust_fund_recovery_penalty"
    assert workflow["review_priority"] == "high"
    assert workflow["responsible_person_review_required"] is True
    assert workflow["source_references"] == ["5.7.1.1"]
    assert workflow["recommended_records"] == ["IRS notice", "account transcript", "EFTPS payment history"]
    assert workflow["tax_periods"] == ["2025-Q4", "2026-Q1"]
    assert workflow["recommended_action"]["type"] == "review_payroll_tax_evidence"
    assert workflow["recommended_action"]["requires_approval"] is False


def test_payroll_tax_workflow_requests_expected_evidence() -> None:
    workflow = build_payroll_tax_review_workflow({"issue_type": "payroll tax"}, issue_type="payroll tax")
    request_keys = {request["requirement_key"] for request in workflow["evidence_requests"]}

    assert {
        "irs_payroll_tax_notice",
        "forms_941_and_940",
        "eftps_deposit_history",
        "payroll_registers",
        "irs_account_transcripts",
        "penalty_and_payment_history",
    }.issubset(request_keys)
    assert "responsible_person_authority_records" not in request_keys
    assert workflow["readiness_summary"]["missing_evidence_count"] == len(workflow["evidence_gaps"])


def test_payroll_tax_workflow_adds_responsible_person_evidence_for_tfrp() -> None:
    workflow = build_payroll_tax_review_workflow({"issue_type": "TFRP"})
    request_keys = {request["requirement_key"] for request in workflow["evidence_requests"]}
    criteria_text = " ".join(workflow["escalation_criteria"])

    assert "responsible_person_authority_records" in request_keys
    assert "payroll_decision_timeline" in request_keys
    assert "responsible-person exposure" in criteria_text


def test_payroll_tax_workflow_derives_critical_priority_from_deadline_or_amount() -> None:
    workflow = build_payroll_tax_review_workflow(
        {
            "issue_type": "payroll tax",
            "deadline_days": 5,
            "key_amount": 125000,
        }
    )

    assert workflow["review_priority"] == "critical"
    assert "Response deadline is within 5 days." in workflow["escalation_criteria"]
    assert "Amount at issue is $125,000.00 or more." in workflow["escalation_criteria"]


def test_payroll_tax_workflow_handles_empty_or_non_payroll_payload() -> None:
    empty_workflow = build_payroll_tax_review_workflow({})
    levy_workflow = build_payroll_tax_review_workflow({"issue_type": "levy"})

    assert empty_workflow["status"] == "no_findings"
    assert empty_workflow["issue_type"] == "unknown"
    assert empty_workflow["recommended_action"]["type"] == "review_payroll_tax_evidence"
    assert levy_workflow["status"] == "no_findings"
    assert is_payroll_tax_issue({"issue_type": "payroll tax"}) is True
    assert is_payroll_tax_issue({"issue_type": "levy"}) is False
