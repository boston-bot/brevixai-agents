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
