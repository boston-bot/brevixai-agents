from __future__ import annotations

from mcp_servers.brevix_intelligence.tools.relational_readiness import audit_relational_readiness


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
