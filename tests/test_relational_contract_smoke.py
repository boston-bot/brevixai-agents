from __future__ import annotations

import pytest

from scripts import smoke_relational_contract


class CompleteContractClient:
    async def company_context(self, company_id: str, user_id: str) -> dict:
        return {"company_id": company_id, "user_id": user_id}

    async def transaction_lookup(self, company_id: str, user_id: str, limit: int) -> dict:
        return {
            "company_id": company_id,
            "total": 1,
            "returned_count": 1,
            "transactions": [
                {
                    "id": "txn-1",
                    "company_id": company_id,
                    "company_user_id": user_id,
                    "vendor_id": "vendor-1",
                    "vendor": "ABC Supply",
                    "bank_account_id": "bank-1",
                    "approved_by": "employee-1",
                    "document_id": "doc-1",
                    "amount": 1000.0,
                    "date": "2026-05-01",
                }
            ],
        }

    async def vendor_risk(self, company_id: str, user_id: str) -> dict:
        return {
            "vendor_id": "vendor-1",
            "vendor_name": "ABC Supply",
            "vendor_risk_score": 42,
        }

    async def entity_relationship_risk(self, company_id: str, user_id: str) -> dict:
        return {
            "supporting_evidence": [
                {
                    "employee_id": "employee-1",
                    "vendor_id": "vendor-1",
                    "bank_account_id": "bank-1",
                    "related_vendor_id": "vendor-2",
                    "relationship_type": "shared_address",
                }
            ]
        }


class BlockedContractClient(CompleteContractClient):
    async def transaction_lookup(self, company_id: str, user_id: str, limit: int) -> dict:
        return {
            "company_id": company_id,
            "total": 1,
            "returned_count": 1,
            "transactions": [
                {"id": "txn-1", "vendor": "ABC Supply", "amount": 1000.0, "date": "2026-05-01"}
            ],
        }

    async def vendor_risk(self, company_id: str, user_id: str) -> dict:
        return {"vendor_name": "ABC Supply", "vendor_risk_score": 42}

    async def entity_relationship_risk(self, company_id: str, user_id: str) -> dict:
        return {"supporting_evidence": []}


class FailingVendorClient(CompleteContractClient):
    async def vendor_risk(self, company_id: str, user_id: str) -> dict:
        raise RuntimeError("vendor endpoint unavailable")


@pytest.mark.asyncio
async def test_contract_gate_passes_when_payloads_satisfy_phase_5b_contract() -> None:
    result = await smoke_relational_contract.run_contract_gate(
        CompleteContractClient(),
        company_id="company-1",
        user_id="user-1",
    )

    assert result["passed"] is True
    assert result["tool_failures"] == []
    assert result["audit"]["phase_5_ready"] is True


@pytest.mark.asyncio
async def test_contract_gate_fails_when_payload_identifiers_are_missing() -> None:
    result = await smoke_relational_contract.run_contract_gate(
        BlockedContractClient(),
        company_id="company-1",
        user_id="user-1",
    )

    blockers = {blocker["contract"]: blocker for blocker in result["audit"]["critical_blockers"]}

    assert result["passed"] is False
    assert result["audit"]["phase_5_ready"] is False
    assert "payments" in blockers
    assert "vendor_id" in blockers["payments"]["missing_required_fields"]
    assert "document_id" in blockers["payments"]["missing_required_fields"]


@pytest.mark.asyncio
async def test_contract_gate_fails_when_optional_payload_fetch_fails() -> None:
    result = await smoke_relational_contract.run_contract_gate(
        FailingVendorClient(),
        company_id="company-1",
        user_id="user-1",
    )

    assert result["passed"] is False
    assert result["tool_failures"][0]["tool"] == "vendor_risk"
    assert result["audit"]["phase_5_ready"] is True


def test_contract_gate_cli_requires_tool_key(monkeypatch: pytest.MonkeyPatch) -> None:
    exit_code = smoke_relational_contract.main(
        [
            "--base-url",
            "http://laravel.test",
            "--tool-key",
            "",
            "--company-id",
            "company-1",
            "--user-id",
            "user-1",
        ]
    )

    assert exit_code == 2


def test_contract_gate_cli_can_allow_blocked_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run_contract_gate(client, company_id: str, user_id: str, *, transaction_limit: int = 100) -> dict:
        return {
            "passed": False,
            "company_id": company_id,
            "user_id": user_id,
            "transaction_limit": transaction_limit,
            "latency_ms": 1.0,
            "tool_failures": [],
            "audit": {
                "phase_5_ready": False,
                "status": "blocked",
                "readiness_score": 0.1,
                "readiness_summary": {
                    "entity_ready_count": 1,
                    "entity_contract_count": 7,
                    "relationship_ready_count": 0,
                    "relationship_contract_count": 6,
                },
                "critical_blockers": [],
            },
            "answer": "blocked",
        }

    monkeypatch.setattr(smoke_relational_contract, "run_contract_gate", fake_run_contract_gate)

    exit_code = smoke_relational_contract.main(
        [
            "--base-url",
            "http://laravel.test",
            "--tool-key",
            "tool-key",
            "--company-id",
            "company-1",
            "--user-id",
            "user-1",
            "--allow-blocked",
        ]
    )

    assert exit_code == 0
