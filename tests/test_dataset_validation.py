"""Tests for benchmark dataset validation rules (Phase 2.12)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.validate_benchmark_dataset import (
    validate_scenario,
    validate_dataset_file,
)


def _make_valid_scenario() -> dict:
    """Helper to return a fully valid scenario dictionary."""
    return {
        "scenario_id": "test_scenario_id",
        "title": "Valid Test Scenario Title",
        "category": "accounts_payable",
        "risk_type": "duplicate_invoice",
        "severity": "high",
        "tags": ["vendor", "payments"],
        "input_prompt": "Please review this month for duplicate invoice risk.",
        "expected_findings": ["duplicate invoice"],
        "expected_severity": "high",
        "expected_evidence_patterns": [
            {"type": "transaction", "min_count": 2}
        ],
        "expected_recommended_action": "review_findings",
        "false_positive_guardrails": ["employee-vendor overlap", "payroll anomaly"],
    }


# ---------------------------------------------------------------------------
# Valid scenario check
# ---------------------------------------------------------------------------

def test_valid_scenario_passes() -> None:
    scenario = _make_valid_scenario()
    errors = validate_scenario(scenario, 0)
    assert not errors, f"Expected valid scenario to pass, got errors: {errors}"


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "missing_field",
    [
        "title",
        "category",
        "risk_type",
        "severity",
        "tags",
        "input_prompt",
        "expected_findings",
        "expected_severity",
        "expected_evidence_patterns",
        "expected_recommended_action",
        "false_positive_guardrails",
    ],
)
def test_missing_required_field_fails(missing_field: str) -> None:
    scenario = _make_valid_scenario()
    del scenario[missing_field]
    errors = validate_scenario(scenario, 0)
    assert errors, f"Expected failure when '{missing_field}' is missing"
    assert any(missing_field in err for err in errors)


def test_missing_both_id_fields_fails() -> None:
    scenario = _make_valid_scenario()
    del scenario["scenario_id"]
    if "id" in scenario:
        del scenario["id"]
    errors = validate_scenario(scenario, 0)
    assert errors
    assert any("missing both 'scenario_id' and 'id'" in err for err in errors)


# ---------------------------------------------------------------------------
# Valid vs Invalid Severity Values
# ---------------------------------------------------------------------------

def test_valid_severity_values_pass() -> None:
    for sev in ["info", "low", "medium", "high", "critical", "INFO", "High"]:
        scenario = _make_valid_scenario()
        scenario["severity"] = sev
        scenario["expected_severity"] = sev
        errors = validate_scenario(scenario, 0)
        assert not errors, f"Expected severity '{sev}' to pass, got: {errors}"


def test_invalid_severity_fails() -> None:
    scenario = _make_valid_scenario()
    scenario["severity"] = "super_critical"
    errors = validate_scenario(scenario, 0)
    assert errors
    assert any("invalid severity" in err for err in errors)

    scenario = _make_valid_scenario()
    scenario["expected_severity"] = "none"
    errors = validate_scenario(scenario, 0)
    assert errors
    assert any("invalid expected_severity" in err for err in errors)


# ---------------------------------------------------------------------------
# Tags Validation
# ---------------------------------------------------------------------------

def test_empty_tags_fail() -> None:
    scenario = _make_valid_scenario()
    scenario["tags"] = []
    errors = validate_scenario(scenario, 0)
    assert errors
    assert any("tags' cannot be empty" in err for err in errors)


def test_invalid_tags_type_fails() -> None:
    scenario = _make_valid_scenario()
    scenario["tags"] = "not_a_list"
    errors = validate_scenario(scenario, 0)
    assert errors
    assert any("must be a list" in err for err in errors)


def test_non_string_tags_fail() -> None:
    scenario = _make_valid_scenario()
    scenario["tags"] = ["valid", 123, ""]
    errors = validate_scenario(scenario, 0)
    assert errors
    assert any("must be a non-empty string" in err for err in errors)


# ---------------------------------------------------------------------------
# Expected findings, evidence, guardrails validation
# ---------------------------------------------------------------------------

def test_empty_expected_findings_fails() -> None:
    scenario = _make_valid_scenario()
    scenario["expected_findings"] = []
    errors = validate_scenario(scenario, 0)
    assert errors
    assert any("expected_findings' cannot be empty" in err for err in errors)


def test_empty_expected_evidence_patterns_fails() -> None:
    scenario = _make_valid_scenario()
    scenario["expected_evidence_patterns"] = []
    errors = validate_scenario(scenario, 0)
    assert errors
    assert any("expected_evidence_patterns' cannot be empty" in err for err in errors)


def test_empty_false_positive_guardrails_fails() -> None:
    scenario = _make_valid_scenario()
    scenario["false_positive_guardrails"] = []
    errors = validate_scenario(scenario, 0)
    assert errors
    assert any("false_positive_guardrails' cannot be empty" in err for err in errors)


# ---------------------------------------------------------------------------
# Scenario ID format (lowercase snake_case)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_id",
    [
        "camelCaseScenario",
        "Kebab-Case-Scenario",
        "Scenario_With_Caps",
        "scenario with spaces",
        "scenario-id-with-dashes",
    ],
)
def test_invalid_scenario_id_format_fails(bad_id: str) -> None:
    scenario = _make_valid_scenario()
    scenario["scenario_id"] = bad_id
    errors = validate_scenario(scenario, 0)
    assert errors
    assert any("must be lowercase snake_case" in err for err in errors)


# ---------------------------------------------------------------------------
# Prohibited sensitive fields detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "sensitive_key",
    [
        "ssn",
        "social_security_number",
        "password",
        "api_key",
        "secret",
        "secret_key",
        "private_key",
        "routing_number",
        "credit_card",
        "cvv",
        "pin",
    ],
)
def test_prohibited_sensitive_payload_fields_fail(sensitive_key: str) -> None:
    # 1. Prohibited field as a top-level key
    scenario = _make_valid_scenario()
    scenario[sensitive_key] = "confidential_data"
    errors = validate_scenario(scenario, 0)
    assert errors, f"Expected top-level prohibited field '{sensitive_key}' to fail"
    assert any("prohibited sensitive field" in err for err in errors)

    # 2. Prohibited field nested inside nested payloads (e.g. seeded employee or vendor)
    scenario = _make_valid_scenario()
    scenario["seeded_vendors"] = [
        {"vendor_id": "v-1", "name": "Vendor Corp", sensitive_key: "nested_secret"}
    ]
    errors = validate_scenario(scenario, 0)
    assert errors, f"Expected nested prohibited field '{sensitive_key}' to fail"
    assert any("prohibited sensitive field" in err for err in errors)


# ---------------------------------------------------------------------------
# File Validation (Duplicate checking)
# ---------------------------------------------------------------------------

def test_valid_dataset_file_passes(tmp_path: Path) -> None:
    dataset = [
        _make_valid_scenario(),
        {**_make_valid_scenario(), "scenario_id": "test_scenario_2"},
    ]
    filepath = tmp_path / "dataset.json"
    filepath.write_text(json.dumps(dataset))

    success = validate_dataset_file(filepath)
    assert success


def test_duplicate_scenario_id_fails(tmp_path: Path) -> None:
    dataset = [
        _make_valid_scenario(),
        _make_valid_scenario(),  # duplicate ID: test_scenario_id
    ]
    filepath = tmp_path / "dataset.json"
    filepath.write_text(json.dumps(dataset))

    success = validate_dataset_file(filepath)
    assert not success
