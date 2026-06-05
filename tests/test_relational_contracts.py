from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from app.relational_readiness import build_relational_readiness_audit


REQUIRED_PAYMENT_FIELDS = {
    "id",
    "company_id",
    "vendor_id",
    "amount",
    "date",
    "approved_by",
    "document_id",
    "bank_account_id",
    "company_user_id",
}


def _complete_sources() -> dict:
    return {
        "transactions": [
            {
                "id": "txn-1",
                "company_id": "company-1",
                "company_user_id": "user-1",
                "vendor_id": "vendor-1",
                "vendor": "ABC Supply",
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


def _contract_by_name(contracts: list[dict], name: str) -> dict:
    return next(contract for contract in contracts if contract["name"] == name)


def test_phase_5b_complete_payload_contract_is_graph_ready() -> None:
    audit = build_relational_readiness_audit(_complete_sources())

    assert audit["phase_5_ready"] is True
    assert audit["critical_blockers"] == []
    payment_contract = _contract_by_name(audit["entity_contracts"], "payments")
    assert payment_contract["status"] == "ready"
    assert set(payment_contract["present_fields"]).issuperset(REQUIRED_PAYMENT_FIELDS)


def test_phase_5b_payment_contract_blocks_when_required_fields_are_missing() -> None:
    for field in REQUIRED_PAYMENT_FIELDS:
        sources = deepcopy(_complete_sources())
        sources["transactions"][0].pop(field)

        audit = build_relational_readiness_audit(sources)
        payment_contract = _contract_by_name(audit["entity_contracts"], "payments")

        assert audit["phase_5_ready"] is False, field
        assert field in payment_contract["missing_required_fields"], field
        assert payment_contract["status"] in {"missing", "partial"}, field


def test_phase_5b_vendor_name_only_is_not_graph_ready() -> None:
    sources = deepcopy(_complete_sources())
    sources["transactions"][0].pop("vendor_id")
    sources["vendor_risk"] = {"vendor_name": "ABC Supply", "vendor_risk_score": 42}
    sources["entity_relationship_risk"]["supporting_evidence"][0].pop("vendor_id")

    audit = build_relational_readiness_audit(sources)
    vendors = _contract_by_name(audit["entity_contracts"], "vendors")
    payment_to_vendor = _contract_by_name(audit["relationship_contracts"], "payment_to_vendor")

    assert audit["phase_5_ready"] is False
    assert vendors["status"] == "partial"
    assert payment_to_vendor["status"] == "partial"
    assert "vendor_id" in payment_to_vendor["missing_required_fields"]


def test_phase_5b_entity_relationship_contracts_require_stable_endpoints() -> None:
    sources = deepcopy(_complete_sources())
    sources["entity_relationship_risk"]["supporting_evidence"][0].pop("employee_id")

    audit = build_relational_readiness_audit(sources)
    employees = _contract_by_name(audit["entity_contracts"], "employees")
    employee_vendor = _contract_by_name(audit["relationship_contracts"], "employee_shares_address_with_vendor")

    assert audit["phase_5_ready"] is False
    assert employees["status"] == "missing"
    assert employee_vendor["status"] == "missing"
    assert "employee_id" in employees["missing_required_fields"]


def test_phase_5b_contract_doc_lists_required_identifiers() -> None:
    doc = Path("docs/mcp/PHASE_5B_RELATIONAL_CONTRACT.md").read_text()

    for field in sorted(REQUIRED_PAYMENT_FIELDS):
        assert f"`{field}`" in doc

    for relationship in (
        "Payment To Vendor",
        "Employee Approved Payment",
        "Payment To Document",
        "Vendor Uses Bank Account",
    ):
        assert relationship in doc
