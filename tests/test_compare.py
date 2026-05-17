"""Tests for benchmark report comparison logic (Phase 2.8)."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from evaluators.compare import (
    MetricDelta,
    ReportComparison,
    compare_reports,
    comparison_to_json,
    comparison_to_markdown,
    print_comparison,
)
from evaluators.report import BenchmarkReport
from scripts.compare_benchmark_reports import CompareError, load_report, main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PROMPTS_V1 = [
    {"prompt_name": "router",                 "prompt_version": "v1", "prompt_hash": "a" * 64},
    {"prompt_name": "fraud_analyzer_summary", "prompt_version": "v1", "prompt_hash": "b" * 64},
    {"prompt_name": "explanation",            "prompt_version": "v1", "prompt_hash": "c" * 64},
    {"prompt_name": "action_gate",            "prompt_version": "v1", "prompt_hash": "d" * 64},
]

_PROMPTS_V2 = [
    {"prompt_name": "router",                 "prompt_version": "v1", "prompt_hash": "a" * 64},
    {"prompt_name": "fraud_analyzer_summary", "prompt_version": "v1", "prompt_hash": "b" * 64},
    {"prompt_name": "explanation",            "prompt_version": "v2", "prompt_hash": "e" * 64},  # changed
    {"prompt_name": "action_gate",            "prompt_version": "v1", "prompt_hash": "d" * 64},
]


def _perfect_report(**overrides) -> BenchmarkReport:
    defaults = dict(
        generated_at="2026-05-17T10:00:00+00:00",
        total_scenarios=16,
        total_passed=16,
        total_failed=0,
        pass_rate=1.0,
        failed_scenario_ids=[],
        failed_evaluator_names=[],
        severity_accuracy=1.0,
        evidence_completeness_avg=1.0,
        false_positive_pass_rate=1.0,
        hallucination_failure_count=0,
        average_latency_ms=4.7,
        slowest_scenarios=[],
        scenario_breakdown=[],
        known_gaps=[],
        next_improvements=[],
        prompts_used=_PROMPTS_V1,
    )
    defaults.update(overrides)
    return BenchmarkReport(**defaults)


def _write_report(path: Path, report: BenchmarkReport) -> None:
    path.write_text(json.dumps(asdict(report), indent=2))


# ---------------------------------------------------------------------------
# compare_reports — metric deltas
# ---------------------------------------------------------------------------

def test_identical_reports_all_metrics_unchanged() -> None:
    base = _perfect_report()
    current = _perfect_report(generated_at="2026-05-17T14:00:00+00:00")
    comparison = compare_reports(base, current)

    assert all(d.direction == "unchanged" for d in comparison.metric_deltas)


def test_all_six_metrics_present() -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    metric_names = [d.metric for d in comparison.metric_deltas]

    assert "pass_rate" in metric_names
    assert "severity_accuracy" in metric_names
    assert "evidence_completeness_avg" in metric_names
    assert "false_positive_pass_rate" in metric_names
    assert "hallucination_failure_count" in metric_names
    assert "average_latency_ms" in metric_names
    assert len(metric_names) == 6


def test_degraded_pass_rate_detected() -> None:
    base = _perfect_report()
    current = _perfect_report(pass_rate=0.8, total_passed=13, total_failed=3)
    comparison = compare_reports(base, current)

    delta = _get_delta(comparison, "pass_rate")
    assert delta.direction == "degraded"
    assert delta.delta == pytest.approx(-0.2, abs=1e-5)
    assert delta.base == pytest.approx(1.0)
    assert delta.current == pytest.approx(0.8)


def test_improved_pass_rate_detected() -> None:
    base = _perfect_report(pass_rate=0.8, total_passed=13, total_failed=3)
    current = _perfect_report()
    comparison = compare_reports(base, current)

    delta = _get_delta(comparison, "pass_rate")
    assert delta.direction == "improved"
    assert delta.delta == pytest.approx(0.2, abs=1e-5)


def test_improved_severity_accuracy_detected() -> None:
    base = _perfect_report(severity_accuracy=0.875)
    current = _perfect_report(severity_accuracy=1.0)
    comparison = compare_reports(base, current)

    delta = _get_delta(comparison, "severity_accuracy")
    assert delta.direction == "improved"
    assert delta.delta == pytest.approx(0.125, abs=1e-5)


def test_degraded_severity_accuracy_detected() -> None:
    base = _perfect_report(severity_accuracy=1.0)
    current = _perfect_report(severity_accuracy=0.75)
    comparison = compare_reports(base, current)

    delta = _get_delta(comparison, "severity_accuracy")
    assert delta.direction == "degraded"


def test_degraded_latency_detected() -> None:
    base = _perfect_report(average_latency_ms=4.7)
    current = _perfect_report(average_latency_ms=12.5)
    comparison = compare_reports(base, current)

    delta = _get_delta(comparison, "average_latency_ms")
    assert delta.direction == "degraded"
    assert delta.delta == pytest.approx(7.8, abs=1e-4)


def test_improved_latency_detected() -> None:
    base = _perfect_report(average_latency_ms=12.5)
    current = _perfect_report(average_latency_ms=4.7)
    comparison = compare_reports(base, current)

    delta = _get_delta(comparison, "average_latency_ms")
    assert delta.direction == "improved"
    assert delta.delta < 0


def test_degraded_hallucination_count_detected() -> None:
    base = _perfect_report(hallucination_failure_count=0)
    current = _perfect_report(hallucination_failure_count=2, total_failed=2, pass_rate=0.875)
    comparison = compare_reports(base, current)

    delta = _get_delta(comparison, "hallucination_failure_count")
    assert delta.direction == "degraded"
    assert delta.delta == pytest.approx(2.0)


def test_improved_hallucination_count_detected() -> None:
    base = _perfect_report(hallucination_failure_count=3)
    current = _perfect_report(hallucination_failure_count=0)
    comparison = compare_reports(base, current)

    delta = _get_delta(comparison, "hallucination_failure_count")
    assert delta.direction == "improved"
    assert delta.delta == pytest.approx(-3.0)


# ---------------------------------------------------------------------------
# compare_reports — scenario changes
# ---------------------------------------------------------------------------

def test_no_scenario_changes_on_identical_reports() -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    assert comparison.newly_failed == []
    assert comparison.newly_passing == []


def test_newly_failed_scenarios_detected() -> None:
    base = _perfect_report(failed_scenario_ids=[])
    current = _perfect_report(
        failed_scenario_ids=["split_payments", "duplicate_invoice"],
        pass_rate=0.875,
    )
    comparison = compare_reports(base, current)

    assert "split_payments" in comparison.newly_failed
    assert "duplicate_invoice" in comparison.newly_failed
    assert comparison.newly_passing == []


def test_newly_passing_scenarios_detected() -> None:
    base = _perfect_report(failed_scenario_ids=["vendor_concentration"])
    current = _perfect_report(failed_scenario_ids=[])
    comparison = compare_reports(base, current)

    assert "vendor_concentration" in comparison.newly_passing
    assert comparison.newly_failed == []


def test_both_newly_failed_and_newly_passing() -> None:
    base = _perfect_report(failed_scenario_ids=["scenario_a"])
    current = _perfect_report(failed_scenario_ids=["scenario_b"])
    comparison = compare_reports(base, current)

    assert comparison.newly_failed == ["scenario_b"]
    assert comparison.newly_passing == ["scenario_a"]


def test_newly_failed_is_sorted() -> None:
    base = _perfect_report(failed_scenario_ids=[])
    current = _perfect_report(failed_scenario_ids=["z_scenario", "a_scenario"])
    comparison = compare_reports(base, current)
    assert comparison.newly_failed == sorted(comparison.newly_failed)


# ---------------------------------------------------------------------------
# compare_reports — prompt changes
# ---------------------------------------------------------------------------

def test_no_prompt_changes_when_hashes_match() -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    assert all(not p.changed for p in comparison.prompt_changes)


def test_prompt_hash_change_detected() -> None:
    base = _perfect_report(prompts_used=_PROMPTS_V1)
    current = _perfect_report(prompts_used=_PROMPTS_V2)
    comparison = compare_reports(base, current)

    explanation_change = next(
        p for p in comparison.prompt_changes if p.prompt_name == "explanation"
    )
    assert explanation_change.changed is True
    assert explanation_change.base_hash == "c" * 64
    assert explanation_change.current_hash == "e" * 64


def test_unchanged_prompts_not_flagged_as_changed() -> None:
    base = _perfect_report(prompts_used=_PROMPTS_V1)
    current = _perfect_report(prompts_used=_PROMPTS_V2)
    comparison = compare_reports(base, current)

    router_change = next(p for p in comparison.prompt_changes if p.prompt_name == "router")
    assert router_change.changed is False


def test_prompt_added_in_current() -> None:
    base = _perfect_report(prompts_used=[])
    current = _perfect_report(prompts_used=_PROMPTS_V1)
    comparison = compare_reports(base, current)

    # All prompts appear as changes since base had no hash to match
    assert len(comparison.prompt_changes) == len(_PROMPTS_V1)
    assert all(p.changed for p in comparison.prompt_changes)


def test_prompt_removed_in_current() -> None:
    base = _perfect_report(prompts_used=_PROMPTS_V1)
    current = _perfect_report(prompts_used=[])
    comparison = compare_reports(base, current)

    assert len(comparison.prompt_changes) == len(_PROMPTS_V1)
    assert all(p.changed for p in comparison.prompt_changes)


def test_no_prompt_changes_section_when_both_empty() -> None:
    base = _perfect_report(prompts_used=[])
    current = _perfect_report(prompts_used=[])
    comparison = compare_reports(base, current)
    assert comparison.prompt_changes == []


def test_prompt_changes_sorted_by_name() -> None:
    comparison = compare_reports(
        _perfect_report(prompts_used=_PROMPTS_V1),
        _perfect_report(prompts_used=_PROMPTS_V2),
    )
    names = [p.prompt_name for p in comparison.prompt_changes]
    assert names == sorted(names)


# ---------------------------------------------------------------------------
# comparison_to_json
# ---------------------------------------------------------------------------

def test_json_comparison_is_valid_json() -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    raw = comparison_to_json(comparison)
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)


def test_json_comparison_has_required_top_level_keys() -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    data = json.loads(comparison_to_json(comparison))

    assert "base_generated_at" in data
    assert "current_generated_at" in data
    assert "metric_deltas" in data
    assert "newly_failed" in data
    assert "newly_passing" in data
    assert "prompt_changes" in data


def test_json_metric_deltas_have_all_fields() -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    data = json.loads(comparison_to_json(comparison))

    for entry in data["metric_deltas"]:
        assert "metric" in entry
        assert "base" in entry
        assert "current" in entry
        assert "delta" in entry
        assert "direction" in entry


def test_json_prompt_changes_have_all_fields() -> None:
    comparison = compare_reports(
        _perfect_report(prompts_used=_PROMPTS_V1),
        _perfect_report(prompts_used=_PROMPTS_V2),
    )
    data = json.loads(comparison_to_json(comparison))

    for entry in data["prompt_changes"]:
        assert "prompt_name" in entry
        assert "base_hash" in entry
        assert "current_hash" in entry
        assert "changed" in entry


def test_json_degradation_values_are_accurate() -> None:
    base = _perfect_report(pass_rate=1.0)
    current = _perfect_report(pass_rate=0.8)
    comparison = compare_reports(base, current)
    data = json.loads(comparison_to_json(comparison))

    pr = next(d for d in data["metric_deltas"] if d["metric"] == "pass_rate")
    assert pr["base"] == pytest.approx(1.0)
    assert pr["current"] == pytest.approx(0.8)
    assert pr["delta"] == pytest.approx(-0.2, abs=1e-5)
    assert pr["direction"] == "degraded"


# ---------------------------------------------------------------------------
# comparison_to_markdown
# ---------------------------------------------------------------------------

def test_markdown_has_required_sections() -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    md = comparison_to_markdown(comparison)

    assert "# Brevix AI Benchmark Comparison" in md
    assert "## Metric Deltas" in md
    assert "## Scenario Changes" in md


def test_markdown_includes_prompt_changes_section_when_present() -> None:
    comparison = compare_reports(
        _perfect_report(prompts_used=_PROMPTS_V1),
        _perfect_report(prompts_used=_PROMPTS_V2),
    )
    md = comparison_to_markdown(comparison)
    assert "## Prompt Changes" in md


def test_markdown_omits_prompt_changes_when_none() -> None:
    comparison = compare_reports(
        _perfect_report(prompts_used=[]),
        _perfect_report(prompts_used=[]),
    )
    md = comparison_to_markdown(comparison)
    assert "## Prompt Changes" not in md


def test_markdown_marks_changed_prompt_as_yes() -> None:
    comparison = compare_reports(
        _perfect_report(prompts_used=_PROMPTS_V1),
        _perfect_report(prompts_used=_PROMPTS_V2),
    )
    md = comparison_to_markdown(comparison)
    assert "YES" in md


def test_markdown_newly_failed_scenario_appears() -> None:
    base = _perfect_report(failed_scenario_ids=[])
    current = _perfect_report(failed_scenario_ids=["rogue_scenario"])
    comparison = compare_reports(base, current)
    md = comparison_to_markdown(comparison)
    assert "rogue_scenario" in md


def test_markdown_informational_note_present() -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    md = comparison_to_markdown(comparison)
    assert "Informational only" in md


def test_markdown_timestamps_in_header() -> None:
    base = _perfect_report(generated_at="2026-05-15T10:00:00+00:00")
    current = _perfect_report(generated_at="2026-05-17T14:00:00+00:00")
    comparison = compare_reports(base, current)
    md = comparison_to_markdown(comparison)
    assert "2026-05-15T10:00:00" in md
    assert "2026-05-17T14:00:00" in md


# ---------------------------------------------------------------------------
# print_comparison — console output
# ---------------------------------------------------------------------------

def test_print_comparison_includes_metric_names(capsys: pytest.CaptureFixture) -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    print_comparison(comparison)
    out = capsys.readouterr().out
    assert "pass_rate" in out
    assert "average_latency_ms" in out


def test_print_comparison_shows_informational_note(capsys: pytest.CaptureFixture) -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    print_comparison(comparison)
    out = capsys.readouterr().out
    assert "Informational only" in out


def test_print_comparison_shows_prompt_changed(capsys: pytest.CaptureFixture) -> None:
    comparison = compare_reports(
        _perfect_report(prompts_used=_PROMPTS_V1),
        _perfect_report(prompts_used=_PROMPTS_V2),
    )
    print_comparison(comparison)
    out = capsys.readouterr().out
    assert "CHANGED" in out
    assert "explanation" in out


def test_print_comparison_summary_line(capsys: pytest.CaptureFixture) -> None:
    comparison = compare_reports(_perfect_report(), _perfect_report())
    print_comparison(comparison)
    out = capsys.readouterr().out
    assert "Summary:" in out


# ---------------------------------------------------------------------------
# CLI — compare_benchmark_reports.py main()
# ---------------------------------------------------------------------------

def test_cli_returns_0_for_identical_reports(tmp_path: Path) -> None:
    p = tmp_path / "report.json"
    _write_report(p, _perfect_report())
    assert main(["--base", str(p), "--current", str(p)]) == 0


def test_cli_returns_0_even_when_metrics_degraded(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    _write_report(base, _perfect_report())
    _write_report(current, _perfect_report(pass_rate=0.5, total_failed=8))
    # Comparison is informational — always exits 0 on success
    assert main(["--base", str(base), "--current", str(current)]) == 0


def test_cli_returns_1_for_missing_base(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    _write_report(current, _perfect_report())
    assert main(["--base", str(tmp_path / "missing.json"), "--current", str(current)]) == 1


def test_cli_returns_1_for_missing_current(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    _write_report(base, _perfect_report())
    assert main(["--base", str(base), "--current", str(tmp_path / "missing.json")]) == 1


def test_cli_returns_1_for_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json")
    good = tmp_path / "good.json"
    _write_report(good, _perfect_report())
    assert main(["--base", str(bad), "--current", str(good)]) == 1


def test_cli_writes_json_output(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    out = tmp_path / "comparison.json"
    _write_report(base, _perfect_report())
    _write_report(current, _perfect_report(pass_rate=0.9))

    main(["--base", str(base), "--current", str(current), "--output-json", str(out)])

    assert out.exists()
    data = json.loads(out.read_text())
    assert "metric_deltas" in data
    assert "newly_failed" in data


def test_cli_writes_md_output(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    current = tmp_path / "current.json"
    out = tmp_path / "comparison.md"
    _write_report(base, _perfect_report())
    _write_report(current, _perfect_report())

    main(["--base", str(base), "--current", str(current), "--output-md", str(out)])

    assert out.exists()
    md = out.read_text()
    assert "# Brevix AI Benchmark Comparison" in md


def test_cli_creates_parent_dirs_for_output(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    _write_report(base, _perfect_report())
    nested_out = tmp_path / "subdir" / "deep" / "comparison.json"

    main(["--base", str(base), "--current", str(base), "--output-json", str(nested_out)])
    assert nested_out.exists()


def test_cli_handles_json_array_as_report(tmp_path: Path) -> None:
    bad = tmp_path / "array.json"
    bad.write_text("[]")
    good = tmp_path / "good.json"
    _write_report(good, _perfect_report())
    assert main(["--base", str(bad), "--current", str(good)]) == 1


# ---------------------------------------------------------------------------
# load_report
# ---------------------------------------------------------------------------

def test_load_report_raises_compare_error_for_missing_file(tmp_path: Path) -> None:
    with pytest.raises(CompareError, match="not found"):
        load_report(tmp_path / "nonexistent.json")


def test_load_report_raises_compare_error_for_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("not json")
    with pytest.raises(CompareError, match="Invalid JSON"):
        load_report(p)


def test_load_report_raises_compare_error_for_missing_fields(tmp_path: Path) -> None:
    p = tmp_path / "sparse.json"
    p.write_text('{"total_scenarios": 1}')
    with pytest.raises(CompareError, match="unexpected structure"):
        load_report(p)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_delta(comparison: ReportComparison, metric: str) -> MetricDelta:
    return next(d for d in comparison.metric_deltas if d.metric == metric)
