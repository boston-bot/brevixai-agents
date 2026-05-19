from __future__ import annotations

import pytest

from app.graph import build_graph
from app.investigation_synthesis import synthesize_investigation
from app.models import AgentRunResponse
from tests.fakes import FixtureLaravelToolClient, base_state


def _multi_domain_fixture() -> dict:
    return {
        "risk_summary": {
            "risk_score": 88,
            "risk_level": "high",
            "top_drivers": [
                {
                    "driver": "Employee-vendor overlap pattern",
                    "description": "Vendor and employee records share a deterministic entity anchor.",
                    "severity": "high",
                    "evidence": [
                        {"type": "vendor", "id": "vendor-overlap-001", "vendor_id": "vendor-overlap-001"},
                        {"type": "transaction", "id": "txn-overlap-001", "vendor_id": "vendor-overlap-001"},
                    ],
                }
            ],
        },
        "vendor_risk": {
            "vendor_name": "Overlap Vendor LLC",
            "vendor_id": "vendor-overlap-001",
            "vendor_risk_score": 84,
            "risk_level": "high",
            "triggered_rules": ["high vendor risk", "employee-vendor overlap"],
            "supporting_evidence": [
                {"type": "vendor", "id": "vendor-overlap-001", "vendor_id": "vendor-overlap-001"},
                {"type": "transaction", "id": "txn-overlap-001", "vendor_id": "vendor-overlap-001"},
            ],
            "recommended_next_action": "Review vendor relationship evidence.",
        },
        "entity_relationship_risk": {
            "entity_relationship_risk_score": 82,
            "risk_level": "high",
            "triggered_rules": ["employee-vendor overlap"],
            "supporting_evidence": [
                {"type": "vendor", "id": "vendor-overlap-001", "vendor_id": "vendor-overlap-001"},
                {"type": "employee_record", "id": "emp-overlap-001", "vendor_id": "vendor-overlap-001"},
            ],
            "related_entities": [
                {"type": "entity_relationship", "id": "rel-overlap-001", "vendor_id": "vendor-overlap-001"},
            ],
            "recommended_next_action": "Validate relationship and approval chain.",
        },
        "aggregate_risk_summary": {
            "overall_risk_score": 86,
            "overall_risk_level": "high",
            "supporting_evidence": [
                {"type": "domain_score", "id": "agg-vendor-entity-001", "score": 86},
            ],
        },
    }


@pytest.mark.asyncio
async def test_synthesis_combines_multiple_deterministic_domains_correctly() -> None:
    graph = build_graph(FixtureLaravelToolClient(_multi_domain_fixture()))

    result = await graph.ainvoke(base_state("Review high vendor risk with entity overlap."))

    synthesis = result["investigative_synthesis"]
    patterns = {finding["pattern"] for finding in synthesis["correlated_findings"]}

    assert "vendor_entity_overlap" in patterns
    assert synthesis["investigation_priority"] == "high"
    assert {"vendor_risk", "entity_relationship_risk"}.issubset(set(synthesis["supporting_domains"]))
    assert synthesis["recommended_investigation_focus"]


def test_unsupported_correlations_are_rejected() -> None:
    synthesis = synthesize_investigation(
        {
            "vendor_risk": {
                "vendor_name": "Unrelated Vendor A",
                "vendor_id": "vendor-a",
                "vendor_risk_score": 85,
                "risk_level": "high",
                "triggered_rules": ["high vendor risk"],
                "supporting_evidence": [{"type": "vendor", "id": "vendor-a", "vendor_id": "vendor-a"}],
            },
            "entity_relationship_risk": {
                "entity_relationship_risk_score": 82,
                "risk_level": "high",
                "triggered_rules": ["employee-vendor overlap"],
                "supporting_evidence": [{"type": "employee_record", "id": "emp-b", "employee_id": "emp-b"}],
            },
        }
    )

    patterns = {finding["pattern"] for finding in synthesis.correlated_findings}
    conflict_types = {signal["type"] for signal in synthesis.conflicting_signals}

    assert "vendor_entity_overlap" not in patterns
    assert "unsupported_correlation_suppressed" in conflict_types


def test_conflicting_signals_are_surfaced() -> None:
    synthesis = synthesize_investigation(
        {
            "vendor_risk": {
                "vendor_name": "High Risk Vendor",
                "vendor_id": "vendor-high-001",
                "vendor_risk_score": 86,
                "risk_level": "high",
                "triggered_rules": ["high vendor risk"],
                "supporting_evidence": [
                    {"type": "vendor", "id": "vendor-high-001", "vendor_id": "vendor-high-001"}
                ],
            },
            "entity_relationship_risk": {
                "entity_relationship_risk_score": 12,
                "risk_level": "low",
                "triggered_rules": [],
                "supporting_evidence": [{"type": "entity_scan", "id": "entity-clear-001"}],
            },
        }
    )

    conflict_types = {signal["type"] for signal in synthesis.conflicting_signals}
    assert "vendor_risk_not_reinforced_by_entity_graph" in conflict_types


def test_synthesis_remains_evidence_linked() -> None:
    synthesis = synthesize_investigation(_multi_domain_fixture())
    correlated = next(
        finding for finding in synthesis.correlated_findings
        if finding["pattern"] == "vendor_entity_overlap"
    )
    evidence_domains = {item["domain"] for item in correlated["evidence"]}

    assert correlated["evidence"]
    assert set(correlated["domains"]).issubset(evidence_domains)
    assert synthesis.evidence_summary


@pytest.mark.asyncio
async def test_synthesis_triggers_no_autonomous_actions() -> None:
    graph = build_graph(FixtureLaravelToolClient(_multi_domain_fixture()))

    result = await graph.ainvoke(base_state("Review high vendor risk with entity overlap."))

    action_types = {action["type"] for action in result["recommended_actions"]}
    assert "create_alert" not in action_types
    assert "create_case" not in action_types
    assert result["recommended_actions"] == [
        {"type": "review_findings", "label": "Review findings", "requires_approval": False, "payload": {"finding_count": 3}}
    ]


@pytest.mark.asyncio
async def test_synthesis_response_contract_and_observability_metadata() -> None:
    graph = build_graph(FixtureLaravelToolClient(_multi_domain_fixture()))
    result = await graph.ainvoke(base_state("Review high vendor risk with entity overlap."))

    response = AgentRunResponse(
        trace_id=result.get("agent_run_id"),
        intent=result.get("intent"),
        message=result.get("final_response") or "",
        findings=result.get("findings", []),
        investigative_synthesis=result.get("investigative_synthesis", {}),
        recommended_actions=result.get("recommended_actions", []),
        steps=result.get("steps", []),
        errors=result.get("errors", []),
    )
    synthesis = response.investigative_synthesis
    assert synthesis.investigative_summary
    assert isinstance(synthesis.correlated_findings, list)
    assert synthesis.investigation_priority in {"low", "medium", "high", "critical"}

    synthesis_step = next(step for step in result["steps"] if step["step_name"] == "investigation_synthesis")
    payload = synthesis_step["output_payload"]
    assert payload["source_domains_used"]
    assert payload["prompt_name"] == "investigation_synthesis"
    assert len(payload["prompt_hash"]) == 64
    assert payload["synthesis_latency_ms"] >= 0.0
    assert payload["provider_name"] == "deterministic"
