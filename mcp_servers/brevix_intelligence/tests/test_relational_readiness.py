from __future__ import annotations

from mcp_servers.brevix_intelligence.tools.relational_readiness import (
    audit_relational_readiness,
    build_relational_contract_adoption,
    build_relational_projection,
)


def test_audit_relational_readiness_delegates_to_builder() -> None:
    result = audit_relational_readiness(
        {
            "transactions": [
                {"id": "txn-1", "vendor": "ABC Supply", "amount": 1000.0, "date": "2026-05-01"}
            ]
        }
    )

    assert result["audit_type"] == "relational_readiness"
    assert result["phase_5_ready"] is False
    assert result["recommended_action"]["type"] == "prepare_relational_data_contracts"


def test_build_relational_contract_adoption_delegates_to_builder() -> None:
    result = build_relational_contract_adoption(
        {
            "transactions": [
                {"id": "txn-1", "vendor": "ABC Supply", "amount": 1000.0, "date": "2026-05-01"}
            ]
        }
    )

    assert result["report_type"] == "relational_contract_adoption"
    assert result["status"] == "blocked"
    assert result["recommended_action"]["type"] == "update_laravel_relational_payloads"


def test_build_relational_projection_delegates_to_builder() -> None:
    result = build_relational_projection(
        {
            "transactions": [
                {"id": "txn-1", "vendor": "ABC Supply", "amount": 1000.0, "date": "2026-05-01"}
            ]
        }
    )

    assert result["projection_type"] == "relational_graph_projection"
    assert result["status"] == "blocked"
    assert result["nodes"] == []
