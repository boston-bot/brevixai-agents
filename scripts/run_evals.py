"""Local regression runner for Brevix AI fraud benchmark scenarios.

Usage:
    python scripts/run_evals.py
    python scripts/run_evals.py --output path/to/results.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.graph import build_graph
from app.observability import summarize_usage
from evaluators import run_deterministic_evaluators
from tests.fakes import FixtureLaravelToolClient

DATASET_PATH = Path(__file__).parent.parent / "datasets" / "fraud_benchmarks.json"
DEFAULT_RESULTS_DIR = Path(__file__).parent.parent / "datasets" / "eval_results"


def _normalize(result: dict) -> dict:
    return {
        "trace_id": result.get("agent_run_id"),
        "intent": result.get("intent"),
        "message": result.get("final_response") or "",
        "findings": result.get("findings", []),
        "recommended_actions": result.get("recommended_actions", []),
        "steps": result.get("steps", []),
        "errors": result.get("errors", []),
        "usage": result.get("usage", {}),
    }


async def _run_scenario(scenario: dict, settings) -> dict:
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
        "recommended_actions": [],
        "errors": [],
        "steps": [],
    }

    start = time.perf_counter()
    result = await graph.ainvoke(state)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    result["usage"] = summarize_usage(result, latency_ms, settings)
    normalized = _normalize(result)
    checks = run_deterministic_evaluators(normalized, scenario)

    return {
        "scenario_id": scenario["id"],
        "latency_ms": latency_ms,
        "passed": all(c.passed for c in checks),
        "checks": [c.to_dict() for c in checks],
        "errors": result.get("errors", []),
    }


async def run_all(dataset: list[dict], settings) -> list[dict]:
    results = []
    for scenario in dataset:
        results.append(await _run_scenario(scenario, settings))
    return results


# Alias kept for any direct callers that used the private name.
_run_all = run_all


def _print_report(results: list[dict]) -> None:
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total - passed_count

    print(f"\n{'=' * 60}")
    print(f"Brevix Fraud Benchmark  {passed_count}/{total} passed")
    print(f"{'=' * 60}")

    for r in results:
        label = "PASS" if r["passed"] else "FAIL"
        print(f"\n[{label}] {r['scenario_id']}  ({r['latency_ms']}ms)")
        for check in r["checks"]:
            icon = "+" if check["passed"] else "!"
            print(f"  {icon} {check['name']}: {check['details']}")
        for err in r.get("errors", []):
            print(f"  ERROR: {err}")

    print(f"\n{'=' * 60}")
    print(f"Total: {total}  Passed: {passed_count}  Failed: {failed_count}")
    if failed_count:
        failed_ids = [r["scenario_id"] for r in results if not r["passed"]]
        print(f"Failed: {failed_ids}")
    print(f"{'=' * 60}\n")


def _save_results(results: list[dict], output_path: Path | None) -> Path:
    if output_path is None:
        DEFAULT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = DEFAULT_RESULTS_DIR / f"eval_{ts}.json"
    with output_path.open("w") as f:
        json.dump(results, f, indent=2)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Brevix fraud benchmark evaluations.")
    parser.add_argument("--output", type=Path, default=None, help="Path to write JSON results.")
    args = parser.parse_args(argv)

    with DATASET_PATH.open() as f:
        dataset = json.load(f)

    settings = get_settings()
    results = asyncio.run(run_all(dataset, settings))
    _print_report(results)

    out_path = _save_results(results, args.output)
    print(f"Results saved to {out_path}")

    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
