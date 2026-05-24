"""Tests for benchmark snapshot generation and release readiness logic."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from evaluators.report import BenchmarkReport
from scripts.generate_benchmark_snapshot import (
    main,
    release_readiness,
    snapshot_to_markdown,
)
from scripts.quality_gate import GateCheck, Thresholds, check_thresholds


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _perfect_report() -> BenchmarkReport:
    return BenchmarkReport(
        generated_at="2026-05-17T00:00:00+00:00",
        total_scenarios=15,
        total_passed=15,
        total_failed=0,
        pass_rate=1.0,
        failed_scenario_ids=[],
        failed_evaluator_names=[],
        severity_accuracy=1.0,
        evidence_completeness_avg=1.0,
        false_positive_pass_rate=1.0,
        hallucination_failure_count=0,
        average_latency_ms=4.5,
        slowest_scenarios=[
            {"scenario_id": "duplicate_invoice", "latency_ms": 9.85},
            {"scenario_id": "ghost_vendor", "latency_ms": 5.0},
        ],
        scenario_breakdown=[
            {
                "scenario_id": "duplicate_invoice",
                "passed": True,
                "latency_ms": 9.85,
                "tags": ["vendor", "duplicate"],
                "failed_checks": [],
                "check_scores": {},
            }
        ],
        known_gaps=["Gap A", "Gap B"],
        next_improvements=[],
    )


def _failing_report() -> BenchmarkReport:
    r = _perfect_report()
    r.pass_rate = 0.80
    r.severity_accuracy = 0.70
    r.total_passed = 12
    r.total_failed = 3
    r.failed_scenario_ids = ["a", "b", "c"]
    return r


def _perfect_checks() -> list[GateCheck]:
    return check_thresholds(_perfect_report(), Thresholds())


def _failing_checks() -> list[GateCheck]:
    return check_thresholds(_failing_report(), Thresholds())


def _write_report_json(path: Path, report: BenchmarkReport) -> None:
    path.write_text(json.dumps(asdict(report), indent=2))


# ---------------------------------------------------------------------------
# release_readiness — pure logic
# ---------------------------------------------------------------------------

def test_release_readiness_ready_when_all_checks_pass() -> None:
    status, failed = release_readiness(_perfect_checks())
    assert status == "READY"
    assert failed == []


def test_release_readiness_review_required_when_any_check_fails() -> None:
    status, failed = release_readiness(_failing_checks())
    assert status == "REVIEW REQUIRED"
    assert len(failed) > 0


def test_release_readiness_failed_metrics_named_correctly() -> None:
    r = _perfect_report()
    r.pass_rate = 0.50
    r.severity_accuracy = 0.60
    checks = check_thresholds(r, Thresholds())
    _, failed = release_readiness(checks)
    assert "pass_rate" in failed
    assert "severity_accuracy" in failed


def test_release_readiness_single_failure_is_review_required() -> None:
    r = _perfect_report()
    r.hallucination_failure_count = 1
    checks = check_thresholds(r, Thresholds())
    status, _ = release_readiness(checks)
    assert status == "REVIEW REQUIRED"


# ---------------------------------------------------------------------------
# snapshot_to_markdown — snapshot from passing report
# ---------------------------------------------------------------------------

def test_snapshot_includes_title() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "# Brevix AI Benchmark Snapshot" in md


def test_snapshot_includes_generated_timestamp() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "2026-05-17T00:00:00" in md


def test_snapshot_includes_total_scenarios() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "15" in md


def test_snapshot_passing_report_shows_ready_status() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "READY" in md
    assert "REVIEW REQUIRED" not in md


def test_snapshot_includes_quality_metrics_table() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "## Quality Metrics" in md
    assert "Pass Rate" in md
    assert "Severity Accuracy" in md
    assert "Evidence Completeness" in md
    assert "False Positive" in md
    assert "Hallucination" in md
    assert "Average Latency" in md


def test_snapshot_all_metrics_show_pass_on_perfect_report() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "FAIL" not in md


def test_snapshot_includes_slowest_scenarios() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "## Slowest Scenarios" in md
    assert "duplicate_invoice" in md


def test_snapshot_includes_known_gaps() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "## Known Gaps" in md
    assert "Gap A" in md
    assert "Gap B" in md


def test_snapshot_includes_service_version() -> None:
    md = snapshot_to_markdown(
        _perfect_report(), _perfect_checks(), Thresholds(), service_version="1.2.3"
    )
    assert "1.2.3" in md


# ---------------------------------------------------------------------------
# snapshot_to_markdown — snapshot from failing report
# ---------------------------------------------------------------------------

def test_snapshot_failing_report_shows_review_required() -> None:
    md = snapshot_to_markdown(_failing_report(), _failing_checks(), Thresholds())
    assert "REVIEW REQUIRED" in md
    assert "READY" not in md.split("REVIEW REQUIRED")[0]  # READY not before the status line


def test_snapshot_failing_report_names_failed_metrics() -> None:
    md = snapshot_to_markdown(_failing_report(), _failing_checks(), Thresholds())
    assert "pass_rate" in md
    assert "severity_accuracy" in md


def test_snapshot_failing_report_shows_fail_in_metrics_table() -> None:
    md = snapshot_to_markdown(_failing_report(), _failing_checks(), Thresholds())
    assert "FAIL" in md


# ---------------------------------------------------------------------------
# snapshot_to_markdown — active filters displayed
# ---------------------------------------------------------------------------

def test_snapshot_active_filters_section_appears_when_filters_set() -> None:
    r = _perfect_report()
    r.active_filters = {"category": "payroll", "severity": "high"}
    r.skipped_scenario_count = 12
    md = snapshot_to_markdown(r, _perfect_checks(), Thresholds())
    assert "## Active Filters" in md
    assert "payroll" in md
    assert "high" in md


def test_snapshot_active_filters_section_absent_when_no_filters() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "## Active Filters" not in md


def test_snapshot_tag_filters_rendered_as_comma_separated() -> None:
    r = _perfect_report()
    r.active_filters = {"tags": ["vendor", "entity_graph"]}
    md = snapshot_to_markdown(r, _perfect_checks(), Thresholds())
    assert "vendor, entity_graph" in md


def test_snapshot_skipped_count_in_header_when_filtered() -> None:
    r = _perfect_report()
    r.skipped_scenario_count = 10
    r.active_filters = {"severity": "high"}
    md = snapshot_to_markdown(r, _perfect_checks(), Thresholds())
    assert "10" in md
    assert "skipped" in md


# ---------------------------------------------------------------------------
# snapshot_to_markdown — prompt metadata displayed
# ---------------------------------------------------------------------------

_SAMPLE_PROMPTS = [
    {"prompt_name": "router", "prompt_version": "v1", "prompt_hash": "a" * 64},
    {"prompt_name": "explanation", "prompt_version": "v2", "prompt_hash": "b" * 64},
]


def test_snapshot_prompt_versions_section_appears_when_prompts_present() -> None:
    r = _perfect_report()
    r.prompts_used = _SAMPLE_PROMPTS
    md = snapshot_to_markdown(r, _perfect_checks(), Thresholds())
    assert "## Prompt Versions" in md
    assert "router" in md
    assert "explanation" in md


def test_snapshot_prompt_short_hashes_displayed() -> None:
    r = _perfect_report()
    r.prompts_used = _SAMPLE_PROMPTS
    md = snapshot_to_markdown(r, _perfect_checks(), Thresholds())
    assert "aaaaaaaa" in md
    assert "bbbbbbbb" in md


def test_snapshot_prompt_versions_omitted_when_no_prompts() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "## Prompt Versions" not in md


# ---------------------------------------------------------------------------
# snapshot_to_markdown — category coverage
# ---------------------------------------------------------------------------

def test_snapshot_category_coverage_shown_when_categories_provided() -> None:
    r = _perfect_report()
    r.scenario_breakdown = [
        {"scenario_id": "dup_inv", "passed": True, "latency_ms": 5.0,
         "tags": [], "failed_checks": [], "check_scores": {}},
        {"scenario_id": "ghost_v", "passed": True, "latency_ms": 4.0,
         "tags": [], "failed_checks": [], "check_scores": {}},
    ]
    cats = {"dup_inv": "accounts_payable", "ghost_v": "vendor_management"}
    md = snapshot_to_markdown(r, _perfect_checks(), Thresholds(), categories_by_id=cats)
    assert "Categories covered" in md
    assert "accounts_payable" in md
    assert "vendor_management" in md


def test_snapshot_category_coverage_absent_when_no_categories() -> None:
    md = snapshot_to_markdown(_perfect_report(), _perfect_checks(), Thresholds())
    assert "Categories covered" not in md


# ---------------------------------------------------------------------------
# main() — CLI integration
# ---------------------------------------------------------------------------

def test_main_generates_snapshot_file(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "BENCHMARK_SNAPSHOT.md"
    _write_report_json(report_path, _perfect_report())

    code = main(["--report-json", str(report_path), "--output", str(output_path)])

    assert code == 0
    assert output_path.exists()
    content = output_path.read_text()
    assert "# Brevix AI Benchmark Snapshot" in content


def test_main_snapshot_contains_ready_for_passing_report(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "BENCHMARK_SNAPSHOT.md"
    _write_report_json(report_path, _perfect_report())
    main(["--report-json", str(report_path), "--output", str(output_path)])
    assert "READY" in output_path.read_text()


def test_main_snapshot_contains_review_required_for_failing_report(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "BENCHMARK_SNAPSHOT.md"
    _write_report_json(report_path, _failing_report())
    main(["--report-json", str(report_path), "--output", str(output_path)])
    assert "REVIEW REQUIRED" in output_path.read_text()


def test_main_missing_report_returns_1(tmp_path: Path) -> None:
    output_path = tmp_path / "out.md"
    code = main([
        "--report-json", str(tmp_path / "does_not_exist.json"),
        "--output", str(output_path),
    ])
    assert code == 1
    assert not output_path.exists()


def test_main_missing_report_does_not_raise(tmp_path: Path) -> None:
    try:
        main([
            "--report-json", str(tmp_path / "does_not_exist.json"),
            "--output", str(tmp_path / "out.md"),
        ])
    except Exception as exc:
        pytest.fail(f"main() raised unexpectedly: {exc}")


def test_main_creates_output_directory_if_missing(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "nested" / "dir" / "BENCHMARK_SNAPSHOT.md"
    _write_report_json(report_path, _perfect_report())

    code = main(["--report-json", str(report_path), "--output", str(output_path)])
    assert code == 0
    assert output_path.exists()


def test_main_returns_0_regardless_of_readiness_status(tmp_path: Path) -> None:
    """Snapshot generator exit code reflects I/O success, not gate pass/fail."""
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "out.md"
    _write_report_json(report_path, _failing_report())

    code = main(["--report-json", str(report_path), "--output", str(output_path)])
    assert code == 0  # snapshot was written successfully


def test_main_prints_readiness_status_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "out.md"
    _write_report_json(report_path, _perfect_report())
    main(["--report-json", str(report_path), "--output", str(output_path)])
    out = capsys.readouterr().out
    assert "READY" in out


def test_main_uses_default_dataset_for_categories(tmp_path: Path) -> None:
    """When dataset exists, categories appear in snapshot."""
    from scripts.run_evals import DATASET_PATH
    report_path = tmp_path / "report.json"
    output_path = tmp_path / "out.md"

    report = _perfect_report()
    # Use a real scenario_id from the production dataset
    report.scenario_breakdown = [
        {
            "scenario_id": "payroll_anomaly",
            "passed": True,
            "latency_ms": 5.0,
            "tags": ["payroll"],
            "failed_checks": [],
            "check_scores": {},
        }
    ]
    _write_report_json(report_path, report)

    main([
        "--report-json", str(report_path),
        "--output", str(output_path),
        "--dataset", str(DATASET_PATH),
    ])
    assert "payroll" in output_path.read_text()
