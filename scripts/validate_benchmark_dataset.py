#!/usr/bin/env python3
"""Scenario validator CLI for Brevix AI fraud benchmarks.

Validates that benchmark datasets and templates adhere to strict quality rules:
- Required fields are present
- Unique scenario_id
- Valid severity values (info, low, medium, high, critical)
- Non-empty tags list of strings
- Non-empty expected_findings list of strings
- Non-empty expected_evidence_patterns
- Non-empty false_positive_guardrails
- No prohibited sensitive raw payload fields (SSN, routing, password, etc.)
- Lowercase snake_case format for scenario_id
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Color output helpers
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_success(msg: str) -> None:
    print(f"{GREEN}✔ {msg}{RESET}")


def print_error(msg: str) -> None:
    print(f"{RED}✘ {msg}{RESET}", file=sys.stderr)


def print_warn(msg: str) -> None:
    print(f"{YELLOW}⚠ {msg}{RESET}")


def print_info(msg: str) -> None:
    print(f"{BLUE}i {msg}{RESET}")


# Prohibited sensitive keys (PII, credentials, credentials-adjacent keys)
PROHIBITED_SENSITIVE_KEYS = {
    "ssn",
    "socialsecuritynumber",
    "password",
    "apikey",
    "secret",
    "secretkey",
    "privatekey",
    "routingnumber",
    "bankroutingnumber",
    "creditcard",
    "cardnumber",
    "cvv",
    "pin",
}


def normalize_key(key: str) -> str:
    """Normalize a key to lower case without common delimiters for robust matching."""
    return key.lower().replace("_", "").replace("-", "").replace(" ", "")


def scan_prohibited_fields(data: Any, path: str = "") -> list[str]:
    """Recursively scan a JSON structure for prohibited sensitive fields."""
    found = []
    if isinstance(data, dict):
        for k, v in data.items():
            norm_k = normalize_key(k)
            # Exclude false positives like "requires_review" or "requires_human_approval"
            # which might have "secret" or similar if we were too broad, but let's check
            # if the key itself matches any of the normalized prohibited keys
            if norm_k in PROHIBITED_SENSITIVE_KEYS:
                found.append(f"{path}.{k}" if path else k)
            found.extend(scan_prohibited_fields(v, f"{path}.{k}" if path else k))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            found.extend(scan_prohibited_fields(item, f"{path}[{i}]"))
    return found


def validate_scenario(scenario: dict[str, Any], index: int) -> list[str]:
    """Validate a single scenario against dataset quality rules.

    Returns a list of error strings if invalid, or empty list if valid.
    """
    errors = []

    # 1. Alias handling and required fields check
    # Check for scenario_id (we also allow id as a fallback/alias, but scenario_id is expected)
    scenario_id = scenario.get("scenario_id") or scenario.get("id")
    if not scenario_id:
        errors.append(f"Scenario at index {index} is missing both 'scenario_id' and 'id'")
        return errors

    # Check for lowercase snake_case scenario_id
    if not re.match(r"^[a-z0-9_]+$", str(scenario_id)):
        errors.append(
            f"Scenario ID '{scenario_id}' (index {index}) is invalid: must be lowercase snake_case"
        )

    required_fields = [
        "scenario_id",
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
    ]

    for field in required_fields:
        # Check if the field is present either with its name, or with "id" for scenario_id
        if field == "scenario_id" and "scenario_id" not in scenario and "id" not in scenario:
            errors.append(f"Scenario '{scenario_id}' is missing required field: 'scenario_id'")
        elif field != "scenario_id" and field not in scenario:
            errors.append(f"Scenario '{scenario_id}' is missing required field: '{field}'")

    # 2. Valid severity values
    valid_severities = {"info", "low", "medium", "high", "critical"}
    if "severity" in scenario:
        sev = str(scenario["severity"]).lower()
        if sev not in valid_severities:
            errors.append(
                f"Scenario '{scenario_id}' has invalid severity '{scenario['severity']}': "
                f"must be one of {sorted(valid_severities)}"
            )

    if "expected_severity" in scenario:
        exp_sev = str(scenario["expected_severity"]).lower()
        if exp_sev not in valid_severities:
            errors.append(
                f"Scenario '{scenario_id}' has invalid expected_severity '{scenario['expected_severity']}': "
                f"must be one of {sorted(valid_severities)}"
            )

    # 3. Tags are non-empty list of strings
    if "tags" in scenario:
        tags = scenario["tags"]
        if not isinstance(tags, list):
            errors.append(f"Scenario '{scenario_id}' field 'tags' must be a list")
        elif not tags:
            errors.append(f"Scenario '{scenario_id}' field 'tags' cannot be empty")
        else:
            for tag in tags:
                if not isinstance(tag, str) or not tag.strip():
                    errors.append(
                        f"Scenario '{scenario_id}' tag {tag!r} is invalid: must be a non-empty string"
                    )

    # 4. expected_findings is non-empty list of strings
    if "expected_findings" in scenario:
        findings = scenario["expected_findings"]
        if not isinstance(findings, list):
            errors.append(f"Scenario '{scenario_id}' field 'expected_findings' must be a list")
        elif not findings:
            errors.append(f"Scenario '{scenario_id}' field 'expected_findings' cannot be empty")
        else:
            for finding in findings:
                if not isinstance(finding, str) or not finding.strip():
                    errors.append(
                        f"Scenario '{scenario_id}' expected finding {finding!r} is invalid: "
                        f"must be a non-empty string"
                    )

    # 5. expected_evidence_patterns is non-empty list/dict
    if "expected_evidence_patterns" in scenario:
        ev_patterns = scenario["expected_evidence_patterns"]
        if not isinstance(ev_patterns, (list, dict)):
            errors.append(
                f"Scenario '{scenario_id}' field 'expected_evidence_patterns' must be a list or dict"
            )
        elif not ev_patterns:
            errors.append(
                f"Scenario '{scenario_id}' field 'expected_evidence_patterns' cannot be empty"
            )

    # 6. false_positive_guardrails is non-empty list/dict
    if "false_positive_guardrails" in scenario:
        guardrails = scenario["false_positive_guardrails"]
        if not isinstance(guardrails, (list, dict)):
            errors.append(
                f"Scenario '{scenario_id}' field 'false_positive_guardrails' must be a list or dict"
            )
        elif not guardrails:
            errors.append(
                f"Scenario '{scenario_id}' field 'false_positive_guardrails' cannot be empty"
            )

    # 7. Scan for prohibited sensitive raw payload fields
    prohibited_hits = scan_prohibited_fields(scenario)
    if prohibited_hits:
        for hit in prohibited_hits:
            errors.append(
                f"Scenario '{scenario_id}' contains prohibited sensitive field: '{hit}'"
            )

    return errors


def validate_dataset_file(filepath: Path) -> bool:
    """Validate a dataset JSON file against quality rules.

    Returns True if valid, False otherwise.
    """
    print_info(f"Validating dataset file: {filepath}")

    if not filepath.exists():
        print_error(f"File not found: {filepath}")
        return False

    try:
        with filepath.open("r", encoding="utf-8") as f:
            dataset = json.load(f)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in {filepath}: {e}")
        return False

    # A dataset file can be a single scenario (dict) or a dataset (list)
    if isinstance(dataset, dict):
        dataset = [dataset]
    elif not isinstance(dataset, list):
        print_error(f"Dataset in {filepath} must be a JSON array or a JSON object")
        return False

    # Check for empty dataset
    if not dataset:
        print_error(f"Dataset in {filepath} is empty")
        return False

    all_errors = []
    seen_ids = set()
    duplicates = set()

    for index, scenario in enumerate(dataset):
        # Unique scenario_id check
        scenario_id = scenario.get("scenario_id") or scenario.get("id")
        if scenario_id:
            if scenario_id in seen_ids:
                duplicates.add(scenario_id)
            seen_ids.add(scenario_id)

        # Individual scenario checks
        scenario_errors = validate_scenario(scenario, index)
        all_errors.extend(scenario_errors)

    # Report duplicates
    if duplicates:
        for dup in sorted(duplicates):
            all_errors.append(f"Duplicate scenario ID found: '{dup}'")

    if all_errors:
        print_error(f"Dataset validation failed for {filepath} with {len(all_errors)} errors:")
        for err in all_errors:
            print(f"  - {RED}{err}{RESET}")
        return False

    print_success(f"Dataset {filepath} is 100% valid! Checked {len(dataset)} scenarios successfully.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Brevix AI fraud benchmark datasets against quality rules."
    )
    parser.add_argument(
        "filepath",
        type=Path,
        nargs="?",
        default=Path("datasets/fraud_benchmarks.json"),
        help="Path to the dataset JSON file to validate (default: datasets/fraud_benchmarks.json)",
    )
    args = parser.parse_args()

    success = validate_dataset_file(args.filepath)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
