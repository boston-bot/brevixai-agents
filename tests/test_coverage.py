"""Tests for benchmark coverage matrix computation and formatting."""
from __future__ import annotations

import json
from pathlib import Path

from evaluators.coverage import (
    RECOMMENDED_TAGS,
    compute_coverage,
    coverage_to_json,
    coverage_to_markdown,
)


# ---------------------------------------------------------------------------
# Minimal scenario builder
# ---------------------------------------------------------------------------

def _s(
    sid: str,
    *,
    category: str = "accounts_payable",
    risk_type: str = "duplicate_invoice",
    severity: str = "high",
    tags: list[str] | None = None,
    evidence_patterns: list[dict] | None = None,
    guardrails: list[str] | None = None,
) -> dict:
    return {
        "id": sid,
        "category": category,
        "risk_type": risk_type,
        "expected_severity": severity,
        "tags": tags if tags is not None else ["vendor", "payments"],
        "expected_evidence_patterns": (
            evidence_patterns if evidence_patterns is not None
            else [{"type": "transaction", "min_count": 1}]
        ),
        "false_positive_guardrails": (
            guardrails if guardrails is not None
            else ["ghost vendor", "payroll anomaly"]
        ),
    }


def _dataset(*scenarios: dict) -> list[dict]:
    return list(scenarios)


# ---------------------------------------------------------------------------
# counts by category
# ---------------------------------------------------------------------------

def test_by_category_counts_correctly() -> None:
    ds = _dataset(
        _s("a", category="accounts_payable"),
        _s("b", category="accounts_payable"),
        _s("c", category="vendor_management"),
    )
    m = compute_coverage(ds)
    assert m.by_category["accounts_payable"] == 2
    assert m.by_category["vendor_management"] == 1


def test_by_category_single_entry() -> None:
    ds = _dataset(_s("a", category="payroll"))
    m = compute_coverage(ds)
    assert m.by_category == {"payroll": 1}


def test_by_category_keys_are_sorted() -> None:
    ds = _dataset(
        _s("a", category="vendor_management"),
        _s("b", category="accounts_payable"),
        _s("c", category="payroll"),
    )
    m = compute_coverage(ds)
    assert list(m.by_category.keys()) == sorted(m.by_category.keys())


# ---------------------------------------------------------------------------
# counts by risk_type
# ---------------------------------------------------------------------------

def test_by_risk_type_counts_correctly() -> None:
    ds = _dataset(
        _s("a", risk_type="duplicate_invoice"),
        _s("b", risk_type="duplicate_invoice"),
        _s("c", risk_type="ghost_vendor"),
    )
    m = compute_coverage(ds)
    assert m.by_risk_type["duplicate_invoice"] == 2
    assert m.by_risk_type["ghost_vendor"] == 1


def test_by_risk_type_all_unique() -> None:
    ds = _dataset(
        _s("a", risk_type="x"),
        _s("b", risk_type="y"),
        _s("c", risk_type="z"),
    )
    m = compute_coverage(ds)
    assert m.by_risk_type == {"x": 1, "y": 1, "z": 1}


def test_by_risk_type_keys_are_sorted() -> None:
    ds = _dataset(
        _s("a", risk_type="z_type"),
        _s("b", risk_type="a_type"),
    )
    m = compute_coverage(ds)
    assert list(m.by_risk_type.keys()) == sorted(m.by_risk_type.keys())


# ---------------------------------------------------------------------------
# counts by severity
# ---------------------------------------------------------------------------

def test_by_severity_counts_correctly() -> None:
    ds = _dataset(
        _s("a", severity="high"),
        _s("b", severity="high"),
        _s("c", severity="critical"),
        _s("d", severity="medium"),
    )
    m = compute_coverage(ds)
    assert m.by_severity["high"] == 2
    assert m.by_severity["critical"] == 1
    assert m.by_severity["medium"] == 1


def test_by_severity_missing_level_not_in_dict() -> None:
    ds = _dataset(_s("a", severity="high"))
    m = compute_coverage(ds)
    assert "critical" not in m.by_severity
    assert "medium" not in m.by_severity


def test_by_severity_keys_are_sorted() -> None:
    ds = _dataset(
        _s("a", severity="medium"),
        _s("b", severity="critical"),
        _s("c", severity="high"),
    )
    m = compute_coverage(ds)
    assert list(m.by_severity.keys()) == sorted(m.by_severity.keys())


# ---------------------------------------------------------------------------
# counts by tag
# ---------------------------------------------------------------------------

def test_by_tag_counts_correctly() -> None:
    ds = _dataset(
        _s("a", tags=["vendor", "payments"]),
        _s("b", tags=["vendor", "duplicate"]),
        _s("c", tags=["payroll"]),
    )
    m = compute_coverage(ds)
    assert m.by_tag["vendor"] == 2
    assert m.by_tag["payments"] == 1
    assert m.by_tag["duplicate"] == 1
    assert m.by_tag["payroll"] == 1


def test_by_tag_empty_tags_list_contributes_nothing() -> None:
    ds = _dataset(_s("a", tags=[]))
    m = compute_coverage(ds)
    assert m.by_tag == {}


def test_by_tag_keys_are_sorted() -> None:
    ds = _dataset(_s("a", tags=["vendor", "payroll", "after_hours"]))
    m = compute_coverage(ds)
    assert list(m.by_tag.keys()) == sorted(m.by_tag.keys())


# ---------------------------------------------------------------------------
# missing recommended tag detection
# ---------------------------------------------------------------------------

def test_missing_recommended_tags_identified() -> None:
    ds = _dataset(_s("a", tags=["vendor"]))
    m = compute_coverage(ds)
    # All RECOMMENDED_TAGS except "vendor" should be missing
    for tag in RECOMMENDED_TAGS:
        if tag != "vendor":
            assert tag in m.missing_recommended_tags


def test_no_missing_recommended_tags_when_all_covered() -> None:
    scenarios = [_s(f"s{i}", tags=[tag]) for i, tag in enumerate(RECOMMENDED_TAGS)]
    m = compute_coverage(scenarios)
    assert m.missing_recommended_tags == []


def test_missing_recommended_tags_only_from_recommended_list() -> None:
    ds = _dataset(_s("a", tags=["custom_tag_not_in_list"]))
    m = compute_coverage(ds)
    # custom_tag_not_in_list is not recommended, so it shouldn't affect the missing list
    assert "custom_tag_not_in_list" not in m.missing_recommended_tags
    # All recommended tags are missing
    assert set(m.missing_recommended_tags) == set(RECOMMENDED_TAGS)


# ---------------------------------------------------------------------------
# duplicate scenario_id detection
# ---------------------------------------------------------------------------

def test_no_duplicates_in_clean_dataset() -> None:
    ds = _dataset(_s("a"), _s("b"), _s("c"))
    m = compute_coverage(ds)
    assert m.duplicate_scenario_ids == []


def test_duplicate_scenario_id_detected() -> None:
    ds = _dataset(_s("same_id"), _s("same_id"), _s("other"))
    m = compute_coverage(ds)
    assert "same_id" in m.duplicate_scenario_ids


def test_multiple_duplicates_all_detected() -> None:
    ds = _dataset(_s("dup_a"), _s("dup_a"), _s("dup_b"), _s("dup_b"), _s("unique"))
    m = compute_coverage(ds)
    assert "dup_a" in m.duplicate_scenario_ids
    assert "dup_b" in m.duplicate_scenario_ids
    assert "unique" not in m.duplicate_scenario_ids


def test_duplicate_scenario_ids_sorted() -> None:
    ds = _dataset(_s("z_dup"), _s("z_dup"), _s("a_dup"), _s("a_dup"))
    m = compute_coverage(ds)
    assert m.duplicate_scenario_ids == sorted(m.duplicate_scenario_ids)


# ---------------------------------------------------------------------------
# missing evidence pattern detection
# ---------------------------------------------------------------------------

def test_no_missing_evidence_patterns_in_clean_dataset() -> None:
    ds = _dataset(_s("a"), _s("b"))
    m = compute_coverage(ds)
    assert m.missing_evidence_patterns == []


def test_missing_evidence_patterns_detected_when_empty_list() -> None:
    ds = _dataset(
        _s("has_evidence"),
        _s("no_evidence", evidence_patterns=[]),
    )
    m = compute_coverage(ds)
    assert "no_evidence" in m.missing_evidence_patterns
    assert "has_evidence" not in m.missing_evidence_patterns


def test_missing_evidence_patterns_detected_when_key_absent() -> None:
    scenario = _s("no_key")
    del scenario["expected_evidence_patterns"]
    m = compute_coverage([scenario])
    assert "no_key" in m.missing_evidence_patterns


# ---------------------------------------------------------------------------
# missing false-positive guardrail detection
# ---------------------------------------------------------------------------

def test_no_missing_guardrails_in_clean_dataset() -> None:
    ds = _dataset(_s("a"), _s("b"))
    m = compute_coverage(ds)
    assert m.missing_false_positive_guardrails == []


def test_missing_guardrails_detected_when_empty_list() -> None:
    ds = _dataset(
        _s("has_guardrails"),
        _s("no_guardrails", guardrails=[]),
    )
    m = compute_coverage(ds)
    assert "no_guardrails" in m.missing_false_positive_guardrails
    assert "has_guardrails" not in m.missing_false_positive_guardrails


def test_missing_guardrails_detected_when_key_absent() -> None:
    scenario = _s("no_key")
    del scenario["false_positive_guardrails"]
    m = compute_coverage([scenario])
    assert "no_key" in m.missing_false_positive_guardrails


# ---------------------------------------------------------------------------
# total_scenarios
# ---------------------------------------------------------------------------

def test_total_scenarios_matches_dataset_length() -> None:
    ds = _dataset(_s("a"), _s("b"), _s("c"))
    m = compute_coverage(ds)
    assert m.total_scenarios == 3


def test_total_scenarios_empty_dataset() -> None:
    m = compute_coverage([])
    assert m.total_scenarios == 0


# ---------------------------------------------------------------------------
# recommended_gaps
# ---------------------------------------------------------------------------

def test_gaps_include_missing_recommended_tag() -> None:
    ds = _dataset(_s("a", tags=[]))
    m = compute_coverage(ds)
    all_gaps_text = " ".join(m.recommended_gaps)
    # At least one recommended tag gap should be mentioned
    assert any(tag in all_gaps_text for tag in RECOMMENDED_TAGS)


def test_gaps_include_uncovered_standard_severity() -> None:
    ds = _dataset(_s("a", severity="high"))
    m = compute_coverage(ds)
    gaps_text = " ".join(m.recommended_gaps)
    assert "critical" in gaps_text or "medium" in gaps_text or "low" in gaps_text


def test_gaps_include_thin_category() -> None:
    ds = _dataset(
        _s("a", category="payroll"),  # only 1 in payroll
        _s("b", category="accounts_payable"),
        _s("c", category="accounts_payable"),
    )
    m = compute_coverage(ds)
    gaps_text = " ".join(m.recommended_gaps)
    assert "payroll" in gaps_text


def test_gaps_include_duplicate_ids() -> None:
    ds = _dataset(_s("dup"), _s("dup"), _s("ok"))
    m = compute_coverage(ds)
    gaps_text = " ".join(m.recommended_gaps)
    assert "dup" in gaps_text


def test_gaps_include_missing_evidence() -> None:
    ds = _dataset(_s("bad", evidence_patterns=[]), _s("ok"))
    m = compute_coverage(ds)
    gaps_text = " ".join(m.recommended_gaps)
    assert "bad" in gaps_text


def test_gaps_include_missing_guardrails() -> None:
    ds = _dataset(_s("bad", guardrails=[]), _s("ok"))
    m = compute_coverage(ds)
    gaps_text = " ".join(m.recommended_gaps)
    assert "bad" in gaps_text


def test_no_gaps_when_coverage_is_complete() -> None:
    scenarios = []
    for i, tag in enumerate(RECOMMENDED_TAGS):
        scenarios.append(_s(
            f"s_{i}",
            category="accounts_payable",
            severity="high",
            tags=[tag],
        ))
    # Add scenarios to cover other severities and avoid thin categories
    for i, sev in enumerate(["critical", "medium"], start=len(RECOMMENDED_TAGS)):
        scenarios.append(_s(f"s_{i}", category="accounts_payable", severity=sev))

    m = compute_coverage(scenarios)
    # All recommended tags are covered — no tag gaps
    tag_gaps = [g for g in m.recommended_gaps if "Tag `" in g]
    assert tag_gaps == []
    # Covered severities should not appear in gaps
    for covered_sev in ["high", "critical", "medium"]:
        assert not any(f"Severity `{covered_sev}`" in g for g in m.recommended_gaps)


# ---------------------------------------------------------------------------
# production dataset smoke test
# ---------------------------------------------------------------------------

def test_compute_coverage_on_production_dataset() -> None:
    from evaluators.dataset import load_dataset
    from scripts.run_evals import DATASET_PATH
    dataset = load_dataset(DATASET_PATH)
    m = compute_coverage(dataset)
    assert m.total_scenarios == len(dataset)
    assert m.duplicate_scenario_ids == []
    assert m.missing_evidence_patterns == []
    assert m.missing_false_positive_guardrails == []
    assert len(m.by_category) >= 3
    assert len(m.by_severity) >= 2


# ---------------------------------------------------------------------------
# coverage_to_json
# ---------------------------------------------------------------------------

def test_coverage_to_json_produces_valid_json() -> None:
    ds = _dataset(_s("a"), _s("b"))
    m = compute_coverage(ds)
    raw = coverage_to_json(m)
    parsed = json.loads(raw)
    assert isinstance(parsed, dict)


def test_json_output_has_required_keys() -> None:
    m = compute_coverage(_dataset(_s("a")))
    data = json.loads(coverage_to_json(m))
    required = {
        "generated_at", "total_scenarios", "by_category", "by_risk_type",
        "by_severity", "by_tag", "missing_recommended_tags",
        "duplicate_scenario_ids", "missing_evidence_patterns",
        "missing_false_positive_guardrails", "recommended_gaps",
    }
    assert required <= data.keys()


def test_json_output_counts_match_dataset() -> None:
    ds = _dataset(
        _s("a", category="payroll"),
        _s("b", category="payroll"),
        _s("c", category="accounting"),
    )
    data = json.loads(coverage_to_json(compute_coverage(ds)))
    assert data["total_scenarios"] == 3
    assert data["by_category"]["payroll"] == 2
    assert data["by_category"]["accounting"] == 1


def test_json_output_empty_dataset() -> None:
    data = json.loads(coverage_to_json(compute_coverage([])))
    assert data["total_scenarios"] == 0
    assert data["by_category"] == {}
    assert data["by_tag"] == {}


# ---------------------------------------------------------------------------
# coverage_to_markdown
# ---------------------------------------------------------------------------

def test_markdown_has_required_sections() -> None:
    m = compute_coverage(_dataset(_s("a")))
    md = coverage_to_markdown(m)
    assert "# Brevix AI Benchmark Coverage Matrix" in md
    assert "## Summary" in md
    assert "## Category Coverage" in md
    assert "## Risk Type Coverage" in md
    assert "## Severity Coverage" in md
    assert "## Tag Coverage" in md
    assert "## Data Quality Checks" in md
    assert "## Recommended Gaps to Fill Next" in md


def test_markdown_summary_shows_total_scenarios() -> None:
    ds = _dataset(_s("a"), _s("b"), _s("c"))
    md = coverage_to_markdown(compute_coverage(ds))
    assert "3" in md
    assert "Total scenarios" in md


def test_markdown_category_table_contains_category_names() -> None:
    ds = _dataset(
        _s("a", category="payroll"),
        _s("b", category="accounts_payable"),
    )
    md = coverage_to_markdown(compute_coverage(ds))
    assert "payroll" in md
    assert "accounts_payable" in md


def test_markdown_tag_table_contains_tag_names() -> None:
    ds = _dataset(_s("a", tags=["vendor", "entity_graph"]))
    md = coverage_to_markdown(compute_coverage(ds))
    assert "vendor" in md
    assert "entity_graph" in md


def test_markdown_data_quality_shows_pass_for_clean_dataset() -> None:
    ds = _dataset(_s("a"), _s("b"))
    md = coverage_to_markdown(compute_coverage(ds))
    assert "PASS" in md


def test_markdown_data_quality_shows_fail_for_duplicate() -> None:
    ds = _dataset(_s("dup"), _s("dup"))
    md = coverage_to_markdown(compute_coverage(ds))
    assert "FAIL" in md
    assert "dup" in md


def test_markdown_data_quality_shows_fail_for_missing_evidence() -> None:
    ds = _dataset(_s("bad", evidence_patterns=[]))
    md = coverage_to_markdown(compute_coverage(ds))
    assert "FAIL" in md
    assert "bad" in md


def test_markdown_data_quality_shows_fail_for_missing_guardrails() -> None:
    ds = _dataset(_s("bad", guardrails=[]))
    md = coverage_to_markdown(compute_coverage(ds))
    assert "FAIL" in md
    assert "bad" in md


def test_markdown_recommended_gaps_listed() -> None:
    ds = _dataset(_s("a", tags=[]))  # all recommended tags missing
    md = coverage_to_markdown(compute_coverage(ds))
    assert "Recommended Gaps" in md
    # At least one recommended tag gap should appear
    assert any(tag in md for tag in RECOMMENDED_TAGS)


def test_markdown_no_gaps_message_when_complete() -> None:
    m = compute_coverage(_dataset(_s("a"), _s("b")))
    # Manually clear gaps to test the "no gaps" branch
    m.recommended_gaps = []
    md = coverage_to_markdown(m)
    assert "No gaps identified" in md


# ---------------------------------------------------------------------------
# main() CLI
# ---------------------------------------------------------------------------

def test_main_generates_both_output_files(tmp_path: Path) -> None:
    from scripts.generate_coverage_matrix import main
    from scripts.run_evals import DATASET_PATH
    code = main(["--dataset", str(DATASET_PATH), "--output-dir", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "coverage_matrix.json").exists()
    assert (tmp_path / "coverage_matrix.md").exists()


def test_main_missing_dataset_returns_1(tmp_path: Path) -> None:
    from scripts.generate_coverage_matrix import main
    code = main(["--dataset", str(tmp_path / "does_not_exist.json"), "--output-dir", str(tmp_path)])
    assert code == 1


def test_main_json_output_is_parseable(tmp_path: Path) -> None:
    from scripts.generate_coverage_matrix import main
    from scripts.run_evals import DATASET_PATH
    main(["--dataset", str(DATASET_PATH), "--output-dir", str(tmp_path)])
    data = json.loads((tmp_path / "coverage_matrix.json").read_text())
    assert data["total_scenarios"] > 0


def test_main_md_output_has_title(tmp_path: Path) -> None:
    from scripts.generate_coverage_matrix import main
    from scripts.run_evals import DATASET_PATH
    main(["--dataset", str(DATASET_PATH), "--output-dir", str(tmp_path)])
    md = (tmp_path / "coverage_matrix.md").read_text()
    assert "# Brevix AI Benchmark Coverage Matrix" in md
