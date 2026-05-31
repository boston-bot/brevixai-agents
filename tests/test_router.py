from __future__ import annotations

import pytest

from app.graph import build_graph
from tests.fakes import FakeLaravelToolClient, base_state


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
async def test_router_does_not_route_tax_advice_positioning_to_irs_tools() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("Should I pay less tax by settling with the IRS?"))

    assert result["intent"] == "unknown_or_unsupported"
    assert tool_client.risk_summary_calls == []
    assert tool_client.irs_notice_type_calls == []
    assert tool_client.irs_collection_risk_calls == []
