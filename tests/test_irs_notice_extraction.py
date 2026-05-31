"""Tests for Phase 3 IRS notice extraction routing and synthesis."""

from __future__ import annotations

import pytest

from app.graph import build_graph
from app.irs_procedural import (
    IrsToolRequest,
    classify_irs_tool_request,
    synthesize_irs_answer,
    synthesize_irs_notice_workflow,
)
from tests.fakes import FakeLaravelToolClient, base_state

# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------


def test_notice_text_submission_trigger_routes_to_extraction() -> None:
    request = classify_irs_tool_request(
        "My notice says I owe $5,000 and must respond within 30 days. It's a CP504 notice."
    )
    assert request.tool_name == "irs_notice_extract"


def test_long_notice_body_routes_to_extraction() -> None:
    long_notice = (
        "IRS Notice CP504 — Urgent. This notice informs you that the IRS intends to levy your state tax "
        "refunds and other property because you have an unpaid balance. The amount owed is $8,432.15 "
        "including interest and penalties. You must respond within 30 days from the date of this notice "
        "or the levy will proceed. To prevent levy action, pay the full amount, establish an installment "
        "agreement, or contact the IRS to discuss collection alternatives."
    )
    request = classify_irs_tool_request(long_notice)
    assert request.tool_name == "irs_notice_extract"
    assert long_notice.strip() == request.query


def test_short_notice_code_question_does_not_route_to_extraction() -> None:
    request = classify_irs_tool_request("What is CP504?")
    assert request.tool_name == "irs_notice_type"
    assert request.query == "CP504"


def test_irm_reference_still_routes_to_section_lookup() -> None:
    request = classify_irs_tool_request("Look up IRM 5.11.1.1.")
    assert request.tool_name == "irm_section"


# ---------------------------------------------------------------------------
# Synthesis tests
# ---------------------------------------------------------------------------

_EXTRACTION_PAYLOAD = {
    "status": "ok",
    "notice_type": "CP504",
    "deadline_days": 30,
    "deadline_description": "30-day window from notice date",
    "required_action": "Pay in full or file Form 9465 to stop levy action.",
    "risk_level": "critical",
    "key_amount": 5000.0,
    "summary": "CP504 is an urgent notice of intent to levy state tax refunds.",
    "irm_search_topic": "levy notice intent to levy balance due collection",
    "results": [
        {
            "irm_reference": "5.11.1.1",
            "section_title": "Notice of Levy",
            "excerpt": "A levy is a legal seizure of property to satisfy a tax debt.",
        }
    ],
    "disclaimer": "For informational purposes only.",
}


def test_synthesis_includes_notice_type_and_risk_level() -> None:
    request = IrsToolRequest(tool_name="irs_notice_extract", query="pasted notice text")
    answer = synthesize_irs_answer(request, _EXTRACTION_PAYLOAD)
    assert "CP504" in answer
    assert "critical" in answer


def test_synthesis_includes_irm_reference() -> None:
    request = IrsToolRequest(tool_name="irs_notice_extract", query="pasted notice text")
    answer = synthesize_irs_answer(request, _EXTRACTION_PAYLOAD)
    assert "irm_reference:" in answer
    assert "5.11.1.1" in answer


def test_synthesis_includes_disclaimer() -> None:
    request = IrsToolRequest(tool_name="irs_notice_extract", query="pasted notice text")
    answer = synthesize_irs_answer(request, _EXTRACTION_PAYLOAD)
    assert "Disclaimer:" in answer


def test_synthesis_includes_deadline_and_action() -> None:
    request = IrsToolRequest(tool_name="irs_notice_extract", query="pasted notice text")
    answer = synthesize_irs_answer(request, _EXTRACTION_PAYLOAD)
    assert "30-day window" in answer
    assert "Form 9465" in answer


def test_synthesis_includes_notice_workflow_guidance() -> None:
    request = IrsToolRequest(tool_name="irs_notice_extract", query="pasted notice text")
    payload = {**_EXTRACTION_PAYLOAD, "workflow": synthesize_irs_notice_workflow(_EXTRACTION_PAYLOAD)}
    answer = synthesize_irs_answer(request, payload)
    assert "Workflow next steps:" in answer
    assert "Evidence to gather:" in answer
    assert "Escalation criteria:" in answer


def test_synthesis_unknown_notice_falls_back_to_no_source_response() -> None:
    request = IrsToolRequest(tool_name="irs_notice_extract", query="pasted notice text")
    payload = {
        "status": "ok",
        "notice_type": "Unknown",
        "deadline_days": None,
        "deadline_description": "See notice for deadline details.",
        "required_action": "Review notice and consult a tax professional.",
        "risk_level": "medium",
        "key_amount": None,
        "summary": "",
        "irm_search_topic": None,
        "results": [],
        "disclaimer": "For informational purposes only.",
    }
    answer = synthesize_irs_answer(request, payload)
    assert "irm_reference: none returned" in answer
    assert "Disclaimer:" in answer


# ---------------------------------------------------------------------------
# Graph integration test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_graph_routes_notice_text_to_extraction_and_returns_irm_reference() -> None:
    tool_client = FakeLaravelToolClient()
    graph = build_graph(tool_client)

    long_notice = (
        "IRS Notice CP504 — my notice says I owe $5,000 and must respond within 30 days. "
        "This notice informs you that the IRS intends to levy your state tax refunds because you "
        "have an unpaid balance. Pay in full or establish an installment agreement to prevent levy."
    )
    result = await graph.ainvoke(base_state(long_notice))

    assert result["intent"] == "irs_procedural_question"
    assert tool_client.irs_notice_extract_calls, "Expected irs_notice_extract to be called"
    assert result["recommended_workflow"] == "irs_notice_review"
    assert result["next_best_action"]["type"] == "prepare_irs_notice_review"
    assert result["recommended_actions"][0]["type"] == "prepare_irs_notice_review"
    assert result["tool_results"]["irs_notice_workflow"]["review_priority"] == "critical"
    assert "irm_reference:" in result["final_response"]
    assert "Workflow next steps:" in result["final_response"]
    assert "Disclaimer:" in result["final_response"]
