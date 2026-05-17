from __future__ import annotations

import pytest

from app.graph import build_graph
from tests.fakes import FakeLaravelToolClient, base_state


@pytest.mark.asyncio
async def test_fraud_analyzer_calls_deterministic_laravel_risk_summary_tool() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state())

    assert tool_client.risk_summary_calls == [
        {"company_id": "company-1", "user_id": "user-1", "period": "2026-05"}
    ]
    assert result["findings"][0]["title"] == "Possible unusual vendor pattern"
    assert result["findings"][0]["severity"] == "medium"
    assert result["findings"][0]["evidence"] == [{"type": "alert", "id": "alert-1"}]
    assert result["tool_results"]["risk_summary"]["risk_score"] == 74
    assert result["recommended_actions"][0]["type"] == "review_findings"
