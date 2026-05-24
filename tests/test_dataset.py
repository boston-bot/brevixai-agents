"""Tests for dataset loading, metadata validation, and scenario filtering."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluators.dataset import (
    DatasetValidationError,
    build_active_filters,
    filter_dataset,
    load_dataset,
    validate_dataset,
    validate_scenario,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_scenario(
    scenario_id: str = "test_scenario",
    *,
    expected_severity: str = "high",
    category: str = "accounts_payable",
    risk_type: str = "duplicate_invoice",
    tags: list | None = None,
) -> dict:
    return {
        "id": scenario_id,
        "expected_severity": expected_severity,
        "category": category,
        "risk_type": risk_type,
        "tags": tags if tags is not None else ["vendor", "payments"],
    }


def _write_dataset(tmp_path: Path, scenarios: list[dict]) -> Path:
    p = tmp_path / "dataset.json"
    p.write_text(json.dumps(scenarios))
    return p


# ---------------------------------------------------------------------------
# validate_scenario — required field checks
# ---------------------------------------------------------------------------

def test_valid_scenario_passes_validation() -> None:
    validate_scenario(_make_scenario(), 0)  # must not raise


def test_missing_id_raises() -> None:
    s = _make_scenario()
    del s["id"]
    with pytest.raises(DatasetValidationError, match="id"):
        validate_scenario(s, 0)


def test_missing_expected_severity_raises() -> None:
    s = _make_scenario()
    del s["expected_severity"]
    with pytest.raises(DatasetValidationError, match="expected_severity"):
        validate_scenario(s, 0)


def test_missing_category_raises() -> None:
    s = _make_scenario()
    del s["category"]
    with pytest.raises(DatasetValidationError, match="category"):
        validate_scenario(s, 0)


def test_missing_risk_type_raises() -> None:
    s = _make_scenario()
    del s["risk_type"]
    with pytest.raises(DatasetValidationError, match="risk_type"):
        validate_scenario(s, 0)


def test_missing_tags_raises() -> None:
    s = _make_scenario()
    del s["tags"]
    with pytest.raises(DatasetValidationError, match="tags"):
        validate_scenario(s, 0)


def test_non_list_tags_raises() -> None:
    s = _make_scenario(tags="vendor")  # type: ignore[arg-type]
    with pytest.raises(DatasetValidationError, match="list"):
        validate_scenario(s, 0)


def test_non_string_tag_raises() -> None:
    s = _make_scenario(tags=["vendor", 42])  # type: ignore[list-item]
    with pytest.raises(DatasetValidationError, match="string"):
        validate_scenario(s, 0)


def test_empty_tags_list_is_valid() -> None:
    s = _make_scenario(tags=[])
    validate_scenario(s, 0)  # must not raise


def test_validate_dataset_validates_all_scenarios() -> None:
    dataset = [
        _make_scenario("a"),
        _make_scenario("b"),
        _make_scenario("c"),
    ]
    validate_dataset(dataset)  # must not raise


def test_validate_dataset_raises_for_invalid_scenario() -> None:
    bad = _make_scenario("bad")
    del bad["category"]
    with pytest.raises(DatasetValidationError, match="category"):
        validate_dataset([_make_scenario("ok"), bad])


# ---------------------------------------------------------------------------
# load_dataset
# ---------------------------------------------------------------------------

def test_load_dataset_returns_validated_list(tmp_path: Path) -> None:
    scenarios = [_make_scenario("a"), _make_scenario("b")]
    p = _write_dataset(tmp_path, scenarios)
    result = load_dataset(p)
    assert isinstance(result, list)
    assert len(result) == 2


def test_load_dataset_raises_for_non_array_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text('{"not": "an array"}')
    with pytest.raises(DatasetValidationError, match="JSON array"):
        load_dataset(p)


def test_load_dataset_raises_for_invalid_scenario(tmp_path: Path) -> None:
    bad = _make_scenario("x")
    del bad["risk_type"]
    p = _write_dataset(tmp_path, [bad])
    with pytest.raises(DatasetValidationError, match="risk_type"):
        load_dataset(p)


def test_load_dataset_validates_production_fixture() -> None:
    """The shipped fraud_benchmarks.json must pass validation."""
    from scripts.run_evals import DATASET_PATH
    result = load_dataset(DATASET_PATH)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# filter_dataset — by category
# ---------------------------------------------------------------------------

def _make_dataset() -> list[dict]:
    return [
        _make_scenario("dup_invoice", category="accounts_payable", risk_type="duplicate_invoice", tags=["vendor", "duplicate", "payments"]),
        _make_scenario("ghost_vendor", category="vendor_management", risk_type="ghost_vendor", tags=["vendor", "onboarding", "entity_graph"]),
        _make_scenario("payroll", category="payroll", risk_type="payroll_fraud", tags=["payroll"]),
        _make_scenario("recon", category="accounting", risk_type="reconciliation_error", tags=["reconciliation", "payments"]),
        _make_scenario("threshold", category="accounts_payable", risk_type="threshold_evasion", tags=["vendor", "threshold", "payments"]),
    ]


def test_filter_by_category_returns_matching_scenarios() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, category="accounts_payable")
    ids = [s["id"] for s in result]
    assert "dup_invoice" in ids
    assert "threshold" in ids
    assert "ghost_vendor" not in ids
    assert "payroll" not in ids


def test_filter_by_category_returns_empty_when_none_match() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, category="does_not_exist")
    assert result == []


# ---------------------------------------------------------------------------
# filter_dataset — by risk_type
# ---------------------------------------------------------------------------

def test_filter_by_risk_type_returns_matching_scenarios() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, risk_type="duplicate_invoice")
    assert len(result) == 1
    assert result[0]["id"] == "dup_invoice"


def test_filter_by_risk_type_returns_empty_when_none_match() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, risk_type="nonexistent_risk")
    assert result == []


# ---------------------------------------------------------------------------
# filter_dataset — by severity
# ---------------------------------------------------------------------------

def test_filter_by_severity_returns_matching_scenarios() -> None:
    dataset = [
        _make_scenario("high_a", expected_severity="high"),
        _make_scenario("high_b", expected_severity="high"),
        _make_scenario("critical_a", expected_severity="critical"),
        _make_scenario("medium_a", expected_severity="medium"),
    ]
    result = filter_dataset(dataset, severity="high")
    assert len(result) == 2
    assert all(s["expected_severity"] == "high" for s in result)


def test_filter_by_severity_returns_empty_when_none_match() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, severity="low")
    assert result == []


# ---------------------------------------------------------------------------
# filter_dataset — by single tag
# ---------------------------------------------------------------------------

def test_filter_by_single_tag_returns_matching_scenarios() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, tags=["payroll"])
    assert len(result) == 1
    assert result[0]["id"] == "payroll"


def test_filter_by_vendor_tag_returns_multiple_scenarios() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, tags=["vendor"])
    ids = [s["id"] for s in result]
    assert "dup_invoice" in ids
    assert "ghost_vendor" in ids
    assert "threshold" in ids
    assert "payroll" not in ids
    assert "recon" not in ids


# ---------------------------------------------------------------------------
# filter_dataset — multiple tags with AND behavior
# ---------------------------------------------------------------------------

def test_filter_by_multiple_tags_requires_all_tags() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, tags=["vendor", "entity_graph"])
    assert len(result) == 1
    assert result[0]["id"] == "ghost_vendor"


def test_filter_by_multiple_tags_returns_empty_when_no_full_match() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, tags=["payroll", "vendor"])
    assert result == []


# ---------------------------------------------------------------------------
# filter_dataset — combined filters (AND across dimensions)
# ---------------------------------------------------------------------------

def test_filter_combines_category_and_tag_with_and() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, category="accounts_payable", tags=["threshold"])
    assert len(result) == 1
    assert result[0]["id"] == "threshold"


def test_filter_combines_severity_and_tag() -> None:
    dataset = [
        _make_scenario("high_vendor", expected_severity="high", tags=["vendor", "payments"]),
        _make_scenario("high_payroll", expected_severity="high", tags=["payroll"]),
        _make_scenario("critical_vendor", expected_severity="critical", tags=["vendor"]),
    ]
    result = filter_dataset(dataset, severity="high", tags=["vendor"])
    assert len(result) == 1
    assert result[0]["id"] == "high_vendor"


# ---------------------------------------------------------------------------
# No matching scenarios — handled safely
# ---------------------------------------------------------------------------

def test_filter_no_match_returns_empty_list_not_error() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset, category="nonexistent", tags=["vendor"])
    assert result == []


def test_filter_no_args_returns_full_dataset() -> None:
    dataset = _make_dataset()
    result = filter_dataset(dataset)
    assert result == dataset


# ---------------------------------------------------------------------------
# build_active_filters
# ---------------------------------------------------------------------------

def test_build_active_filters_empty_when_no_args() -> None:
    filters = build_active_filters()
    assert filters == {}


def test_build_active_filters_includes_set_values() -> None:
    filters = build_active_filters(category="accounts_payable", severity="high")
    assert filters["category"] == "accounts_payable"
    assert filters["severity"] == "high"
    assert "risk_type" not in filters
    assert "tags" not in filters


def test_build_active_filters_includes_tags_when_provided() -> None:
    filters = build_active_filters(tags=["vendor", "entity_graph"])
    assert filters["tags"] == ["vendor", "entity_graph"]


def test_build_active_filters_omits_empty_tags_list() -> None:
    filters = build_active_filters(tags=[])
    assert "tags" not in filters
