from __future__ import annotations

import pytest

from app.graph import build_graph
from app.providers import ProviderRuntimeError
from tests.fakes import FakeLaravelToolClient, base_state


class DuplicatePaymentToolClient(FakeLaravelToolClient):
    async def transaction_lookup(
        self,
        company_id: str,
        user_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int | None = None,
        vendor: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.transaction_lookup_calls.append({"company_id": company_id, "user_id": user_id})
        return {
            "company_id": company_id,
            "total": 2,
            "returned_count": 2,
            "transactions": [
                {
                    "id": "txn-1",
                    "vendor": "ABC Supply",
                    "amount": 1840.22,
                    "date": "2026-04-01",
                    "invoice_number": "INV-100",
                    "memo": "April services",
                },
                {
                    "id": "txn-2",
                    "vendor": "ABC Supply",
                    "amount": 1840.22,
                    "date": "2026-04-03",
                    "invoice_number": "INV-100",
                    "memo": "April services",
                },
            ],
        }


class VendorRiskToolClient(FakeLaravelToolClient):
    async def vendor_risk(
        self,
        company_id: str,
        user_id: str,
        vendor: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.vendor_risk_calls.append({"company_id": company_id, "user_id": user_id, "vendor": vendor})
        return {
            "company_id": company_id,
            "vendor_name": "Overlap Vendor LLC",
            "vendor_id": "vendor-overlap-001",
            "vendor_risk_score": 84,
            "risk_level": "high",
            "triggered_rules": ["high vendor risk", "employee-vendor overlap"],
            "supporting_evidence": [
                {"type": "vendor", "id": "vendor-overlap-001", "vendor_id": "vendor-overlap-001"},
                {"type": "transaction", "id": "txn-overlap-001", "vendor_id": "vendor-overlap-001"},
            ],
            "recommended_next_action": "Review vendor relationship evidence.",
        }

    async def entity_relationship_risk(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict | None = None,
    ) -> dict:
        self.entity_relationship_risk_calls.append({"company_id": company_id, "user_id": user_id})
        return {
            "company_id": company_id,
            "entity_relationship_risk_score": 82,
            "risk_level": "high",
            "triggered_rules": ["employee-vendor overlap"],
            "supporting_evidence": [
                {"type": "employee_record", "id": "emp-overlap-001", "vendor_id": "vendor-overlap-001"},
            ],
            "recommended_next_action": "Validate relationship and approval chain.",
        }


@pytest.mark.asyncio
async def test_graph_routes_fraud_request_through_deterministic_risk_tool() -> None:
    graph = build_graph(FakeLaravelToolClient())

    result = await graph.ainvoke(base_state())

    assert result["intent"] == "fraud_pattern_search"
    assert result["findings"][0]["title"] == "Possible unusual vendor pattern"
    assert "does not prove fraud" in result["final_response"]
    assert result["recommended_actions"][0]["requires_approval"] is False
    assert [step["step_name"] for step in result["steps"]] == [
        "router",
        "context_loader",
        "fraud_analyzer",
        "investigation_synthesis",
        "explanation",
        "action_gate",
        "final_response",
    ]


class FailingProvider:
    provider_name = "openai"
    model_name = "gpt-4o"

    async def generate(self, prompt: str, context: dict):
        raise ProviderRuntimeError("OpenAI provider request failed.")


@pytest.mark.asyncio
async def test_graph_returns_safe_response_when_provider_fails() -> None:
    graph = build_graph(FakeLaravelToolClient(), provider=FailingProvider())

    result = await graph.ainvoke(base_state())

    assert result["final_response"] == "I could not complete the risk review right now. No alerts or cases were created."
    assert result["recommended_actions"] == []
    assert result["errors"] == ["OpenAI provider request failed."]

    explanation_step = next(step for step in result["steps"] if step["step_name"] == "explanation")
    assert explanation_step["status"] == "failed"
    assert explanation_step["error_message"] == "OpenAI provider request failed."


@pytest.mark.asyncio
async def test_graph_builds_duplicate_payment_review_workflow() -> None:
    graph = build_graph(DuplicatePaymentToolClient())

    result = await graph.ainvoke(base_state("Find duplicate payments this month."))

    assert result["recommended_workflow"] == "duplicate_payment_review"
    assert result["next_best_action"]["type"] == "review_duplicate_payment_evidence"
    assert result["recommended_actions"][0]["type"] == "review_duplicate_payment_evidence"
    assert result["tool_results"]["duplicate_payment_workflow"]["transaction_ids"] == ["txn-1", "txn-2"]
    assert any(step["step_name"] == "duplicate_payment_workflow" for step in result["steps"])


@pytest.mark.asyncio
async def test_graph_builds_vendor_verification_workflow() -> None:
    graph = build_graph(VendorRiskToolClient())

    result = await graph.ainvoke(base_state("Review high vendor risk with entity overlap."))

    assert result["recommended_workflow"] == "vendor_verification"
    assert result["next_best_action"]["type"] == "review_vendor_verification_evidence"
    assert result["recommended_actions"][0]["type"] == "review_vendor_verification_evidence"
    assert result["tool_results"]["vendor_verification_workflow"]["vendors"] == ["Overlap Vendor LLC"]
    assert result["tool_results"]["vendor_verification_workflow"]["vendor_ids"] == ["vendor-overlap-001"]
    assert any(step["step_name"] == "vendor_verification_workflow" for step in result["steps"])
