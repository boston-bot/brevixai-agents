"""Tests for CI quality gate thresholds and CLI behavior."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from evaluators.report import BenchmarkReport
from scripts.quality_gate import GateError, Thresholds, check_thresholds, load_report_from_json, main


# ---------------------------------------------------------------------------
# Fixtures
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
        slowest_scenarios=[],
        scenario_breakdown=[],
        known_gaps=[],
        next_improvements=[],
    )


def _write_report(tmp_path: Path, report: BenchmarkReport) -> Path:
    p = tmp_path / "report.json"
    p.write_text(json.dumps(asdict(report), indent=2))
    return p


# ---------------------------------------------------------------------------
# check_thresholds — unit tests (no I/O)
# ---------------------------------------------------------------------------

def test_all_gates_pass_on_perfect_report() -> None:
    checks = check_thresholds(_perfect_report(), Thresholds())
    assert all(c.passed for c in checks)
    assert len(checks) == 6


def test_gate_metrics_are_labeled_correctly() -> None:
    checks = check_thresholds(_perfect_report(), Thresholds())
    names = [c.metric for c in checks]
    assert "pass_rate" in names
    assert "severity_accuracy" in names
    assert "evidence_completeness_avg" in names
    assert "false_positive_pass_rate" in names
    assert "hallucination_failure_count" in names
    assert "average_latency_ms" in names


def test_pass_rate_gate_fails_below_threshold() -> None:
    report = _perfect_report()
    report.pass_rate = 0.80
    checks = check_thresholds(report, Thresholds(min_pass_rate=0.95))
    gate = next(c for c in checks if c.metric == "pass_rate")
    assert not gate.passed
    assert gate.actual == pytest.approx(0.80)


def test_severity_accuracy_gate_fails_below_threshold() -> None:
    report = _perfect_report()
    report.severity_accuracy = 0.70
    checks = check_thresholds(report, Thresholds(min_severity_accuracy=0.95))
    gate = next(c for c in checks if c.metric == "severity_accuracy")
    assert not gate.passed


def test_evidence_completeness_gate_fails_below_threshold() -> None:
    report = _perfect_report()
    report.evidence_completeness_avg = 0.50
    checks = check_thresholds(report, Thresholds(min_evidence_completeness=0.90))
    gate = next(c for c in checks if c.metric == "evidence_completeness_avg")
    assert not gate.passed


def test_false_positive_pass_rate_gate_fails_below_threshold() -> None:
    report = _perfect_report()
    report.false_positive_pass_rate = 0.60
    checks = check_thresholds(report, Thresholds(min_false_positive_pass_rate=0.95))
    gate = next(c for c in checks if c.metric == "false_positive_pass_rate")
    assert not gate.passed


def test_hallucination_gate_fails_when_nonzero() -> None:
    report = _perfect_report()
    report.hallucination_failure_count = 1
    checks = check_thresholds(report, Thresholds(max_hallucination_failures=0))
    gate = next(c for c in checks if c.metric == "hallucination_failure_count")
    assert not gate.passed


def test_latency_gate_fails_above_threshold() -> None:
    report = _perfect_report()
    report.average_latency_ms = 750.0
    checks = check_thresholds(report, Thresholds(max_average_latency_ms=500.0))
    gate = next(c for c in checks if c.metric == "average_latency_ms")
    assert not gate.passed


def test_only_failing_gate_is_marked_failed() -> None:
    report = _perfect_report()
    report.severity_accuracy = 0.50
    checks = check_thresholds(report, Thresholds())
    failed = [c for c in checks if not c.passed]
    assert len(failed) == 1
    assert failed[0].metric == "severity_accuracy"


def test_custom_threshold_relaxes_default() -> None:
    report = _perfect_report()
    report.pass_rate = 0.80
    # Relax the threshold below actual value — should pass
    checks = check_thresholds(report, Thresholds(min_pass_rate=0.75))
    gate = next(c for c in checks if c.metric == "pass_rate")
    assert gate.passed


def test_hallucination_allowed_when_threshold_raised() -> None:
    report = _perfect_report()
    report.hallucination_failure_count = 2
    checks = check_thresholds(report, Thresholds(max_hallucination_failures=3))
    gate = next(c for c in checks if c.metric == "hallucination_failure_count")
    assert gate.passed


# ---------------------------------------------------------------------------
# load_report_from_json
# ---------------------------------------------------------------------------

def test_load_report_from_json_returns_benchmark_report(tmp_path: Path) -> None:
    p = _write_report(tmp_path, _perfect_report())
    report = load_report_from_json(p)
    assert isinstance(report, BenchmarkReport)
    assert report.total_scenarios == 15


def test_load_report_raises_gate_error_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(GateError, match="not found"):
        load_report_from_json(tmp_path / "does_not_exist.json")


def test_load_report_raises_gate_error_for_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{ this is not valid json }")
    with pytest.raises(GateError, match="Invalid JSON"):
        load_report_from_json(p)


def test_load_report_raises_gate_error_for_json_array(tmp_path: Path) -> None:
    p = tmp_path / "array.json"
    p.write_text("[]")
    with pytest.raises(GateError, match="JSON object"):
        load_report_from_json(p)


def test_load_report_raises_gate_error_for_missing_fields(tmp_path: Path) -> None:
    p = tmp_path / "sparse.json"
    p.write_text('{"total_scenarios": 1}')
    with pytest.raises(GateError, match="unexpected structure"):
        load_report_from_json(p)


# ---------------------------------------------------------------------------
# main() — CLI integration via --report-json (no live benchmark runs)
# ---------------------------------------------------------------------------

def test_main_returns_0_for_perfect_report(tmp_path: Path) -> None:
    p = _write_report(tmp_path, _perfect_report())
    assert main(["--report-json", str(p)]) == 0


def test_main_returns_1_when_pass_rate_fails(tmp_path: Path) -> None:
    report = _perfect_report()
    report.pass_rate = 0.50
    p = _write_report(tmp_path, report)
    assert main(["--report-json", str(p)]) == 1


def test_main_returns_1_when_severity_accuracy_fails(tmp_path: Path) -> None:
    report = _perfect_report()
    report.severity_accuracy = 0.50
    p = _write_report(tmp_path, report)
    assert main(["--report-json", str(p)]) == 1


def test_main_returns_1_when_evidence_completeness_fails(tmp_path: Path) -> None:
    report = _perfect_report()
    report.evidence_completeness_avg = 0.50
    p = _write_report(tmp_path, report)
    assert main(["--report-json", str(p)]) == 1


def test_main_returns_1_when_false_positive_rate_fails(tmp_path: Path) -> None:
    report = _perfect_report()
    report.false_positive_pass_rate = 0.50
    p = _write_report(tmp_path, report)
    assert main(["--report-json", str(p)]) == 1


def test_main_returns_1_when_hallucination_failures_nonzero(tmp_path: Path) -> None:
    report = _perfect_report()
    report.hallucination_failure_count = 1
    p = _write_report(tmp_path, report)
    assert main(["--report-json", str(p)]) == 1


def test_main_returns_1_when_latency_exceeds_threshold(tmp_path: Path) -> None:
    report = _perfect_report()
    report.average_latency_ms = 999.0
    p = _write_report(tmp_path, report)
    assert main(["--report-json", str(p)]) == 1


def test_main_returns_1_for_missing_report_file(tmp_path: Path) -> None:
    assert main(["--report-json", str(tmp_path / "missing.json")]) == 1


def test_main_returns_1_for_invalid_report_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not json at all")
    assert main(["--report-json", str(p)]) == 1


def test_main_threshold_flag_overrides_default_and_passes(tmp_path: Path) -> None:
    report = _perfect_report()
    report.pass_rate = 0.80  # below default 0.95
    p = _write_report(tmp_path, report)
    # Relax threshold via CLI flag — should now pass
    assert main(["--report-json", str(p), "--min-pass-rate", "0.75"]) == 0


def test_main_threshold_flag_overrides_default_and_fails(tmp_path: Path) -> None:
    report = _perfect_report()
    report.pass_rate = 1.0  # passes default 0.95
    p = _write_report(tmp_path, report)
    # Tighten threshold above actual — should fail
    assert main(["--report-json", str(p), "--min-pass-rate", "1.01"]) == 1


def test_main_hallucination_threshold_flag(tmp_path: Path) -> None:
    report = _perfect_report()
    report.hallucination_failure_count = 2
    p = _write_report(tmp_path, report)
    assert main(["--report-json", str(p), "--max-hallucination-failures", "3"]) == 0
    assert main(["--report-json", str(p), "--max-hallucination-failures", "1"]) == 1


# ---------------------------------------------------------------------------
# Prompt metadata in quality gate output (Phase 2.7)
# ---------------------------------------------------------------------------

_SAMPLE_PROMPTS: list[dict] = [
    {"prompt_name": "router", "prompt_version": "v1", "prompt_hash": "a" * 64},
    {"prompt_name": "explanation", "prompt_version": "v1", "prompt_hash": "b" * 64},
    {"prompt_name": "fraud_analyzer_summary", "prompt_version": "v1", "prompt_hash": "c" * 64},
    {"prompt_name": "action_gate", "prompt_version": "v1", "prompt_hash": "d" * 64},
]


def _report_with_prompts() -> BenchmarkReport:
    r = _perfect_report()
    r.prompts_used = _SAMPLE_PROMPTS
    return r


def test_gate_prints_prompt_versions_when_present(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    p = _write_report(tmp_path, _report_with_prompts())
    main(["--report-json", str(p)])
    out = capsys.readouterr().out
    assert "Prompt Versions" in out
    assert "router" in out
    assert "explanation" in out
    assert "fraud_analyzer_summary" in out
    assert "action_gate" in out


def test_gate_prints_short_hash_for_each_prompt(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    p = _write_report(tmp_path, _report_with_prompts())
    main(["--report-json", str(p)])
    out = capsys.readouterr().out
    # Each 64-char hash is truncated to 8 chars in output
    assert "aaaaaaaa" in out
    assert "bbbbbbbb" in out
    assert "cccccccc" in out
    assert "dddddddd" in out


def test_gate_omits_prompt_section_when_prompts_used_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    report = _perfect_report()
    # prompts_used defaults to [] — old report with no prompt metadata
    p = _write_report(tmp_path, report)
    main(["--report-json", str(p)])
    out = capsys.readouterr().out
    assert "Prompt Versions" not in out


def test_gate_pass_fail_unaffected_by_prompt_metadata(tmp_path: Path) -> None:
    """Exit code must not change based on prompt metadata presence."""
    p1 = tmp_path / "without_prompts.json"
    p1.write_text(json.dumps(asdict(_perfect_report())))

    p2 = tmp_path / "with_prompts.json"
    p2.write_text(json.dumps(asdict(_report_with_prompts())))

    assert main(["--report-json", str(p1)]) == main(["--report-json", str(p2)])


def test_old_report_without_prompts_used_loads_in_gate(tmp_path: Path) -> None:
    """A report JSON that predates prompts_used must load without error."""
    data = asdict(_perfect_report())
    del data["prompts_used"]
    p = tmp_path / "old_report.json"
    p.write_text(json.dumps(data))
    # Must not raise; gate should pass (perfect report)
    assert main(["--report-json", str(p)]) == 0
