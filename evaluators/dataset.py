"""Dataset loading, validation, and filtering for Brevix AI fraud benchmarks."""
from __future__ import annotations

import json
from pathlib import Path


class DatasetValidationError(ValueError):
    pass


_REQUIRED_FIELDS = {"id", "expected_severity", "category", "risk_type"}


def validate_scenario(scenario: dict, index: int) -> None:
    missing = _REQUIRED_FIELDS - scenario.keys()
    if missing:
        raise DatasetValidationError(
            f"Scenario at index {index} missing required fields: {sorted(missing)}"
        )

    scenario_id = scenario.get("id", f"<index {index}>")

    if "tags" not in scenario:
        raise DatasetValidationError(f"Scenario '{scenario_id}' missing 'tags' field")

    tags = scenario["tags"]
    if not isinstance(tags, list):
        raise DatasetValidationError(
            f"Scenario '{scenario_id}' 'tags' must be a list, got {type(tags).__name__}"
        )
    for tag in tags:
        if not isinstance(tag, str):
            raise DatasetValidationError(
                f"Scenario '{scenario_id}' tag {tag!r} must be a string"
            )


def validate_dataset(dataset: list[dict]) -> None:
    for i, scenario in enumerate(dataset):
        validate_scenario(scenario, i)


def load_dataset(path: Path) -> list[dict]:
    """Load and validate a benchmark dataset from a JSON file."""
    with path.open() as f:
        dataset = json.load(f)
    if not isinstance(dataset, list):
        raise DatasetValidationError(
            f"Dataset must be a JSON array, got {type(dataset).__name__}"
        )
    validate_dataset(dataset)
    return dataset


def filter_dataset(
    dataset: list[dict],
    *,
    category: str | None = None,
    risk_type: str | None = None,
    severity: str | None = None,
    tags: list[str] | None = None,
) -> list[dict]:
    """Filter scenarios by metadata. Multiple filters combine with AND."""
    filtered = dataset

    if category is not None:
        filtered = [s for s in filtered if s.get("category") == category]

    if risk_type is not None:
        filtered = [s for s in filtered if s.get("risk_type") == risk_type]

    if severity is not None:
        filtered = [s for s in filtered if s.get("expected_severity") == severity]

    if tags:
        for tag in tags:
            filtered = [s for s in filtered if tag in s.get("tags", [])]

    return filtered


def build_active_filters(
    *,
    category: str | None = None,
    risk_type: str | None = None,
    severity: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Build a dict of active filters, omitting unset values."""
    filters: dict = {}
    if category is not None:
        filters["category"] = category
    if risk_type is not None:
        filters["risk_type"] = risk_type
    if severity is not None:
        filters["severity"] = severity
    if tags:
        filters["tags"] = tags
    return filters
