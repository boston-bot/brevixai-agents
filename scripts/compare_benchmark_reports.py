"""Compare two Brevix benchmark reports and show metric deltas.

Exit codes:
  0 — comparison completed successfully (degradations do not cause exit 1)
  1 — a report file could not be loaded

Usage:
    python scripts/compare_benchmark_reports.py \\
        --base reports/history/benchmark_report_20260517_100000.json \\
        --current reports/latest_benchmark_report.json

    python scripts/compare_benchmark_reports.py \\
        --base reports/history/benchmark_report_20260517_100000.json \\
        --current reports/latest_benchmark_report.json \\
        --output-json reports/comparison.json \\
        --output-md reports/comparison.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluators.compare import compare_reports, comparison_to_json, comparison_to_markdown, print_comparison
from evaluators.report import BenchmarkReport


class CompareError(Exception):
    pass


def load_report(path: Path) -> BenchmarkReport:
    try:
        raw = path.read_text()
    except FileNotFoundError:
        raise CompareError(f"Report file not found: {path}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CompareError(f"Invalid JSON in {path}: {exc}")

    if not isinstance(data, dict):
        raise CompareError(f"Report must be a JSON object, got {type(data).__name__}")

    try:
        return BenchmarkReport(**data)
    except TypeError as exc:
        raise CompareError(f"Report has unexpected structure: {exc}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare two Brevix benchmark reports and show metric deltas."
    )
    parser.add_argument(
        "--base",
        type=Path,
        required=True,
        metavar="PATH",
        help="Path to the baseline benchmark report JSON.",
    )
    parser.add_argument(
        "--current",
        type=Path,
        required=True,
        metavar="PATH",
        help="Path to the current benchmark report JSON to compare against the base.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write the comparison result as JSON to this path.",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write the comparison result as Markdown to this path.",
    )
    args = parser.parse_args(argv)

    try:
        base_report = load_report(args.base)
        current_report = load_report(args.current)
    except CompareError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    comparison = compare_reports(base_report, current_report)
    print_comparison(comparison)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(comparison_to_json(comparison))
        print(f"Comparison JSON saved to {args.output_json}")

    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(comparison_to_markdown(comparison))
        print(f"Comparison Markdown saved to {args.output_md}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
