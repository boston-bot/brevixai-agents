from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationCheck:
    name: str
    passed: bool
    details: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_response_contract(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    required_types: dict[str, type | tuple[type, ...]] = {
        "message": str,
        "findings": list,
        "recommended_actions": list,
        "steps": list,
        "errors": list,
        "usage": dict,
    }
    optional_types: dict[str, type | tuple[type, ...]] = {
        "trace_id": (str, type(None)),
        "intent": (str, type(None)),
    }
    missing = [key for key in required_types if key not in response]
    wrong_types = [
        key
        for key, expected_type in {**required_types, **optional_types}.items()
        if key in response and not isinstance(response[key], expected_type)
    ]
    passed = not missing and not wrong_types

    return EvaluationCheck(
        name="response_contract_validation",
        passed=passed,
        details=f"missing={missing}, wrong_types={wrong_types}",
        score=1.0 if passed else 0.0,
    )


def evaluate_finding_correctness(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    findings_text = " ".join(
        " ".join(
            str(finding.get(field, ""))
            for field in ("title", "summary", "description")
        )
        for finding in response.get("findings", [])
        if isinstance(finding, dict)
    ).lower()
    expected_terms = [str(term).lower() for term in dataset_item.get("expected_findings", [])]
    matched = [term for term in expected_terms if term in findings_text]
    passed = len(matched) == len(expected_terms)

    return EvaluationCheck(
        name="finding_correctness",
        passed=passed,
        details=f"matched={matched}, expected={expected_terms}",
        score=len(matched) / len(expected_terms) if expected_terms else 1.0,
    )


def evaluate_severity_correctness(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    expected = str(dataset_item.get("expected_severity", "")).lower()
    severities = [
        str(finding.get("severity", "")).lower()
        for finding in response.get("findings", [])
        if isinstance(finding, dict)
    ]
    passed = expected in severities

    return EvaluationCheck(
        name="severity_correctness",
        passed=passed,
        details=f"expected={expected}, actual={severities}",
        score=1.0 if passed else 0.0,
    )


def evaluate_hallucination_detection(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    allowed_evidence_ids = {
        str(item.get("id"))
        for driver in dataset_item.get("tool_fixture", {}).get("top_drivers", [])
        for item in driver.get("evidence", [])
        if isinstance(item, dict) and item.get("id")
    }
    actual_evidence_ids = {
        str(item.get("id"))
        for finding in response.get("findings", [])
        if isinstance(finding, dict)
        for item in finding.get("evidence", [])
        if isinstance(item, dict) and item.get("id")
    }
    invented_ids = sorted(actual_evidence_ids - allowed_evidence_ids)
    message = str(response.get("message", "")).lower()
    prohibited_claims = [
        "committed fraud",
        "is fraud",
        "stole",
        "theft confirmed",
    ]
    prohibited_hits = [claim for claim in prohibited_claims if claim in message]
    evidence_patterns_passed = expected_evidence_patterns_pass(response, dataset_item)
    passed = not invented_ids and not prohibited_hits and evidence_patterns_passed

    return EvaluationCheck(
        name="hallucination_detection",
        passed=passed,
        details=(
            f"invented_evidence_ids={invented_ids}, "
            f"prohibited_claims={prohibited_hits}, "
            f"evidence_patterns_passed={evidence_patterns_passed}"
        ),
        score=1.0 if passed else 0.0,
    )


def expected_evidence_patterns_pass(response: dict[str, Any], dataset_item: dict[str, Any]) -> bool:
    evidence = [
        item
        for finding in response.get("findings", [])
        if isinstance(finding, dict)
        for item in finding.get("evidence", [])
        if isinstance(item, dict)
    ]

    for pattern in dataset_item.get("expected_evidence_patterns", []):
        if not isinstance(pattern, dict):
            continue

        if "type" in pattern:
            minimum = int(pattern.get("min_count", 1))
            count = sum(1 for item in evidence if item.get("type") == pattern["type"])
            if count < minimum:
                return False

        if "id_contains" in pattern:
            needle = str(pattern["id_contains"])
            if not any(needle in str(item.get("id", "")) for item in evidence):
                return False

    return True


def run_deterministic_evaluators(response: dict[str, Any], dataset_item: dict[str, Any]) -> list[EvaluationCheck]:
    return [
        evaluate_response_contract(response, dataset_item),
        evaluate_finding_correctness(response, dataset_item),
        evaluate_severity_correctness(response, dataset_item),
        evaluate_hallucination_detection(response, dataset_item),
    ]
