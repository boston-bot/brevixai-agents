"""CI pytest wrapper for fraud benchmark evaluations.

Run with:  pytest tests/test_evals.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import get_settings
from app.graph import build_graph
from app.observability import summarize_usage
from evaluators import run_deterministic_evaluators
from tests.fakes import FixtureLaravelToolClient

_DATASET_PATH = Path(__file__).parent.parent / "datasets" / "fraud_benchmarks.json"


def _load_scenarios() -> list[dict]:
    with _DATASET_PATH.open() as f:
        return json.load(f)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", _load_scenarios(), ids=lambda s: s["id"])
async def test_fraud_benchmark(scenario: dict) -> None:
    settings = get_settings()
    tool_client = FixtureLaravelToolClient(scenario["tool_fixture"])
    graph = build_graph(tool_client, settings=settings)

    state = {
        "agent_run_id": f"eval-{scenario['id']}",
        "company_id": "eval-company",
        "user_id": "eval-user",
        "user_message": scenario["input_prompt"],
        "page_context": scenario.get("page_context", {}),
        "tool_results": {},
        "findings": [],
        "investigative_synthesis": {},
        "recommended_actions": [],
        "errors": [],
        "steps": [],
    }

    result = await graph.ainvoke(state)

    import time  # noqa: PLC0415
    result["usage"] = summarize_usage(result, 0.0, settings)

    normalized = {
        "trace_id": result.get("agent_run_id"),
        "intent": result.get("intent"),
        "message": result.get("final_response") or "",
        "findings": result.get("findings", []),
        "investigative_synthesis": result.get("investigative_synthesis", {}),
        "recommended_actions": result.get("recommended_actions", []),
        "steps": result.get("steps", []),
        "errors": result.get("errors", []),
        "usage": result.get("usage", {}),
    }

    checks = run_deterministic_evaluators(normalized, scenario)
    failures = [c for c in checks if not c.passed]

    assert not failures, (
        f"Scenario '{scenario['id']}' failed {len(failures)} check(s):\n"
        + "\n".join(f"  {c.name}: {c.details}" for c in failures)
    )
