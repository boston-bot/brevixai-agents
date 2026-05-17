from __future__ import annotations

import pytest

from app.graph import build_graph


class FakeLaravelToolClient:
    async def company_context(self, company_id: str, user_id: str) -> dict:
        return {
            "company_id": company_id,
            "company_name": "Brevix Test Co",
            "industry": "Retail",
            "available_data_sources": ["file_upload"],
            "user_role": "owner",
        }

    async def risk_summary(self, company_id: str, user_id: str, period: str | None = None) -> dict:
        return {
            "company_id": company_id,
            "risk_score": 74,
            "risk_level": "high",
            "period": period or "2026-05",
            "top_drivers": [
                {
                    "driver": "Possible unusual vendor pattern",
                    "description": "Open alerts are driving the risk score.",
                    "severity": "medium",
                    "evidence": [{"type": "alert", "id": "alert-1"}],
                }
            ],
        }


@pytest.mark.asyncio
async def test_graph_routes_fraud_request_through_deterministic_risk_tool() -> None:
    graph = build_graph(FakeLaravelToolClient())

    result = await graph.ainvoke(
        {
            "company_id": "company-1",
            "user_id": "user-1",
            "user_message": "Are there any suspicious vendors this month?",
            "page_context": {"selected_period": "2026-05"},
            "tool_results": {},
            "findings": [],
            "recommended_actions": [],
            "errors": [],
            "steps": [],
        }
    )

    assert result["intent"] == "fraud_pattern_search"
    assert result["findings"][0]["title"] == "Possible unusual vendor pattern"
    assert "does not prove fraud" in result["final_response"]
    assert result["recommended_actions"][0]["requires_approval"] is False
    assert [step["step_name"] for step in result["steps"]] == [
        "router",
        "context_loader",
        "fraud_analyzer",
        "explanation",
        "action_gate",
        "final_response",
    ]
