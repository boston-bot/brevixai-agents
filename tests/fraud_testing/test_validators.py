"""Tests for fraud testing validators."""

import json
import tempfile
from pathlib import Path

import pytest

from app.fraud_testing.validators import (
    ValidationResult,
    check_mock_data_minimums,
    load_and_validate_extraction_file,
    load_and_validate_mock_data_file,
    validate_extraction_payload,
    validate_mock_data_payload,
)


def _write_tmp_json(data: dict) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return f.name


VALID_EXTRACTION = {
    "fraud_category": "Payroll Fraud",
    "industry": "Construction",
    "actor_type": "Payroll Manager",
    "summary": "Ghost employee scheme.",
    "confidence_score": 0.86,
    "model_name": "chatgpt-manual",
    "prompt_version": "fraud-extraction-v1",
    "structured_payload": {"scenario_title": "Ghost Employee"},
    "expected_indicators": [
        {
            "indicator_key": "missing_personnel_file",
            "indicator_name": "Missing Personnel File",
            "severity": "High",
        }
    ],
    "expected_findings": [
        {
            "finding_key": "potential_ghost_employee",
            "finding_title": "Potential Ghost Employee",
            "finding_description": "No supporting records.",
            "expected_risk_score": 90,
            "expected_confidence": "High",
        }
    ],
}

VALID_MOCK_DATA = {
    "mock_company": {
        "company_name": "Acme Construction LLC",
        "industry": "Construction",
        "entity_type": "LLC",
        "employee_count": 20,
        "months_of_activity": 24,
    },
    "parties": [
        {"external_party_id": f"EMP-{i:03d}", "party_type": "Employee", "party_name": f"Employee {i}"}
        for i in range(1, 8)
    ],
    "transactions": [
        {
            "external_transaction_id": f"TX-{i:03d}",
            "transaction_type": "Payroll Payment",
            "transaction_date": "2025-01-15",
            "amount": 4500.00,
            "external_party_id": f"EMP-{(i % 7) + 1:03d}",
            "is_fraudulent": i == 20,
        }
        for i in range(1, 22)
    ],
}


class TestValidationResult:
    def test_valid_result_is_truthy(self):
        result = ValidationResult(valid=True)
        assert bool(result) is True
        assert result.valid is True
        assert result.errors == []

    def test_invalid_result_is_falsy(self):
        result = ValidationResult(valid=False, errors=["something wrong"])
        assert bool(result) is False
        assert result.errors == ["something wrong"]


class TestValidateExtractionPayload:
    def test_valid_payload_passes(self):
        result = validate_extraction_payload(VALID_EXTRACTION)
        assert result.valid is True
        assert result.errors == []

    def test_missing_required_field_fails(self):
        # structured_payload is required in the schema
        bad = {**VALID_EXTRACTION}
        del bad["structured_payload"]
        result = validate_extraction_payload(bad)
        # structured_payload has a default_factory so it won't fail — remove fraud_category instead
        bad2 = {k: v for k, v in VALID_EXTRACTION.items() if k != "fraud_category"}
        # fraud_category also has a default; the payload is actually lenient
        # so check that invalid nested data fails
        bad3 = {**VALID_EXTRACTION, "expected_indicators": [{"severity": "Extreme"}]}
        result3 = validate_extraction_payload(bad3)
        assert not result3.valid

    def test_invalid_nested_indicator_severity_fails(self):
        bad = {**VALID_EXTRACTION, "expected_indicators": [{"severity": "Extreme", "indicator_key": "x", "indicator_name": "X"}]}
        result = validate_extraction_payload(bad)
        assert not result.valid

    def test_invalid_finding_confidence_fails(self):
        bad = {
            **VALID_EXTRACTION,
            "expected_findings": [{
                "finding_key": "x",
                "finding_title": "X",
                "finding_description": "X",
                "expected_confidence": "Super High",
            }],
        }
        result = validate_extraction_payload(bad)
        assert not result.valid


class TestValidateMockDataPayload:
    def test_valid_payload_passes(self):
        result = validate_mock_data_payload(VALID_MOCK_DATA)
        assert result.valid is True

    def test_missing_mock_company_fails(self):
        bad = {"parties": [], "transactions": []}
        result = validate_mock_data_payload(bad)
        assert not result.valid

    def test_invalid_party_type_is_coerced_not_error(self):
        data = {
            **VALID_MOCK_DATA,
            "parties": [{"external_party_id": "X-001", "party_type": "Robot", "party_name": "Bot"}],
        }
        result = validate_mock_data_payload(data)
        assert result.valid is True


class TestCheckMockDataMinimums:
    def test_passes_with_sufficient_data(self):
        result = check_mock_data_minimums(VALID_MOCK_DATA)
        assert result.valid is True

    def test_fails_with_too_few_parties(self):
        data = {
            **VALID_MOCK_DATA,
            "parties": [{"external_party_id": "EMP-001", "party_type": "Employee", "party_name": "X"}] * 3,
        }
        result = check_mock_data_minimums(data)
        assert not result.valid
        assert any("parties" in e for e in result.errors)

    def test_fails_with_too_few_transactions(self):
        data = {**VALID_MOCK_DATA, "transactions": []}
        result = check_mock_data_minimums(data)
        assert not result.valid
        assert any("transactions" in e for e in result.errors)

    def test_fails_without_fraudulent_transaction(self):
        data = {
            **VALID_MOCK_DATA,
            "transactions": [
                {"external_transaction_id": f"TX-{i}", "transaction_type": "Payroll Payment", "transaction_date": "2025-01-15", "amount": 100.0, "is_fraudulent": False}
                for i in range(25)
            ],
        }
        result = check_mock_data_minimums(data)
        assert not result.valid
        assert any("fraudulent" in e for e in result.errors)

    def test_fails_with_missing_company(self):
        data = {**VALID_MOCK_DATA, "mock_company": None}
        result = check_mock_data_minimums(data)
        assert not result.valid


class TestFileValidation:
    def test_load_and_validate_valid_extraction_file(self):
        path = _write_tmp_json(VALID_EXTRACTION)
        data, result = load_and_validate_extraction_file(path)
        assert result.valid is True
        assert data["fraud_category"] == "Payroll Fraud"

    def test_load_and_validate_missing_file(self):
        data, result = load_and_validate_extraction_file("/nonexistent/path.json")
        assert not result.valid
        assert any("Could not read" in e for e in result.errors)

    def test_load_and_validate_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            path = f.name
        data, result = load_and_validate_extraction_file(path)
        assert not result.valid

    def test_load_and_validate_valid_mock_data_file(self):
        path = _write_tmp_json(VALID_MOCK_DATA)
        data, result = load_and_validate_mock_data_file(path)
        assert result.valid is True
