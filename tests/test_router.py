from __future__ import annotations

import pytest

from app.graph import build_graph
from tests.fakes import FakeLaravelToolClient, base_state


class RelationalReadinessToolClient(FakeLaravelToolClient):
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
        self.transaction_lookup_calls.append({"company_id": company_id, "user_id": user_id, "limit": limit})
        return {
            "company_id": company_id,
            "total": 1,
            "returned_count": 1,
            "transactions": [
                {"id": "txn-1", "vendor": "ABC Supply", "amount": 1000.0, "date": "2026-05-01"}
            ],
        }


@pytest.mark.asyncio
async def test_router_classifies_fraud_request() -> None:
    graph = build_graph(FakeLaravelToolClient())

    result = await graph.ainvoke(base_state("Are there suspicious vendors this month?"))

    assert result["intent"] == "fraud_pattern_search"


@pytest.mark.asyncio
async def test_router_classifies_unsupported_request_without_fraud_tool_call() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("Write a marketing slogan."))

    assert result["intent"] == "unknown_or_unsupported"
    assert tool_client.risk_summary_calls == []


@pytest.mark.asyncio
async def test_router_classifies_plain_transaction_lookup_without_risk_tool_call() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("What are my transactions for the last 5 days?"))

    assert result["intent"] == "transaction_lookup"
    assert tool_client.risk_summary_calls == []
    assert tool_client.company_context_calls[0]["transaction_filters"]["date_from"]
    assert "I found 2 transactions" in result["final_response"]


@pytest.mark.asyncio
async def test_router_classifies_financial_health_as_dashboard_health() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("What's my current financial health?"))

    assert result["intent"] == "dashboard_health"
    assert tool_client.risk_summary_calls == []
    assert tool_client.company_context_calls[0]["dashboard_context"] is True
    assert result["findings"][0]["title"] == "Financial health summary"
    assert result["findings"][0]["evidence"][0]["type"] == "dashboard_metric"
    assert "Your current financial health score is 42/100" in result["final_response"]


@pytest.mark.asyncio
async def test_router_builds_relational_readiness_audit_without_risk_summary() -> None:
    tool_client = RelationalReadinessToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("Is relational data ready to begin Phase 5 graph intelligence?"))

    assert result["intent"] == "relational_readiness_audit"
    assert tool_client.risk_summary_calls == []
    assert tool_client.transaction_lookup_calls[0]["limit"] == 100
    assert result["tool_results"]["relational_readiness_audit"]["phase_5_ready"] is False
    assert result["readiness_summary"]["critical_blocker_count"] > 0
    assert result["next_best_action"]["type"] == "prepare_relational_data_contracts"
    assert result["recommended_actions"][0]["type"] == "prepare_relational_data_contracts"
    assert "Phase 5 relational readiness audit: not ready" in result["final_response"]
    assert any(step["step_name"] == "relational_readiness_audit" for step in result["steps"])


@pytest.mark.asyncio
async def test_router_classifies_irs_notice_explanation_without_risk_tool_call() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("Explain IRS notice CP504."))

    assert result["intent"] == "irs_procedural_question"
    assert tool_client.risk_summary_calls == []
    assert tool_client.irs_notice_type_calls[0]["code"] == "CP504"
    assert "irm_reference:" in result["final_response"]
    assert "Disclaimer:" in result["final_response"]


@pytest.mark.asyncio
async def test_router_classifies_irs_records_request_without_risk_tool_call() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("What records should I gather for a levy notice?"))

    assert result["intent"] == "irs_procedural_question"
    assert tool_client.risk_summary_calls == []
    assert tool_client.irs_records_checklist_calls[0]["issue_type"] == "levy"
    assert "Records to gather:" in result["final_response"]


@pytest.mark.asyncio
async def test_router_prefers_records_tool_for_notice_records_request() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("What records should I gather for CP504?"))

    assert result["intent"] == "irs_procedural_question"
    assert tool_client.irs_notice_type_calls == []
    assert tool_client.irs_records_checklist_calls[0]["issue_type"] == "CP504"


@pytest.mark.asyncio
async def test_router_builds_payroll_tax_review_workflow_for_tfrp_request() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("Explain trust fund recovery penalty collection process."))

    assert result["intent"] == "irs_procedural_question"
    assert tool_client.risk_summary_calls == []
    assert tool_client.irs_collection_risk_calls[0]["issue_type"] == "trust fund recovery penalty"
    assert result["recommended_workflow"] == "payroll_tax_review"
    assert result["next_best_action"]["type"] == "review_payroll_tax_evidence"
    assert result["recommended_actions"][0]["type"] == "review_payroll_tax_evidence"
    assert result["tool_results"]["payroll_tax_workflow"]["issue_type"] == "trust_fund_recovery_penalty"
    assert result["tool_results"]["payroll_tax_workflow"]["responsible_person_review_required"] is True
    assert "Workflow next steps:" in result["final_response"]
    assert any(step["step_name"] == "payroll_tax_workflow" for step in result["steps"])


@pytest.mark.asyncio
async def test_router_does_not_route_tax_advice_positioning_to_irs_tools() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("Should I pay less tax by settling with the IRS?"))

    assert result["intent"] == "unknown_or_unsupported"
    assert tool_client.risk_summary_calls == []
    assert tool_client.irs_notice_type_calls == []
    assert tool_client.irs_collection_risk_calls == []
