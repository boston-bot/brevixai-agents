"""Validators for fraud testing JSON files before import."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.fraud_testing.schemas import ExtractionImportPayload, MockDataImportPayload


class ValidationResult:
    def __init__(self, valid: bool, errors: list[str] | None = None):
        self.valid = valid
        self.errors: list[str] = errors or []

    def __bool__(self) -> bool:
        return self.valid

    def __repr__(self) -> str:
        if self.valid:
            return "ValidationResult(valid=True)"
        return f"ValidationResult(valid=False, errors={self.errors})"


def validate_extraction_payload(data: dict) -> ValidationResult:
    """Validate a dict against ExtractionImportPayload schema."""
    try:
        ExtractionImportPayload(**data)
        return ValidationResult(valid=True)
    except ValidationError as e:
        errors = [f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()]
        return ValidationResult(valid=False, errors=errors)
    except Exception as e:
        return ValidationResult(valid=False, errors=[str(e)])


def validate_mock_data_payload(data: dict) -> ValidationResult:
    """Validate a dict against MockDataImportPayload schema."""
    try:
        MockDataImportPayload(**data)
        return ValidationResult(valid=True)
    except ValidationError as e:
        errors = [f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in e.errors()]
        return ValidationResult(valid=False, errors=errors)
    except Exception as e:
        return ValidationResult(valid=False, errors=[str(e)])


def load_and_validate_extraction_file(path: str | Path) -> tuple[dict, ValidationResult]:
    """Load extraction.json from disk and validate it."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return {}, ValidationResult(valid=False, errors=[f"Could not read file: {e}"])

    return data, validate_extraction_payload(data)


def load_and_validate_mock_data_file(path: str | Path) -> tuple[dict, ValidationResult]:
    """Load mock_data.json from disk and validate it."""
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return {}, ValidationResult(valid=False, errors=[f"Could not read file: {e}"])

    return data, validate_mock_data_payload(data)


def check_mock_data_minimums(data: dict) -> ValidationResult:
    """Check that generated mock data meets V1 minimum requirements."""
    errors = []
    parties = data.get("parties", [])
    transactions = data.get("transactions", [])

    if not data.get("mock_company"):
        errors.append("mock_company is required")

    if len(parties) < 5:
        errors.append(f"At least 5 parties required, got {len(parties)}")

    if len(transactions) < 20:
        errors.append(f"At least 20 transactions required, got {len(transactions)}")

    fraudulent = [t for t in transactions if t.get("is_fraudulent")]
    if not fraudulent:
        errors.append("At least 1 fraudulent transaction is required")

    return ValidationResult(valid=len(errors) == 0, errors=errors)
