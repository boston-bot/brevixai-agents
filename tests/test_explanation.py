from __future__ import annotations

import pytest

from app.graph import build_graph
from tests.fakes import FakeLaravelToolClient, base_state


@pytest.mark.asyncio
async def test_explanation_node_uses_safe_non_accusatory_language() -> None:
    graph = build_graph(FakeLaravelToolClient())

    result = await graph.ainvoke(base_state("Check for fraud risk."))

    assert "may indicate" in result["final_response"]
    assert "does not prove fraud" in result["final_response"]
    assert "committed fraud" not in result["final_response"].lower()
    assert "No alerts or cases were created." in result["final_response"]
