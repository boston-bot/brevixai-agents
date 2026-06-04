from __future__ import annotations

from app.vendor_verification_workflow import build_vendor_verification_workflow


def test_vendor_verification_workflow_builds_priority_from_vendor_and_entity_risk() -> None:
    workflow = build_vendor_verification_workflow(
        {
            "vendor_name": "Overlap Vendor LLC",
            "vendor_id": "vendor-overlap-001",
            "vendor_risk_score": 84,
            "risk_level": "high",
            "triggered_rules": ["high vendor risk", "employee-vendor overlap"],
            "supporting_evidence": [
                {"type": "vendor", "id": "vendor-overlap-001", "vendor_id": "vendor-overlap-001"},
                {"type": "transaction", "id": "txn-overlap-001", "vendor_id": "vendor-overlap-001"},
            ],
        },
        {
            "entity_relationship_risk_score": 92,
            "risk_level": "critical",
            "triggered_rules": ["employee-vendor overlap"],
            "supporting_evidence": [
                {"type": "employee_record", "id": "emp-overlap-001", "vendor_id": "vendor-overlap-001"},
            ],
        },
    )

    assert workflow["status"] == "ok"
    assert workflow["workflow_type"] == "vendor_verification"
    assert workflow["review_priority"] == "critical"
    assert workflow["highest_vendor_risk_score"] == 84
    assert workflow["entity_relationship_risk_score"] == 92
    assert workflow["recommended_action"]["type"] == "review_vendor_verification_evidence"
    assert workflow["recommended_action"]["requires_approval"] is False


def test_vendor_verification_workflow_aggregates_vendor_names_ids_rules_and_evidence() -> None:
    workflow = build_vendor_verification_workflow(
        {
            "vendors": [
                {
                    "vendor_name": "Harbor Advisory LLC",
                    "vendor_id": "vendor-1",
                    "vendor_risk_score": 76,
                    "risk_level": "high",
                    "triggered_rules": ["rapid onboarding", "shared account"],
                    "supporting_evidence": [
                        {"type": "vendor", "id": "vendor-1", "vendor_id": "vendor-1"},
                        {"type": "transaction", "transaction_id": "txn-1", "vendor_id": "vendor-1"},
                    ],
                },
                {
                    "vendor_name": "Lakeside Services",
                    "vendor_id": "vendor-2",
                    "vendor_risk_score": 42,
                    "risk_level": "medium",
                    "triggered_rules": ["shared account"],
                    "supporting_evidence": [{"type": "vendor", "id": "vendor-2", "vendor_id": "vendor-2"}],
                },
                {
                    "vendor_name": "Clean Vendor",
                    "vendor_id": "vendor-3",
                    "vendor_risk_score": 12,
                    "risk_level": "low",
                },
            ]
        }
    )

    assert workflow["vendor_count"] == 2
    assert workflow["vendors"] == ["Harbor Advisory LLC", "Lakeside Services"]
    assert workflow["vendor_ids"] == ["vendor-1", "vendor-2"]
    assert workflow["triggered_rules"] == ["rapid onboarding", "shared account"]
    assert workflow["supporting_evidence_ids"] == ["vendor-1", "txn-1", "vendor-2"]
    assert workflow["supporting_evidence_count"] == 3


def test_vendor_verification_workflow_requests_expected_evidence() -> None:
    workflow = build_vendor_verification_workflow(
        {
            "vendor_name": "Harbor Advisory LLC",
            "vendor_id": "vendor-1",
            "vendor_risk_score": 70,
            "risk_level": "high",
        }
    )

    request_keys = {request["requirement_key"] for request in workflow["evidence_requests"]}

    assert {
        "vendor_master_record",
        "tax_documentation",
        "bank_payment_validation",
        "ownership_relationship_review",
        "invoice_payment_support",
    }.issubset(request_keys)
    assert workflow["evidence_gaps"]
    assert workflow["readiness_summary"]["missing_evidence_count"] == len(workflow["evidence_gaps"])


def test_vendor_verification_workflow_adds_relationship_escalation_criteria() -> None:
    workflow = build_vendor_verification_workflow(
        {
            "vendor_name": "Overlap Vendor LLC",
            "vendor_id": "vendor-overlap-001",
            "vendor_risk_score": 74,
            "risk_level": "high",
            "triggered_rules": ["employee-vendor overlap"],
        },
        {"entity_relationship_risk_score": 81},
    )

    criteria_text = " ".join(workflow["escalation_criteria"])

    assert "Highest vendor risk score is 74/100." in workflow["escalation_criteria"]
    assert "Entity relationship risk score is 81/100." in workflow["escalation_criteria"]
    assert "employee-vendor overlap" in criteria_text


def test_vendor_verification_workflow_handles_empty_or_clean_payloads() -> None:
    empty_workflow = build_vendor_verification_workflow({})
    clean_workflow = build_vendor_verification_workflow(
        {
            "vendor_name": "Clean Vendor",
            "vendor_id": "vendor-clean-001",
            "vendor_risk_score": 12,
            "risk_level": "low",
        }
    )

    assert empty_workflow["status"] == "no_findings"
    assert empty_workflow["vendor_count"] == 0
    assert empty_workflow["recommended_action"]["type"] == "review_vendor_verification_evidence"
    assert clean_workflow["status"] == "no_findings"
    assert clean_workflow["vendor_count"] == 0
