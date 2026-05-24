"""Benchmark runner with structured report generation.

Usage:
    python scripts/run_benchmarks.py --report
    python scripts/run_benchmarks.py --report --history
    python scripts/run_benchmarks.py --report --tag vendor
    python scripts/run_benchmarks.py --report --severity high --tag payments
    python scripts/run_benchmarks.py --report --category vendor_management
    python scripts/run_benchmarks.py --report --output path/to/results.json
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluators.dataset import build_active_filters, filter_dataset, load_dataset
from evaluators.report import BenchmarkReport, generate_report, report_to_json, report_to_markdown
from scripts.run_evals import DATASET_PATH, run_all

REPORTS_DIR = Path(__file__).parent.parent / "reports"
HISTORY_DIR = REPORTS_DIR / "history"


def _history_timestamp(report: BenchmarkReport) -> str:
    """Return a YYYYMMDD_HHMMSS string derived from the report's generated_at field."""
    dt = datetime.fromisoformat(report.generated_at)
    return dt.strftime("%Y%m%d_%H%M%S")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Brevix fraud benchmarks and generate a structured report."
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate JSON and Markdown reports in reports/.",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help=(
            "Also write timestamped copies to reports/history/. "
            "Requires --report. Enables report comparison with compare_benchmark_reports.py."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to write raw eval results JSON (optional).",
    )
    # Scenario filter flags
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        metavar="CATEGORY",
        help="Only run scenarios with this category (e.g. vendor_management, accounts_payable).",
    )
    parser.add_argument(
        "--risk-type",
        type=str,
        default=None,
        metavar="RISK_TYPE",
        help="Only run scenarios with this risk_type (e.g. duplicate_invoice, ghost_vendor).",
    )
    parser.add_argument(
        "--severity",
        type=str,
        default=None,
        metavar="SEVERITY",
        help="Only run scenarios with this expected_severity (e.g. high, critical, medium).",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=None,
        metavar="TAG",
        help=(
            "Only run scenarios that have this tag. "
            "Repeat to require multiple tags (AND logic): --tag vendor --tag entity_graph"
        ),
    )
    args = parser.parse_args(argv)

    dataset = load_dataset(DATASET_PATH)

    active_filters = build_active_filters(
        category=args.category,
        risk_type=args.risk_type,
        severity=args.severity,
        tags=args.tag,
    )

    if active_filters:
        filtered = filter_dataset(
            dataset,
            category=args.category,
            risk_type=args.risk_type,
            severity=args.severity,
            tags=args.tag,
        )
        skipped_count = len(dataset) - len(filtered)
        if not filtered:
            print(
                f"WARNING: No scenarios match the specified filters: {active_filters}. "
                "Nothing to run."
            )
            return 0
        print(
            f"Filters active: {active_filters} — "
            f"running {len(filtered)}/{len(dataset)} scenarios "
            f"({skipped_count} skipped)"
        )
    else:
        filtered = dataset
        skipped_count = 0

    from app.config import get_settings
    settings = get_settings()
    results = asyncio.run(run_all(filtered, settings))

    tags_by_id = {s["id"]: s.get("tags", []) for s in filtered}

    if args.output:
        import json
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w") as f:
            json.dump(results, f, indent=2)
        print(f"Raw results saved to {args.output}")

    if args.report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report = generate_report(
            results,
            active_filters=active_filters,
            skipped_scenario_count=skipped_count,
            tags_by_id=tags_by_id,
        )

        json_path = REPORTS_DIR / "latest_benchmark_report.json"
        json_path.write_text(report_to_json(report))

        md_path = REPORTS_DIR / "latest_benchmark_report.md"
        md_path.write_text(report_to_markdown(report))

        total = report.total_scenarios
        passed = report.total_passed
        rate = report.pass_rate
        print(f"\nBenchmark complete: {passed}/{total} passed ({rate:.1%})")
        if skipped_count:
            print(f"  Skipped: {skipped_count} scenarios (filtered out)")
        print(f"  JSON report -> {json_path}")
        print(f"  MD   report -> {md_path}")

        if args.history:
            HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            ts = _history_timestamp(report)
            hist_json = HISTORY_DIR / f"benchmark_report_{ts}.json"
            hist_md = HISTORY_DIR / f"benchmark_report_{ts}.md"
            hist_json.write_text(report_to_json(report))
            hist_md.write_text(report_to_markdown(report))
            print(f"  History JSON -> {hist_json}")
            print(f"  History MD   -> {hist_md}")

        print()

    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
