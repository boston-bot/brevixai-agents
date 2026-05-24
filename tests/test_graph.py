from __future__ import annotations

import pytest

from app.graph import build_graph
from app.providers import ProviderRuntimeError
from tests.fakes import FakeLaravelToolClient, base_state


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
