"""Generate a human-readable benchmark snapshot for release review.

Reads reports/latest_benchmark_report.json (or a specified report), evaluates
release readiness against default quality gate thresholds, and writes
reports/BENCHMARK_SNAPSHOT.md.

Usage:
    python scripts/generate_benchmark_snapshot.py
    python scripts/generate_benchmark_snapshot.py --report-json reports/latest_benchmark_report.json
    python scripts/generate_benchmark_snapshot.py --output path/to/BENCHMARK_SNAPSHOT.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluators.report import BenchmarkReport
from scripts.quality_gate import GateCheck, GateError, Thresholds, check_thresholds, load_report_from_json

REPORTS_DIR = Path(__file__).parent.parent / "reports"
DATASET_PATH = Path(__file__).parent.parent / "datasets" / "fraud_benchmarks.json"
DEFAULT_REPORT = REPORTS_DIR / "latest_benchmark_report.json"
DEFAULT_OUTPUT = REPORTS_DIR / "BENCHMARK_SNAPSHOT.md"

_THRESHOLD_LABELS: dict[str, tuple[str, str]] = {
    "pass_rate":                 ("Pass Rate",                    "≥ {:.0%}"),
    "severity_accuracy":         ("Severity Accuracy",            "≥ {:.0%}"),
    "evidence_completeness_avg": ("Evidence Completeness (avg)",  "≥ {:.0%}"),
    "false_positive_pass_rate":  ("False Positive Clean Rate",    "≥ {:.0%}"),
    "hallucination_failure_count": ("Hallucination Failures",     "≤ {}"),
    "average_latency_ms":        ("Average Latency",              "≤ {} ms"),
}


def _service_version() -> str:
    try:
        from importlib.metadata import version
        return version("brevixai-agent-service")
    except Exception:
        return "unknown"


def release_readiness(checks: list[GateCheck]) -> tuple[str, list[str]]:
    """Return (status_string, list_of_failed_metric_names).

    status_string is 'READY' or 'REVIEW REQUIRED'.
    """
    failed = [c.metric for c in checks if not c.passed]
    status = "READY" if not failed else "REVIEW REQUIRED"
    return status, failed


def _categories_from_dataset(dataset_path: Path) -> dict[str, str]:
    """Load scenario_id -> category mapping from the dataset file."""
    try:
        import json
        with dataset_path.open() as f:
            dataset = json.load(f)
        return {s["id"]: s.get("category", "unknown") for s in dataset if "id" in s}
    except Exception:
        return {}


def _fmt_metric(check: GateCheck) -> str:
    """Format the 'Value' column for a gate check."""
    if check.metric == "hallucination_failure_count":
        return str(int(check.actual))
    if check.metric == "average_latency_ms":
        return f"{check.actual:.1f} ms"
    return f"{check.actual:.1%}"


def _fmt_threshold(check: GateCheck, thresholds: Thresholds) -> str:
    """Format the 'Threshold' column for a gate check."""
    label_fmt = _THRESHOLD_LABELS.get(check.metric, ("", "{}"))[1]
    if check.metric == "hallucination_failure_count":
        return label_fmt.format(thresholds.max_hallucination_failures)
    if check.metric == "average_latency_ms":
        return label_fmt.format(thresholds.max_average_latency_ms)
    # percentage thresholds
    threshold_map = {
        "pass_rate": thresholds.min_pass_rate,
        "severity_accuracy": thresholds.min_severity_accuracy,
        "evidence_completeness_avg": thresholds.min_evidence_completeness,
        "false_positive_pass_rate": thresholds.min_false_positive_pass_rate,
    }
    return label_fmt.format(threshold_map.get(check.metric, check.threshold))


def snapshot_to_markdown(
    report: BenchmarkReport,
    checks: list[GateCheck],
    thresholds: Thresholds,
    *,
    categories_by_id: dict[str, str] | None = None,
    service_version: str = "unknown",
) -> str:
    """Render the snapshot as a Markdown string. Pure function — no I/O."""
    status, failed_metrics = release_readiness(checks)
    lines: list[str] = []

    # Title block
    lines += [
        "# Brevix AI Benchmark Snapshot",
        "",
        f"**Service Version:** {service_version}",
        f"**Generated:** {report.generated_at}",
    ]
    total_in_ds = report.total_scenarios + report.skipped_scenario_count
    if report.skipped_scenario_count:
        lines.append(
            f"**Scenarios run:** {report.total_scenarios} / {total_in_ds}"
            f" ({report.skipped_scenario_count} skipped)"
        )
    else:
        lines.append(f"**Scenarios run:** {report.total_scenarios}")
    lines += ["", "---", ""]

    # Release readiness
    lines += ["## Release Readiness", ""]
    if status == "READY":
        lines.append(f"**Status: {status}** — All quality gate thresholds passed.")
    else:
        failed_str = ", ".join(f"`{m}`" for m in failed_metrics)
        lines.append(
            f"**Status: {status}** — The following thresholds failed: {failed_str}"
        )
    lines += ["", "---", ""]

    # Quality metrics table
    lines += [
        "## Quality Metrics",
        "",
        "| Metric | Value | Threshold | Status |",
        "|--------|-------|-----------|--------|",
    ]
    for c in checks:
        label = _THRESHOLD_LABELS.get(c.metric, (c.metric, ""))[0]
        value = _fmt_metric(c)
        threshold = _fmt_threshold(c, thresholds)
        gate_status = "PASS" if c.passed else "FAIL"
        lines.append(f"| {label} | {value} | {threshold} | {gate_status} |")
    lines += ["", "---", ""]

    # Dataset coverage
    lines += ["## Dataset Coverage", ""]
    lines.append(f"**Total scenarios run:** {report.total_scenarios}")

    if categories_by_id and report.scenario_breakdown:
        category_counts: dict[str, int] = {}
        for entry in report.scenario_breakdown:
            cat = categories_by_id.get(entry["scenario_id"], "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1
        lines.append("")
        lines.append("**Categories covered:**")
        lines.append("")
        lines += [
            "| Category | Scenarios |",
            "|----------|-----------|",
        ]
        for cat, count in sorted(category_counts.items()):
            lines.append(f"| {cat} | {count} |")
    lines += ["", "---", ""]

    # Active filters (only when a filtered run produced this report)
    if report.active_filters:
        lines += ["## Active Filters", ""]
        lines += ["| Filter | Value |", "|--------|-------|"]
        for k, v in report.active_filters.items():
            display = ", ".join(v) if isinstance(v, list) else str(v)
            lines.append(f"| {k} | {display} |")
        lines += ["", "---", ""]

    # Slowest scenarios
    lines += [
        "## Slowest Scenarios",
        "",
        "| Scenario | Latency (ms) |",
        "|----------|--------------| ",
    ]
    for s in report.slowest_scenarios:
        lines.append(f"| {s['scenario_id']} | {s['latency_ms']} |")
    lines += ["", "---", ""]

    # Prompt versions
    if report.prompts_used:
        lines += [
            "## Prompt Versions",
            "",
            "| Prompt | Version | Hash (short) |",
            "|--------|---------|--------------|",
        ]
        for p in report.prompts_used:
            short_hash = p.get("prompt_hash", "")[:8]
            lines.append(
                f"| {p.get('prompt_name', '')} | {p.get('prompt_version', '')} | `{short_hash}` |"
            )
        lines += ["", "---", ""]

    # Known gaps
    lines += ["## Known Gaps", ""]
    for gap in report.known_gaps:
        lines.append(f"- {gap}")
    lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a benchmark snapshot Markdown file for release review."
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=DEFAULT_REPORT,
        metavar="PATH",
        help=f"Benchmark report JSON to read (default: {DEFAULT_REPORT}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        metavar="PATH",
        help=f"Output path for the snapshot Markdown (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        metavar="PATH",
        help="Dataset JSON for category coverage (default: datasets/fraud_benchmarks.json).",
    )
    args = parser.parse_args(argv)

    try:
        report = load_report_from_json(args.report_json)
    except GateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    thresholds = Thresholds()
    checks = check_thresholds(report, thresholds)
    categories_by_id = _categories_from_dataset(args.dataset)
    version = _service_version()

    md = snapshot_to_markdown(
        report,
        checks,
        thresholds,
        categories_by_id=categories_by_id,
        service_version=version,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md)

    status, _ = release_readiness(checks)
    print(f"Snapshot written to {args.output}")
    print(f"Release readiness: {status}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
