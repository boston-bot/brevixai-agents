"""Generate a benchmark coverage matrix from the fraud scenario dataset.

Usage:
    python scripts/generate_coverage_matrix.py
    python scripts/generate_coverage_matrix.py --dataset datasets/fraud_benchmarks.json
    python scripts/generate_coverage_matrix.py --output-dir reports/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluators.coverage import compute_coverage, coverage_to_json, coverage_to_markdown
from evaluators.dataset import DatasetValidationError, load_dataset

DATASET_PATH = Path(__file__).parent.parent / "datasets" / "fraud_benchmarks.json"
REPORTS_DIR = Path(__file__).parent.parent / "reports"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a benchmark coverage matrix from the fraud scenario dataset."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PATH,
        metavar="PATH",
        help=f"Dataset JSON to analyse (default: {DATASET_PATH}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPORTS_DIR,
        metavar="DIR",
        help=f"Directory for output files (default: {REPORTS_DIR}).",
    )
    args = parser.parse_args(argv)

    try:
        dataset = load_dataset(args.dataset)
    except (DatasetValidationError, FileNotFoundError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    matrix = compute_coverage(dataset)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    json_path = args.output_dir / "coverage_matrix.json"
    json_path.write_text(coverage_to_json(matrix))

    md_path = args.output_dir / "coverage_matrix.md"
    md_path.write_text(coverage_to_markdown(matrix))

    print(f"Coverage matrix written:")
    print(f"  JSON -> {json_path}")
    print(f"  MD   -> {md_path}")
    print(f"\n  Scenarios: {matrix.total_scenarios}")
    print(f"  Categories: {len(matrix.by_category)}")
    print(f"  Risk types: {len(matrix.by_risk_type)}")
    print(f"  Tags: {len(matrix.by_tag)}")

    if matrix.missing_recommended_tags:
        print(f"\n  Missing recommended tags: {', '.join(matrix.missing_recommended_tags)}")
    if matrix.duplicate_scenario_ids:
        print(f"\n  WARN: Duplicate IDs: {', '.join(matrix.duplicate_scenario_ids)}")
    if matrix.missing_evidence_patterns:
        print(f"\n  WARN: Missing evidence patterns: {', '.join(matrix.missing_evidence_patterns)}")
    if matrix.missing_false_positive_guardrails:
        print(f"\n  WARN: Missing guardrails: {', '.join(matrix.missing_false_positive_guardrails)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
