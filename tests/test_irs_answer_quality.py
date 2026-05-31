from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.graph import build_graph
from tests.fakes import FixtureLaravelToolClient, base_state

_FIXTURES_PATH = Path(__file__).parent.parent / "datasets" / "irs_answer_quality_fixtures.json"


def _load_fixtures() -> list[dict]:
    with _FIXTURES_PATH.open() as f:
        return json.load(f)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", _load_fixtures(), ids=lambda s: s["id"])
async def test_irs_answer_quality_fixtures(scenario: dict) -> None:
    tool_client = FixtureLaravelToolClient(scenario["tool_fixture"])
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state(scenario["input_prompt"]))
    message = result["final_response"]

    assert result["intent"] == "irs_procedural_question"
    assert "irm_reference:" in message
    assert "Disclaimer:" in message
    assert "not tax, legal, or accounting advice" in message
    expected_action = scenario.get("expected_recommended_action")
    if expected_action:
        assert result["recommended_actions"][0]["type"] == expected_action
    else:
        assert result["recommended_actions"] == []

    irs_step = next(step for step in result["steps"] if step["step_name"] == "irs_knowledge")
    assert irs_step["input_payload"]["tool"] == scenario["expected_tool"]
    assert irs_step["input_payload"]["query"] == scenario["expected_query"]

    if scenario.get("expect_empty"):
        assert "No source-backed IRM result was returned" in message
        assert "I do not have enough retrieved IRM support to give procedural guidance" in message
        assert "Records to gather:" not in message
        assert "procedural summary:" not in message
    else:
        assert scenario["expected_irm_reference"] in message

    if scenario.get("expected_workflow"):
        assert result["recommended_workflow"] == scenario["expected_workflow"]
        assert "Workflow next steps:" in message


@pytest.mark.asyncio
async def test_exact_irm_section_rejects_mismatched_reference() -> None:
    tool_client = FixtureLaravelToolClient(
        {
            "irm_section": {
                "result": {
                    "irm_reference": "5.11.1.2",
                    "title": "Wrong section",
                    "summary": "This should not be used for an exact section response.",
                }
            }
        }
    )
    graph = build_graph(tool_client)

    result = await graph.ainvoke(base_state("Look up IRM 5.11.1.1."))

    assert "No source-backed IRM result was returned" in result["final_response"]
    assert "irm_reference: none returned" in result["final_response"]
    assert "Wrong section" not in result["final_response"]
