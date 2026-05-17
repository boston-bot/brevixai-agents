"""Tests for benchmark report generation and failure diagnostics."""
from __future__ import annotations

import json

import pytest

from evaluators.report import (
    BenchmarkReport,
    generate_report,
    report_to_json,
    report_to_markdown,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PASSING_CHECK = {
    "name": "response_contract_validation",
    "passed": True,
    "details": "missing=[], wrong_types=[]",
    "score": 1.0,
}


def _make_checks(
    *,
    severity_passed: bool = True,
    evidence_score: float = 1.0,
    fp_score: float = 1.0,
    hallucination_passed: bool = True,
) -> list[dict]:
    return [
        {"name": "response_contract_validation", "passed": True, "details": "", "score": 1.0},
        {"name": "finding_correctness", "passed": True, "details": "", "score": 1.0},
        {
            "name": "severity_correctness",
            "passed": severity_passed,
            "details": "",
            "score": 1.0 if severity_passed else 0.0,
        },
        {
            "name": "evidence_completeness",
            "passed": evidence_score == 1.0,
            "details": "",
            "score": evidence_score,
        },
        {
            "name": "hallucination_detection",
            "passed": hallucination_passed,
            "details": "",
            "score": 1.0 if hallucination_passed else 0.0,
        },
        {
            "name": "false_positive_rate",
            "passed": fp_score == 1.0,
            "details": "",
            "score": fp_score,
        },
    ]


def _make_result(
    scenario_id: str,
    *,
    passed: bool = True,
    latency_ms: float = 5.0,
    checks: list[dict] | None = None,
) -> dict:
    return {
        "scenario_id": scenario_id,
        "latency_ms": latency_ms,
        "passed": passed,
        "checks": checks if checks is not None else _make_checks(),
        "errors": [],
    }


# ---------------------------------------------------------------------------
# generate_report summary
# ---------------------------------------------------------------------------

def test_generate_report_counts_all_pass() -> None:
    results = [_make_result("a"), _make_result("b"), _make_result("c")]
    report = generate_report(results)

    assert report.total_scenarios == 3
    assert report.total_passed == 3
    assert report.total_failed == 0
    assert report.pass_rate == 1.0
    assert report.failed_scenario_ids == []


def test_generate_report_counts_partial_fail() -> None:
    results = [
        _make_result("pass_1"),
        _make_result(
            "fail_1",
            passed=False,
            checks=_make_checks(severity_passed=False),
        ),
        _make_result("pass_2"),
    ]
    report = generate_report(results)

    assert report.total_scenarios == 3
    assert report.total_passed == 2
    assert report.total_failed == 1
    assert report.pass_rate == pytest.approx(2 / 3, rel=1e-4)
    assert report.failed_scenario_ids == ["fail_1"]


def test_severity_accuracy_average() -> None:
    results = [
        _make_result("a", checks=_make_checks(severity_passed=True)),
        _make_result("b", passed=False, checks=_make_checks(severity_passed=False)),
    ]
    report = generate_report(results)
    assert report.severity_accuracy == pytest.approx(0.5)


def test_evidence_completeness_average() -> None:
    results = [
        _make_result("a", checks=_make_checks(evidence_score=1.0)),
        _make_result("b", checks=_make_checks(evidence_score=0.5)),
    ]
    report = generate_report(results)
    assert report.evidence_completeness_avg == pytest.approx(0.75)


def test_hallucination_failure_count() -> None:
    results = [
        _make_result("a", checks=_make_checks(hallucination_passed=False), passed=False),
        _make_result("b", checks=_make_checks(hallucination_passed=False), passed=False),
        _make_result("c"),
    ]
    report = generate_report(results)
    assert report.hallucination_failure_count == 2


def test_false_positive_pass_rate() -> None:
    results = [
        _make_result("a", checks=_make_checks(fp_score=1.0)),
        _make_result("b", checks=_make_checks(fp_score=0.5), passed=False),
    ]
    report = generate_report(results)
    assert report.false_positive_pass_rate == pytest.approx(0.75)


def test_average_latency() -> None:
    results = [
        _make_result("a", latency_ms=4.0),
        _make_result("b", latency_ms=6.0),
    ]
    report = generate_report(results)
    assert report.average_latency_ms == pytest.approx(5.0)


def test_slowest_scenarios_capped_at_five() -> None:
    results = [_make_result(f"s{i}", latency_ms=float(i)) for i in range(10)]
    report = generate_report(results)
    assert len(report.slowest_scenarios) == 5
    latencies = [s["latency_ms"] for s in report.slowest_scenarios]
    assert latencies == sorted(latencies, reverse=True)


def test_failed_evaluator_names_are_unique_and_sorted() -> None:
    results = [
        _make_result(
            "a",
            passed=False,
            checks=_make_checks(severity_passed=False, hallucination_passed=False),
        ),
        _make_result(
            "b",
            passed=False,
            checks=_make_checks(severity_passed=False),
        ),
    ]
    report = generate_report(results)
    assert report.failed_evaluator_names == sorted(report.failed_evaluator_names)
    assert len(report.failed_evaluator_names) == len(set(report.failed_evaluator_names))
    assert "severity_correctness" in report.failed_evaluator_names
    assert "hallucination_detection" in report.failed_evaluator_names


# ---------------------------------------------------------------------------
# Empty result handling
# ---------------------------------------------------------------------------

def test_empty_results_returns_zero_report() -> None:
    report = generate_report([])

    assert report.total_scenarios == 0
    assert report.total_passed == 0
    assert report.total_failed == 0
    assert report.pass_rate == 0.0
    assert report.severity_accuracy == 0.0
    assert report.evidence_completeness_avg == 0.0
    assert report.false_positive_pass_rate == 0.0
    assert report.hallucination_failure_count == 0
    assert report.average_latency_ms == 0.0
    assert report.failed_scenario_ids == []
    assert report.scenario_breakdown == []
    assert report.slowest_scenarios == []
    assert isinstance(report.known_gaps, list)
    assert isinstance(report.next_improvements, list)


# ---------------------------------------------------------------------------
# JSON report structure
# ---------------------------------------------------------------------------

def test_json_report_has_required_top_level_keys() -> None:
    report = generate_report([_make_result("x")])
    data = json.loads(report_to_json(report))

    required_keys = {
        "generated_at",
        "total_scenarios",
        "total_passed",
        "total_failed",
        "pass_rate",
        "failed_scenario_ids",
        "failed_evaluator_names",
        "severity_accuracy",
        "evidence_completeness_avg",
        "false_positive_pass_rate",
        "hallucination_failure_count",
        "average_latency_ms",
        "slowest_scenarios",
        "scenario_breakdown",
        "known_gaps",
        "next_improvements",
    }
    assert required_keys <= data.keys()


def test_json_report_scenario_breakdown_has_no_sensitive_fields() -> None:
    report = generate_report([_make_result("x")])
    data = json.loads(report_to_json(report))

    sensitive = {"input_prompt", "tool_fixture", "page_context", "seeded_scenario_id"}
    for scenario in data["scenario_breakdown"]:
        assert not sensitive & scenario.keys(), (
            f"Sensitive field found in scenario_breakdown: {sensitive & scenario.keys()}"
        )


def test_json_report_is_valid_json_for_empty_results() -> None:
    report = generate_report([])
    raw = report_to_json(report)
    parsed = json.loads(raw)
    assert parsed["total_scenarios"] == 0


def test_json_report_scenario_breakdown_structure() -> None:
    results = [
        _make_result("pass_a"),
        _make_result("fail_b", passed=False, checks=_make_checks(severity_passed=False)),
    ]
    report = generate_report(results)
    data = json.loads(report_to_json(report))

    for entry in data["scenario_breakdown"]:
        assert "scenario_id" in entry
        assert "passed" in entry
        assert "latency_ms" in entry
        assert "failed_checks" in entry
        assert "check_scores" in entry


# ---------------------------------------------------------------------------
# Markdown report structure
# ---------------------------------------------------------------------------

def test_markdown_has_required_sections() -> None:
    report = generate_report([_make_result("x")])
    md = report_to_markdown(report)

    assert "# Brevix AI Benchmark Report" in md
    assert "## Summary" in md
    assert "## Scenario Breakdown" in md
    assert "## Slowest Scenarios" in md
    assert "## Failed Checks" in md
    assert "## Known Gaps" in md
    assert "## Next Recommended Improvements" in md


def test_markdown_summary_table_has_expected_rows() -> None:
    report = generate_report([_make_result("x")])
    md = report_to_markdown(report)

    assert "Total Scenarios" in md
    assert "Total Passed" in md
    assert "Total Failed" in md
    assert "Pass Rate" in md
    assert "Severity Accuracy" in md
    assert "Evidence Completeness" in md
    assert "False Positive" in md
    assert "Hallucination Failures" in md
    assert "Average Latency" in md


def test_markdown_all_pass_shows_no_failures_message() -> None:
    report = generate_report([_make_result("a"), _make_result("b")])
    md = report_to_markdown(report)
    assert "All scenarios passed" in md


def test_markdown_failed_checks_section_lists_failures() -> None:
    results = [
        _make_result(
            "bad_scenario",
            passed=False,
            checks=_make_checks(severity_passed=False, hallucination_passed=False),
        )
    ]
    report = generate_report(results)
    md = report_to_markdown(report)

    assert "bad_scenario" in md
    assert "severity_correctness" in md
    assert "hallucination_detection" in md


def test_markdown_scenario_breakdown_table_contains_all_ids() -> None:
    results = [_make_result(f"scenario_{i}") for i in range(4)]
    report = generate_report(results)
    md = report_to_markdown(report)

    for i in range(4):
        assert f"scenario_{i}" in md


def test_markdown_has_known_gaps_content() -> None:
    report = generate_report([_make_result("x")])
    md = report_to_markdown(report)
    assert "deterministic" in md.lower()


def test_markdown_has_next_improvements_content() -> None:
    report = generate_report([_make_result("x")])
    md = report_to_markdown(report)
    assert "LLM" in md


# ---------------------------------------------------------------------------
# Failed scenario diagnostics
# ---------------------------------------------------------------------------

def test_diagnostics_all_failed_check_names_captured() -> None:
    checks = _make_checks(
        severity_passed=False,
        evidence_score=0.5,
        fp_score=0.0,
        hallucination_passed=False,
    )
    results = [_make_result("bad", passed=False, checks=checks)]
    report = generate_report(results)

    assert "severity_correctness" in report.failed_evaluator_names
    assert "evidence_completeness" in report.failed_evaluator_names
    assert "false_positive_rate" in report.failed_evaluator_names
    assert "hallucination_detection" in report.failed_evaluator_names


def test_diagnostics_check_scores_in_breakdown() -> None:
    checks = _make_checks(evidence_score=0.75)
    results = [_make_result("s", checks=checks)]
    report = generate_report(results)
    breakdown = report.scenario_breakdown[0]

    assert breakdown["check_scores"]["evidence_completeness"] == pytest.approx(0.75)


def test_diagnostics_multiple_failed_scenarios_all_listed() -> None:
    results = [
        _make_result(f"fail_{i}", passed=False, checks=_make_checks(severity_passed=False))
        for i in range(3)
    ]
    report = generate_report(results)
    assert sorted(report.failed_scenario_ids) == ["fail_0", "fail_1", "fail_2"]
