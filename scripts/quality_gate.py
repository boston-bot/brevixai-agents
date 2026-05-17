"""CI quality gate for Brevix AI benchmark regression detection.

Runs the benchmark suite (or reads an existing report) and exits with code 1
if any metric falls below its configured threshold.

Usage:
    # Run benchmarks fresh, then check gates
    python scripts/quality_gate.py

    # Check gates against a previously generated report
    python scripts/quality_gate.py --report-json reports/latest_benchmark_report.json

    # Run a filtered subset, then check gates
    python scripts/quality_gate.py --tag vendor --severity high

    # Override individual thresholds
    python scripts/quality_gate.py --min-pass-rate 1.0 --max-average-latency-ms 100
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluators.dataset import build_active_filters, filter_dataset, load_dataset
from evaluators.report import BenchmarkReport, generate_report, report_to_json
from scripts.run_evals import DATASET_PATH, run_all

REPORTS_DIR = Path(__file__).parent.parent / "reports"
_COL = 28  # metric column width


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Thresholds:
    min_pass_rate: float = 0.95
    min_severity_accuracy: float = 0.95
    min_evidence_completeness: float = 0.90
    min_false_positive_pass_rate: float = 0.95
    max_hallucination_failures: int = 0
    max_average_latency_ms: float = 500.0


@dataclass
class GateCheck:
    metric: str
    actual: float
    threshold: float
    passed: bool
    operator: str  # ">=" or "<="


# ---------------------------------------------------------------------------
# Core threshold logic (pure, no I/O — easy to test)
# ---------------------------------------------------------------------------

def check_thresholds(report: BenchmarkReport, thresholds: Thresholds) -> list[GateCheck]:
    return [
        _gte("pass_rate", report.pass_rate, thresholds.min_pass_rate),
        _gte("severity_accuracy", report.severity_accuracy, thresholds.min_severity_accuracy),
        _gte("evidence_completeness_avg", report.evidence_completeness_avg, thresholds.min_evidence_completeness),
        _gte("false_positive_pass_rate", report.false_positive_pass_rate, thresholds.min_false_positive_pass_rate),
        _lte("hallucination_failure_count", float(report.hallucination_failure_count), float(thresholds.max_hallucination_failures)),
        _lte("average_latency_ms", report.average_latency_ms, thresholds.max_average_latency_ms),
    ]


def _gte(metric: str, actual: float, threshold: float) -> GateCheck:
    return GateCheck(metric=metric, actual=actual, threshold=threshold, passed=actual >= threshold, operator=">=")


def _lte(metric: str, actual: float, threshold: float) -> GateCheck:
    return GateCheck(metric=metric, actual=actual, threshold=threshold, passed=actual <= threshold, operator="<=")


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _print_gate_results(checks: list[GateCheck], report: BenchmarkReport) -> None:
    bar = "=" * 62
    print(f"\n{bar}")
    print("Brevix AI Quality Gate")
    print(bar)
    print(f"\n  Scenarios: {report.total_passed}/{report.total_scenarios} passed\n")

    if report.active_filters:
        print("  Active Filters:")
        for k, v in report.active_filters.items():
            display = ", ".join(v) if isinstance(v, list) else str(v)
            print(f"    {k:<28} {display}")
        if report.skipped_scenario_count:
            total_ds = report.total_scenarios + report.skipped_scenario_count
            print(
                f"    {'skipped':<28} {report.skipped_scenario_count} of {total_ds} scenarios"
            )
        print()

    if report.prompts_used:
        print("  Prompt Versions:")
        for p in report.prompts_used:
            name = p.get("prompt_name", "")
            version = p.get("prompt_version", "")
            short_hash = p.get("prompt_hash", "")[:8]
            print(f"    {name:<28} {version}   {short_hash}")
        print()

    for c in checks:
        label = "PASS" if c.passed else "FAIL"
        actual_str = _fmt(c.actual)
        threshold_str = _fmt(c.threshold)
        note = "" if c.passed else "  ← below threshold"
        print(f"  {label}  {c.metric:<{_COL}} {actual_str:<10} {c.operator} {threshold_str}{note}")

    total = len(checks)
    passed = sum(1 for c in checks if c.passed)
    print(f"\n{bar}")
    if passed == total:
        print(f"Quality gate PASSED  ({passed}/{total} checks)")
    else:
        failed_names = [c.metric for c in checks if not c.passed]
        print(f"Quality gate FAILED  ({passed}/{total} checks passed)")
        print(f"Failed: {', '.join(failed_names)}")
    print(f"{bar}\n")


def _fmt(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:.3f}"


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

class GateError(Exception):
    pass


def load_report_from_json(path: Path) -> BenchmarkReport:
    try:
        raw = path.read_text()
    except FileNotFoundError:
        raise GateError(f"Report file not found: {path}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GateError(f"Invalid JSON in {path}: {exc}")

    if not isinstance(data, dict):
        raise GateError(f"Report must be a JSON object, got {type(data).__name__}")

    try:
        return BenchmarkReport(**data)
    except TypeError as exc:
        raise GateError(f"Report has unexpected structure: {exc}")


def _run_and_save(
    *,
    category: str | None = None,
    risk_type: str | None = None,
    severity: str | None = None,
    tags: list[str] | None = None,
) -> BenchmarkReport:
    dataset = load_dataset(DATASET_PATH)

    active_filters = build_active_filters(
        category=category,
        risk_type=risk_type,
        severity=severity,
        tags=tags,
    )

    if active_filters:
        filtered = filter_dataset(
            dataset,
            category=category,
            risk_type=risk_type,
            severity=severity,
            tags=tags,
        )
        skipped_count = len(dataset) - len(filtered)
        if not filtered:
            print(
                f"WARNING: No scenarios match the specified filters: {active_filters}. "
                "Nothing to run.",
                file=sys.stderr,
            )
    else:
        filtered = dataset
        skipped_count = 0

    settings_module = __import__("app.config", fromlist=["get_settings"])
    settings = settings_module.get_settings()
    results = asyncio.run(run_all(filtered, settings))

    tags_by_id = {s["id"]: s.get("tags", []) for s in filtered}
    report = generate_report(
        results,
        active_filters=active_filters,
        skipped_scenario_count=skipped_count,
        tags_by_id=tags_by_id,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "latest_benchmark_report.json"
    out.write_text(report_to_json(report))
    print(f"Report saved to {out}")

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce quality thresholds on Brevix benchmark results."
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to an existing benchmark report JSON. Omit to run benchmarks fresh.",
    )
    # Threshold flags
    parser.add_argument("--min-pass-rate", type=float, default=0.95, metavar="N")
    parser.add_argument("--min-severity-accuracy", type=float, default=0.95, metavar="N")
    parser.add_argument("--min-evidence-completeness", type=float, default=0.90, metavar="N")
    parser.add_argument("--min-false-positive-pass-rate", type=float, default=0.95, metavar="N")
    parser.add_argument("--max-hallucination-failures", type=int, default=0, metavar="N")
    parser.add_argument("--max-average-latency-ms", type=float, default=500.0, metavar="N")
    # Scenario filter flags (only applied when running fresh — ignored with --report-json)
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        metavar="CATEGORY",
        help="Only run scenarios with this category (fresh run only).",
    )
    parser.add_argument(
        "--risk-type",
        type=str,
        default=None,
        metavar="RISK_TYPE",
        help="Only run scenarios with this risk_type (fresh run only).",
    )
    parser.add_argument(
        "--severity",
        type=str,
        default=None,
        metavar="SEVERITY",
        help="Only run scenarios with this expected_severity (fresh run only).",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=None,
        metavar="TAG",
        help=(
            "Only run scenarios that have this tag (fresh run only). "
            "Repeat for AND logic: --tag vendor --tag entity_graph"
        ),
    )
    args = parser.parse_args(argv)

    thresholds = Thresholds(
        min_pass_rate=args.min_pass_rate,
        min_severity_accuracy=args.min_severity_accuracy,
        min_evidence_completeness=args.min_evidence_completeness,
        min_false_positive_pass_rate=args.min_false_positive_pass_rate,
        max_hallucination_failures=args.max_hallucination_failures,
        max_average_latency_ms=args.max_average_latency_ms,
    )

    if args.report_json is not None:
        try:
            report = load_report_from_json(args.report_json)
        except GateError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    else:
        report = _run_and_save(
            category=args.category,
            risk_type=args.risk_type,
            severity=args.severity,
            tags=args.tag,
        )

    checks = check_thresholds(report, thresholds)
    _print_gate_results(checks, report)

    return 0 if all(c.passed for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
