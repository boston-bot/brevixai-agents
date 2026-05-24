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
        "investigative_synthesis": dict,
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
    allowed_evidence_ids = _fixture_evidence_ids(dataset_item.get("tool_fixture", {}))
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
# Investigation synthesis quality
# ---------------------------------------------------------------------------

def evaluate_correlated_finding_accuracy(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    expected = _expected_synthesis(dataset_item)
    expected_patterns = [str(p) for p in expected.get("expected_correlated_patterns", [])]
    forbidden_patterns = [str(p) for p in expected.get("forbidden_correlated_patterns", [])]
    actual_patterns = _synthesis_patterns(response)

    matched = [pattern for pattern in expected_patterns if pattern in actual_patterns]
    missing = [pattern for pattern in expected_patterns if pattern not in actual_patterns]
    forbidden_hits = [pattern for pattern in forbidden_patterns if pattern in actual_patterns]

    if not expected_patterns and not forbidden_patterns:
        passed = True
        score = 1.0
    else:
        passed = not missing and not forbidden_hits
        expected_score = len(matched) / len(expected_patterns) if expected_patterns else 1.0
        penalty = len(forbidden_hits) / len(forbidden_patterns) if forbidden_patterns else 0.0
        score = max(0.0, expected_score - penalty)

    return EvaluationCheck(
        name="correlated_finding_accuracy",
        passed=passed,
        details=f"matched={matched}, missing={missing}, forbidden_hits={forbidden_hits}, actual={actual_patterns}",
        score=score,
    )


def evaluate_unsupported_correlation_detection(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    expected = _expected_synthesis(dataset_item)
    guardrails = [
        str(pattern)
        for pattern in (
            expected.get("unsupported_correlation_patterns", [])
            or dataset_item.get("unsupported_correlation_guardrails", [])
        )
    ]
    actual_patterns = _synthesis_patterns(response)
    triggered = [pattern for pattern in guardrails if pattern in actual_patterns]

    requires_suppression_note = bool(expected.get("expect_suppression_conflict"))
    conflict_types = _synthesis_conflict_types(response)
    has_suppression_note = "unsupported_correlation_suppressed" in conflict_types

    passed = not triggered and (not requires_suppression_note or has_suppression_note)
    score = 1.0 if passed else 0.0

    return EvaluationCheck(
        name="unsupported_correlation_detection",
        passed=passed,
        details=(
            f"guardrails={guardrails}, triggered={triggered}, "
            f"has_suppression_note={has_suppression_note}"
        ),
        score=score,
    )


def evaluate_synthesis_evidence_linkage(response: dict[str, Any], _dataset_item: dict[str, Any]) -> EvaluationCheck:
    synthesis = _synthesis(response)
    correlated = [item for item in synthesis.get("correlated_findings", []) if isinstance(item, dict)]
    if not correlated:
        return EvaluationCheck(
            name="synthesis_evidence_linkage",
            passed=True,
            details="no_correlated_findings",
            score=1.0,
        )

    complete = 0
    failures: list[str] = []
    for finding in correlated:
        pattern = str(finding.get("pattern", "unknown"))
        domains = {str(domain) for domain in finding.get("domains", [])}
        evidence = [item for item in finding.get("evidence", []) if isinstance(item, dict)]
        evidence_domains = {str(item.get("domain")) for item in evidence if item.get("domain")}
        if evidence and domains.issubset(evidence_domains):
            complete += 1
        else:
            failures.append(pattern)

    has_summary = bool(synthesis.get("evidence_summary"))
    passed = complete == len(correlated) and has_summary
    score = complete / len(correlated)
    if not has_summary:
        score = min(score, 0.5)

    return EvaluationCheck(
        name="synthesis_evidence_linkage",
        passed=passed,
        details=f"complete={complete}/{len(correlated)}, missing_or_incomplete={failures}, has_summary={has_summary}",
        score=score,
    )


def evaluate_conflicting_signal_handling(response: dict[str, Any], dataset_item: dict[str, Any]) -> EvaluationCheck:
    expected = _expected_synthesis(dataset_item)
    expected_conflicts = [str(item) for item in expected.get("expected_conflicting_signal_types", [])]
    if not expected_conflicts:
        return EvaluationCheck(
            name="conflicting_signal_handling",
            passed=True,
            details="no_expected_conflicts",
            score=1.0,
        )

    actual_conflicts = _synthesis_conflict_types(response)
    matched = [item for item in expected_conflicts if item in actual_conflicts]
    missing = [item for item in expected_conflicts if item not in actual_conflicts]
    passed = not missing

    return EvaluationCheck(
        name="conflicting_signal_handling",
        passed=passed,
        details=f"matched={matched}, missing={missing}, actual={actual_conflicts}",
        score=len(matched) / len(expected_conflicts),
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
        evaluate_correlated_finding_accuracy(response, dataset_item),
        evaluate_unsupported_correlation_detection(response, dataset_item),
        evaluate_synthesis_evidence_linkage(response, dataset_item),
        evaluate_conflicting_signal_handling(response, dataset_item),
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


def _synthesis(response: dict[str, Any]) -> dict[str, Any]:
    synthesis = response.get("investigative_synthesis")
    return synthesis if isinstance(synthesis, dict) else {}


def _synthesis_patterns(response: dict[str, Any]) -> list[str]:
    synthesis = _synthesis(response)
    return [
        str(item.get("pattern"))
        for item in synthesis.get("correlated_findings", [])
        if isinstance(item, dict) and item.get("pattern")
    ]


def _synthesis_conflict_types(response: dict[str, Any]) -> list[str]:
    synthesis = _synthesis(response)
    return [
        str(item.get("type"))
        for item in synthesis.get("conflicting_signals", [])
        if isinstance(item, dict) and item.get("type")
    ]


def _expected_synthesis(dataset_item: dict[str, Any]) -> dict[str, Any]:
    expected = dataset_item.get("expected_synthesis", {})
    return expected if isinstance(expected, dict) else {}


def _fixture_evidence_ids(value: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, dict):
        if value.get("id"):
            ids.add(str(value["id"]))
        for nested in value.values():
            ids.update(_fixture_evidence_ids(nested))
    elif isinstance(value, list):
        for item in value:
            ids.update(_fixture_evidence_ids(item))
    return ids
