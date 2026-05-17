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


# ---------------------------------------------------------------------------
# Response contract
# ---------------------------------------------------------------------------

def evaluate_response_contract(response: dict[str, Any], _dataset_item: dict[str, Any]) -> EvaluationCheck:
    """Verify all required response fields exist and have correct types."""
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


# ---------------------------------------------------------------------------
# Finding type correctness  (also serves as missing-finding-rate proxy)
# ---------------------------------------------------------------------------

def evaluate_finding_correctness(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    """
    Check that every expected finding term appears in the response findings text.
    score = matched / expected  (1.0 - score = missing finding rate).
    """
    findings_text = _findings_text(response)
    expected_terms = [str(term).lower() for term in dataset_item.get("expected_findings", [])]
    matched = [term for term in expected_terms if term in findings_text]
    missing = [term for term in expected_terms if term not in findings_text]
    passed = len(matched) == len(expected_terms)

    return EvaluationCheck(
        name="finding_correctness",
        passed=passed,
        details=f"matched={matched}, missing={missing}, expected={expected_terms}",
        score=len(matched) / len(expected_terms) if expected_terms else 1.0,
    )


# ---------------------------------------------------------------------------
# Severity correctness
# ---------------------------------------------------------------------------

def evaluate_severity_correctness(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    """Check that the expected severity level appears in at least one finding."""
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


# ---------------------------------------------------------------------------
# Evidence completeness  (scored fraction of expected patterns satisfied)
# ---------------------------------------------------------------------------

def evaluate_evidence_completeness(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    """
    Score what fraction of expected_evidence_patterns are satisfied.
    Each pattern may specify a minimum type count and/or an id_contains substring.
    score = satisfied_patterns / total_patterns.
    """
    patterns = [p for p in dataset_item.get("expected_evidence_patterns", []) if isinstance(p, dict)]
    if not patterns:
        return EvaluationCheck(
            name="evidence_completeness",
            passed=True,
            details="no_patterns_defined",
            score=1.0,
        )

    evidence = _flat_evidence(response)
    satisfied = 0
    unsatisfied: list[dict[str, Any]] = []

    for pattern in patterns:
        ok = True
        if "type" in pattern:
            minimum = int(pattern.get("min_count", 1))
            count = sum(1 for item in evidence if item.get("type") == pattern["type"])
            if count < minimum:
                ok = False
        if ok and "id_contains" in pattern:
            needle = str(pattern["id_contains"])
            if not any(needle in str(item.get("id", "")) for item in evidence):
                ok = False
        if ok:
            satisfied += 1
        else:
            unsatisfied.append(pattern)

    score = satisfied / len(patterns)
    passed = score == 1.0

    return EvaluationCheck(
        name="evidence_completeness",
        passed=passed,
        details=f"satisfied={satisfied}/{len(patterns)}, unsatisfied={unsatisfied}",
        score=score,
    )


# ---------------------------------------------------------------------------
# Hallucination detection  (invented evidence IDs + prohibited message claims)
# ---------------------------------------------------------------------------

def evaluate_hallucination_detection(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    """
    Check two things:
      1. No evidence IDs in the response that were not in the tool fixture.
      2. No prohibited accusatory claims in the final message.
    Evidence completeness is a separate concern handled by evaluate_evidence_completeness.
    """
    allowed_evidence_ids = {
        str(item.get("id"))
        for driver in dataset_item.get("tool_fixture", {}).get("top_drivers", [])
        for item in driver.get("evidence", [])
        if isinstance(item, dict) and item.get("id")
    }
    actual_evidence_ids = {
        str(item.get("id"))
        for item in _flat_evidence(response)
        if item.get("id")
    }
    invented_ids = sorted(actual_evidence_ids - allowed_evidence_ids)

    message = str(response.get("message", "")).lower()
    prohibited_claims = [
        "committed fraud",
        "is fraud",
        "stole",
        "theft confirmed",
        "definitely fraud",
        "proven fraud",
    ]
    prohibited_hits = [claim for claim in prohibited_claims if claim in message]
    passed = not invented_ids and not prohibited_hits

    return EvaluationCheck(
        name="hallucination_detection",
        passed=passed,
        details=f"invented_evidence_ids={invented_ids}, prohibited_claims={prohibited_hits}",
        score=1.0 if passed else 0.0,
    )


# ---------------------------------------------------------------------------
# False positive rate  (guardrail terms from other scenarios must not appear)
# ---------------------------------------------------------------------------

def evaluate_false_positive_rate(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    """
    Check that false_positive_guardrails terms — phrases characteristic of
    other fraud scenarios — do not appear in the response findings text.
    A triggered guardrail means the system surfaced a pattern not present
    in the fixture, which is a false positive.
    score = 1 - (triggered / total_guardrails).
    """
    guardrails = [str(g).lower() for g in dataset_item.get("false_positive_guardrails", [])]
    if not guardrails:
        return EvaluationCheck(
            name="false_positive_rate",
            passed=True,
            details="no_guardrails_defined",
            score=1.0,
        )

    findings_text = _findings_text(response)
    triggered = [g for g in guardrails if g in findings_text]
    passed = not triggered
    score = 1.0 - (len(triggered) / len(guardrails))

    return EvaluationCheck(
        name="false_positive_rate",
        passed=passed,
        details=f"triggered_guardrails={triggered}, clean={len(guardrails) - len(triggered)}/{len(guardrails)}",
        score=score,
    )


# ---------------------------------------------------------------------------
# Composite runner
# ---------------------------------------------------------------------------

def run_deterministic_evaluators(response: dict[str, Any], dataset_item: dict[str, Any]) -> list[EvaluationCheck]:
    return [
        evaluate_response_contract(response, dataset_item),
        evaluate_finding_correctness(response, dataset_item),
        evaluate_severity_correctness(response, dataset_item),
        evaluate_evidence_completeness(response, dataset_item),
        evaluate_hallucination_detection(response, dataset_item),
        evaluate_false_positive_rate(response, dataset_item),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _findings_text(response: dict[str, Any]) -> str:
    return " ".join(
        " ".join(str(finding.get(field, "")) for field in ("title", "summary", "description"))
        for finding in response.get("findings", [])
        if isinstance(finding, dict)
    ).lower()


def _flat_evidence(response: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for finding in response.get("findings", [])
        if isinstance(finding, dict)
        for item in finding.get("evidence", [])
        if isinstance(item, dict)
    ]
