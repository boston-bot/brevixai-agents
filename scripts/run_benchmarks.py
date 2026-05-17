"""Benchmark runner with structured report generation.

Usage:
    python scripts/run_benchmarks.py --report
    python scripts/run_benchmarks.py --report --output path/to/results.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from evaluators.report import generate_report, report_to_json, report_to_markdown
from scripts.run_evals import DATASET_PATH, run_all

REPORTS_DIR = Path(__file__).parent.parent / "reports"


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
        "--output",
        type=Path,
        default=None,
        help="Path to write raw eval results JSON (optional).",
    )
    args = parser.parse_args(argv)

    with DATASET_PATH.open() as f:
        dataset = json.load(f)

    settings = get_settings()
    results = asyncio.run(run_all(dataset, settings))

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w") as f:
            json.dump(results, f, indent=2)
        print(f"Raw results saved to {args.output}")

    if args.report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report = generate_report(results)

        json_path = REPORTS_DIR / "latest_benchmark_report.json"
        json_path.write_text(report_to_json(report))

        md_path = REPORTS_DIR / "latest_benchmark_report.md"
        md_path.write_text(report_to_markdown(report))

        total = report.total_scenarios
        passed = report.total_passed
        rate = report.pass_rate
        print(f"\nBenchmark complete: {passed}/{total} passed ({rate:.1%})")
        print(f"  JSON report -> {json_path}")
        print(f"  MD   report -> {md_path}\n")

    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
