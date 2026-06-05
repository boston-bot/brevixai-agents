from __future__ import annotations

from app.relational_contract_adoption import build_relational_contract_adoption_report
from app.relational_readiness import build_relational_readiness_audit


def _complete_sources() -> dict:
    return {
        "transactions": [
            {
                "id": "txn-1",
                "company_id": "company-1",
                "company_user_id": "user-1",
                "vendor_id": "vendor-1",
                "bank_account_id": "bank-1",
                "approved_by": "employee-1",
                "document_id": "doc-1",
                "amount": 1000.0,
                "date": "2026-05-01",
            }
        ],
        "vendor_risk": {
            "vendor_id": "vendor-1",
            "vendor_name": "ABC Supply",
            "vendor_risk_score": 42,
        },
        "entity_relationship_risk": {
            "supporting_evidence": [
                {
                    "employee_id": "employee-1",
                    "vendor_id": "vendor-1",
                    "bank_account_id": "bank-1",
                    "related_vendor_id": "vendor-2",
                    "relationship_type": "shared_address",
                }
            ]
        },
        "company_context": {"company_id": "company-1", "user_id": "user-1"},
    }


def test_relational_contract_adoption_report_is_ready_when_audit_is_ready() -> None:
    audit = build_relational_readiness_audit(_complete_sources())

    report = build_relational_contract_adoption_report(audit)

    assert report["report_type"] == "relational_contract_adoption"
    assert report["status"] == "ready"
    assert report["phase_5_ready"] is True
    assert report["blocking_endpoint_count"] == 0
    assert report["api_remediation_tasks"] == []
    assert report["recommended_action"]["type"] == "update_laravel_relational_payloads"


def test_relational_contract_adoption_report_maps_blockers_to_laravel_endpoints() -> None:
    audit = build_relational_readiness_audit(
        {
            "transaction_lookup": {
                "transactions": [
                    {"id": "txn-1", "vendor": "ABC Supply", "amount": 1000.0, "date": "2026-05-01"}
                ]
            },
            "vendor_risk": {"vendor_name": "ABC Supply", "vendor_risk_score": 42},
            "entity_relationship_risk": {"supporting_evidence": []},
            "company_context": {"company_id": "company-1"},
        }
    )

    report = build_relational_contract_adoption_report(audit)
    endpoints = {endpoint["endpoint"]: endpoint for endpoint in report["endpoint_requirements"]}
    tasks = {task["endpoint"]: task for task in report["api_remediation_tasks"]}

    assert report["status"] == "blocked"
    assert endpoints["transaction_lookup"]["status"] == "blocked"
    assert "payments" in endpoints["transaction_lookup"]["affected_contracts"]
    assert "vendor_id" in endpoints["transaction_lookup"]["missing_fields"]
    assert "document_id" in endpoints["transaction_lookup"]["missing_fields"]
    assert tasks["transaction_lookup"]["priority"] == "high"
    assert any("document" in action for action in tasks["transaction_lookup"]["actions"])


def test_relational_contract_adoption_report_includes_tool_failures() -> None:
    audit = build_relational_readiness_audit(_complete_sources())

    report = build_relational_contract_adoption_report(
        audit,
        tool_failures=[
            {
                "tool": "vendor_risk",
                "error_class": "RuntimeError",
                "message": "vendor endpoint unavailable",
            }
        ],
    )
    endpoints = {endpoint["endpoint"]: endpoint for endpoint in report["endpoint_requirements"]}

    assert report["status"] == "blocked"
    assert report["phase_5_ready"] is False
    assert endpoints["vendor_risk"]["status"] == "failed"
    assert endpoints["vendor_risk"]["tool_failure"]["message"] == "vendor endpoint unavailable"
    assert any(task["endpoint"] == "vendor_risk" for task in report["api_remediation_tasks"])
