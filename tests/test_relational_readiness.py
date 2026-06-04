from __future__ import annotations

from app.relational_readiness import build_relational_readiness_audit, synthesize_relational_readiness_answer


def test_relational_readiness_blocks_when_core_identifiers_are_missing() -> None:
    audit = build_relational_readiness_audit(
        {
            "transaction_lookup": {
                "transactions": [
                    {"id": "txn-1", "vendor": "ABC Supply", "amount": 1000.0, "date": "2026-05-01"},
                    {"id": "txn-2", "vendor": "ABC Supply", "amount": 1200.0, "date": "2026-05-02"},
                ]
            },
            "company_context": {"company_id": "company-1"},
        }
    )

    contracts = {contract["name"]: contract for contract in audit["entity_contracts"]}
    blockers = {blocker["contract"]: blocker for blocker in audit["critical_blockers"]}

    assert audit["status"] == "blocked"
    assert audit["phase_5_ready"] is False
    assert contracts["payments"]["status"] == "partial"
    assert contracts["vendors"]["status"] == "partial"
    assert contracts["approvers"]["status"] == "missing"
    assert contracts["documents"]["status"] == "missing"
    assert blockers["approvers"]["missing_required_fields"] == ["approved_by"]
    assert blockers["documents"]["missing_required_fields"] == ["document_id"]


def test_relational_readiness_marks_contracts_ready_when_stable_ids_exist() -> None:
    audit = build_relational_readiness_audit(
        {
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
    )

    assert audit["status"] == "ready"
    assert audit["phase_5_ready"] is True
    assert audit["critical_blockers"] == []
    assert audit["readiness_summary"]["entity_ready_count"] == audit["readiness_summary"]["entity_contract_count"]
    assert audit["readiness_summary"]["relationship_ready_count"] == audit["readiness_summary"]["relationship_contract_count"]


def test_relational_readiness_uses_vendor_and_entity_payloads_for_contract_evidence() -> None:
    audit = build_relational_readiness_audit(
        {
            "transactions": [
                {"id": "txn-1", "vendor": "Overlap Vendor", "amount": 1000.0, "date": "2026-05-01"}
            ],
            "vendor_risk": {
                "vendor_name": "Overlap Vendor",
                "vendor_id": "vendor-1",
                "vendor_risk_score": 82,
            },
            "entity_relationship_risk": {
                "supporting_evidence": [{"employee_id": "employee-1", "vendor_id": "vendor-1"}]
            },
        }
    )

    contracts = {contract["name"]: contract for contract in audit["entity_contracts"]}

    assert contracts["vendors"]["status"] == "ready"
    assert contracts["employees"]["status"] == "ready"
    assert audit["phase_5_ready"] is False


def test_relational_readiness_answer_summarizes_blockers_and_next_steps() -> None:
    audit = build_relational_readiness_audit(
        {"transactions": [{"id": "txn-1", "vendor": "ABC", "amount": 1000.0, "date": "2026-05-01"}]}
    )

    answer = synthesize_relational_readiness_answer(audit)

    assert "Phase 5 relational readiness audit: not ready" in answer
    assert "Critical blockers:" in answer
    assert "approved_by" in answer
    assert "document_id" in answer
    assert "No graph database, graph infrastructure, alerts, cases, or data changes were created." in answer
