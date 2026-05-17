"""Benchmark report generator for Brevix AI fraud evaluation results."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class BenchmarkReport:
    generated_at: str
    total_scenarios: int
    total_passed: int
    total_failed: int
    pass_rate: float
    failed_scenario_ids: list[str]
    failed_evaluator_names: list[str]
    severity_accuracy: float
    evidence_completeness_avg: float
    false_positive_pass_rate: float
    hallucination_failure_count: int
    average_latency_ms: float
    slowest_scenarios: list[dict[str, Any]]
    scenario_breakdown: list[dict[str, Any]]
    known_gaps: list[str]
    next_improvements: list[str]


def generate_report(results: list[dict[str, Any]]) -> BenchmarkReport:
    """Build a BenchmarkReport from a list of scenario result dicts."""
    if not results:
        return BenchmarkReport(
            generated_at=_now(),
            total_scenarios=0,
            total_passed=0,
            total_failed=0,
            pass_rate=0.0,
            failed_scenario_ids=[],
            failed_evaluator_names=[],
            severity_accuracy=0.0,
            evidence_completeness_avg=0.0,
            false_positive_pass_rate=0.0,
            hallucination_failure_count=0,
            average_latency_ms=0.0,
            slowest_scenarios=[],
            scenario_breakdown=[],
            known_gaps=_known_gaps(),
            next_improvements=_next_improvements(),
        )

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])

    failed_ids = [r["scenario_id"] for r in results if not r["passed"]]
    failed_evaluator_names = sorted({
        check["name"]
        for r in results
        for check in r.get("checks", [])
        if not check["passed"]
    })

    severity_scores = _collect_scores(results, "severity_correctness")
    severity_accuracy = _avg(severity_scores)

    evidence_scores = _collect_scores(results, "evidence_completeness")
    evidence_completeness_avg = _avg(evidence_scores)

    fp_scores = _collect_scores(results, "false_positive_rate")
    false_positive_pass_rate = _avg(fp_scores)

    hallucination_failures = sum(
        1
        for r in results
        for check in r.get("checks", [])
        if check["name"] == "hallucination_detection" and not check["passed"]
    )

    latencies = [r["latency_ms"] for r in results]
    average_latency_ms = _avg(latencies)
    slowest = sorted(results, key=lambda r: r["latency_ms"], reverse=True)[:5]
    slowest_scenarios = [
        {"scenario_id": r["scenario_id"], "latency_ms": r["latency_ms"]}
        for r in slowest
    ]

    scenario_breakdown = [
        {
            "scenario_id": r["scenario_id"],
            "passed": r["passed"],
            "latency_ms": r["latency_ms"],
            "failed_checks": [c["name"] for c in r.get("checks", []) if not c["passed"]],
            "check_scores": {c["name"]: c["score"] for c in r.get("checks", [])},
        }
        for r in results
    ]

    return BenchmarkReport(
        generated_at=_now(),
        total_scenarios=total,
        total_passed=passed_count,
        total_failed=total - passed_count,
        pass_rate=round(passed_count / total, 4),
        failed_scenario_ids=failed_ids,
        failed_evaluator_names=failed_evaluator_names,
        severity_accuracy=round(severity_accuracy, 4),
        evidence_completeness_avg=round(evidence_completeness_avg, 4),
        false_positive_pass_rate=round(false_positive_pass_rate, 4),
        hallucination_failure_count=hallucination_failures,
        average_latency_ms=round(average_latency_ms, 2),
        slowest_scenarios=slowest_scenarios,
        scenario_breakdown=scenario_breakdown,
        known_gaps=_known_gaps(),
        next_improvements=_next_improvements(),
    )


def report_to_json(report: BenchmarkReport) -> str:
    return json.dumps(asdict(report), indent=2)


def report_to_markdown(report: BenchmarkReport) -> str:
    r = report
    lines: list[str] = []

    lines += [
        "# Brevix AI Benchmark Report",
        "",
        f"Generated: {r.generated_at}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Scenarios | {r.total_scenarios} |",
        f"| Total Passed | {r.total_passed} |",
        f"| Total Failed | {r.total_failed} |",
        f"| Pass Rate | {r.pass_rate:.1%} |",
        f"| Severity Accuracy | {r.severity_accuracy:.1%} |",
        f"| Evidence Completeness (avg) | {r.evidence_completeness_avg:.1%} |",
        f"| False Positive Clean Rate | {r.false_positive_pass_rate:.1%} |",
        f"| Hallucination Failures | {r.hallucination_failure_count} |",
        f"| Average Latency | {r.average_latency_ms:.1f} ms |",
        "",
    ]

    lines += [
        "## Scenario Breakdown",
        "",
        "| Scenario | Status | Latency (ms) | Failed Checks |",
        "|----------|--------|--------------|---------------|",
    ]
    for s in r.scenario_breakdown:
        status = "PASS" if s["passed"] else "FAIL"
        failed = ", ".join(s["failed_checks"]) if s["failed_checks"] else "—"
        lines.append(f"| {s['scenario_id']} | {status} | {s['latency_ms']} | {failed} |")
    lines.append("")

    lines += [
        "## Slowest Scenarios",
        "",
        "| Scenario | Latency (ms) |",
        "|----------|--------------|",
    ]
    for s in r.slowest_scenarios:
        lines.append(f"| {s['scenario_id']} | {s['latency_ms']} |")
    lines.append("")

    lines += ["## Failed Checks", ""]
    if r.total_failed == 0:
        lines.append("All scenarios passed. No failures to report.")
    else:
        lines += [
            f"**Failed Scenario IDs:** {', '.join(r.failed_scenario_ids)}",
            "",
            f"**Failed Evaluator Names:** {', '.join(r.failed_evaluator_names)}",
            "",
        ]
        for s in r.scenario_breakdown:
            if not s["passed"]:
                lines.append(f"### {s['scenario_id']}")
                for check_name in s["failed_checks"]:
                    score = s["check_scores"].get(check_name, 0.0)
                    lines.append(f"- `{check_name}` (score: {score:.2f})")
                lines.append("")
    lines.append("")

    lines += ["## Known Gaps", ""]
    for gap in r.known_gaps:
        lines.append(f"- {gap}")
    lines.append("")

    lines += ["## Next Recommended Improvements", ""]
    for improvement in r.next_improvements:
        lines.append(f"- {improvement}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collect_scores(results: list[dict[str, Any]], check_name: str) -> list[float]:
    return [
        check["score"]
        for r in results
        for check in r.get("checks", [])
        if check["name"] == check_name
    ]


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _known_gaps() -> list[str]:
    return [
        "No LLM-based evaluators — all checks are deterministic; nuanced reasoning quality is unmeasured.",
        "Latency benchmarks use the deterministic model provider; real LLM latency will differ significantly.",
        "Dataset covers 16 scenarios; edge cases like multi-fraud overlaps are not yet represented.",
        "No cross-scenario confusion testing (a scenario triggering a different scenario's pattern).",
        "Evidence ID validation relies on tool fixture; does not test evidence retrieval accuracy end-to-end.",
    ]


def _next_improvements() -> list[str]:
    return [
        "Add LLM-as-judge evaluation for response reasoning quality and explanation clarity.",
        "Expand dataset to cover compound fraud patterns (e.g., duplicate + split threshold).",
        "Add latency benchmarks against the real model provider to establish production SLOs.",
        "Introduce mutation testing: perturb fixtures to verify evaluators catch regressions.",
        "Add a trend report comparing multiple eval runs over time to surface score drift.",
    ]
