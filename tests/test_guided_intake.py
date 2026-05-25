from __future__ import annotations

import pytest

from app.graph import build_graph
from tests.fakes import FakeLaravelToolClient, FixtureLaravelToolClient, base_state

_PARTIAL_FIXTURE = {
    "onboarding_context": {
        "session_status": "in_progress",
        "primary_intent": "suspected_fraud",
        "current_step": "evidence_checklist",
        "scope_mode": "partial",
        "organization_type": "youth sports team",
    },
    "evidence_requirements": {
        "items": [
            {
                "requirement_key": "transaction_ledger",
                "label": "Transaction ledger",
                "reason": "Ledger confirms who approved each payment.",
                "priority": "required",
                "status": "missing",
            },
            {
                "requirement_key": "bank_statements",
                "label": "Bank statements",
                "priority": "required",
                "status": "received",
            },
        ]
    },
    "data_source_status": {
        "sources": [{"type": "file_upload", "label": "Bank export", "status": "validated", "record_count": 247}],
        "total_sources": 1,
    },
    "first_snapshot": {
        "data_readiness_score": 35,
        "review_scope": "partial",
        "available_sources": ["bank_export"],
        "missing_evidence": ["transaction_ledger"],
        "risk_indicators": [
            {
                "driver": "Personal-looking purchase pattern",
                "description": "Transactions appear inconsistent with organizational activity.",
                "severity": "medium",
                "evidence": [
                    {"type": "transaction", "id": "txn-personal-001"},
                    {"type": "evidence_gap", "id": "gap-transaction-ledger"},
                ],
            }
        ],
        "data_quality_issues": [],
        "recommended_next_action": {
            "type": "upload_ledger",
            "label": "Upload your transaction ledger to improve review confidence.",
        },
    },
}

_NO_EVIDENCE_FIXTURE = {
    "onboarding_context": {
        "session_status": "in_progress",
        "primary_intent": "routine_books_review",
        "current_step": "evidence_checklist",
        "scope_mode": "partial",
        "organization_type": "business",
    },
    "evidence_requirements": {
        "items": [
            {"requirement_key": "transaction_ledger", "label": "Transaction ledger", "priority": "required", "status": "missing"},
        ]
    },
    "data_source_status": {"sources": [], "total_sources": 0},
    "first_snapshot": {
        "data_readiness_score": 0,
        "review_scope": "none",
        "available_sources": [],
        "missing_evidence": ["transaction_ledger"],
        "risk_indicators": [],
        "data_quality_issues": [],
        "recommended_next_action": {
            "type": "upload_ledger",
            "label": "Upload your transaction ledger to begin.",
        },
    },
}


@pytest.mark.asyncio
async def test_router_classifies_guided_intake_onboarding_prompt() -> None:
    graph = build_graph(FakeLaravelToolClient())
    result = await graph.ainvoke(base_state("Check evidence readiness and what data is still missing."))
    assert result["intent"] == "guided_intake"


@pytest.mark.asyncio
async def test_router_classifies_guided_intake_first_snapshot_prompt() -> None:
    graph = build_graph(FakeLaravelToolClient())
    result = await graph.ainvoke(base_state("Run my first snapshot to see where I stand."))
    assert result["intent"] == "guided_intake"


@pytest.mark.asyncio
async def test_guided_intake_builds_findings_from_risk_indicators() -> None:
    graph = build_graph(FixtureLaravelToolClient(_PARTIAL_FIXTURE))
    result = await graph.ainvoke(base_state("Check evidence readiness for suspected missing funds."))

    assert result["intent"] == "guided_intake"
    assert len(result["findings"]) == 1
    assert "personal-looking purchase" in result["findings"][0]["title"].lower()
    assert result["findings"][0]["severity"] == "medium"


@pytest.mark.asyncio
async def test_guided_intake_populates_evidence_gaps() -> None:
    graph = build_graph(FixtureLaravelToolClient(_PARTIAL_FIXTURE))
    result = await graph.ainvoke(base_state("Check evidence readiness for suspected missing funds."))

    gaps = result["evidence_gaps"]
    assert len(gaps) == 1
    assert gaps[0]["requirement_key"] == "transaction_ledger"
    assert gaps[0]["status"] == "missing"


@pytest.mark.asyncio
async def test_guided_intake_populates_scope_limitations_for_partial_scope() -> None:
    graph = build_graph(FixtureLaravelToolClient(_PARTIAL_FIXTURE))
    result = await graph.ainvoke(base_state("Check evidence readiness for suspected missing funds."))

    limitations = result["scope_limitations"]
    assert any("scope-limited" in lim.lower() for lim in limitations)
    assert any("transaction ledger" in lim.lower() for lim in limitations)


@pytest.mark.asyncio
async def test_guided_intake_populates_readiness_summary() -> None:
    graph = build_graph(FixtureLaravelToolClient(_PARTIAL_FIXTURE))
    result = await graph.ainvoke(base_state("Check evidence readiness for suspected missing funds."))

    summary = result["readiness_summary"]
    assert summary is not None
    assert summary["data_readiness_score"] == 35
    assert summary["review_scope"] == "partial"
    assert summary["primary_intent"] == "suspected_fraud"


@pytest.mark.asyncio
async def test_guided_intake_populates_next_best_action() -> None:
    graph = build_graph(FixtureLaravelToolClient(_PARTIAL_FIXTURE))
    result = await graph.ainvoke(base_state("Check evidence readiness for suspected missing funds."))

    assert result["next_best_action"] is not None
    assert result["next_best_action"]["type"] == "upload_ledger"


@pytest.mark.asyncio
async def test_guided_intake_falls_back_to_evidence_gap_finding_when_no_risk_indicators() -> None:
    graph = build_graph(FixtureLaravelToolClient(_NO_EVIDENCE_FIXTURE))
    result = await graph.ainvoke(base_state("Check what evidence is still missing."))

    assert result["intent"] == "guided_intake"
    assert len(result["findings"]) == 1
    assert "evidence gaps" in result["findings"][0]["title"].lower()
    assert result["findings"][0]["severity"] == "info"
    assert any(e.get("type") == "evidence_gap" for e in result["findings"][0]["evidence"])


@pytest.mark.asyncio
async def test_guided_intake_final_response_includes_readiness_and_next_step() -> None:
    graph = build_graph(FixtureLaravelToolClient(_PARTIAL_FIXTURE))
    result = await graph.ainvoke(base_state("Check evidence readiness for suspected missing funds."))

    response = result["final_response"] or ""
    assert "35/100" in response
    assert "partial" in response.lower()
    assert "upload" in response.lower()


@pytest.mark.asyncio
async def test_guided_intake_final_response_does_not_declare_fraud() -> None:
    graph = build_graph(FixtureLaravelToolClient(_PARTIAL_FIXTURE))
    result = await graph.ainvoke(base_state("Check evidence readiness for suspected missing funds."))

    response = (result["final_response"] or "").lower()
    for prohibited in ("committed fraud", "is fraud", "stole", "theft confirmed", "proven fraud"):
        assert prohibited not in response, f"Prohibited phrase found: {prohibited!r}"


@pytest.mark.asyncio
async def test_guided_intake_recommended_action_uses_next_best_action_type() -> None:
    graph = build_graph(FixtureLaravelToolClient(_PARTIAL_FIXTURE))
    result = await graph.ainvoke(base_state("Check evidence readiness for suspected missing funds."))

    actions = result["recommended_actions"]
    assert len(actions) == 1
    assert actions[0]["type"] == "upload_ledger"
    assert actions[0]["requires_approval"] is False


@pytest.mark.asyncio
async def test_guided_intake_steps_include_fraud_analyzer() -> None:
    graph = build_graph(FixtureLaravelToolClient(_PARTIAL_FIXTURE))
    result = await graph.ainvoke(base_state("Check evidence readiness for suspected missing funds."))

    step_names = [s["step_name"] for s in result["steps"]]
    assert "router" in step_names
    assert "fraud_analyzer" in step_names
    assert "explanation" in step_names
