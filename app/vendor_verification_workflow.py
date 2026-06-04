from __future__ import annotations

from typing import Any


_PRIORITY_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_PRIORITY_BY_RANK = {rank: label for label, rank in _PRIORITY_RANK.items()}


def build_vendor_verification_workflow(
    vendor_risk_payload: dict[str, Any] | None,
    entity_relationship_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic reviewer workflow from vendor risk evidence."""

    vendor_payloads = [
        vendor
        for vendor in _vendor_payloads(vendor_risk_payload)
        if _is_elevated_vendor_risk(vendor)
    ]

    vendors = _unique_preserving_order(
        _vendor_name(vendor)
        for vendor in vendor_payloads
        if _vendor_name(vendor)
    )
    vendor_ids = _unique_preserving_order(
        _vendor_id(vendor)
        for vendor in vendor_payloads
        if _vendor_id(vendor)
    )
    vendor_scores = [
        score
        for vendor in vendor_payloads
        if (score := _coerce_int(vendor.get("vendor_risk_score") or vendor.get("risk_score"))) is not None
    ]
    highest_vendor_risk_score = max(vendor_scores, default=0)
    entity_relationship_score = _entity_relationship_score(entity_relationship_payload)
    triggered_rules = _unique_preserving_order(
        rule
        for payload in [*vendor_payloads, entity_relationship_payload or {}]
        for rule in _triggered_rules(payload)
        if rule
    )
    supporting_evidence = [
        evidence
        for payload in [*vendor_payloads, entity_relationship_payload or {}]
        for evidence in _supporting_evidence(payload)
    ]
    supporting_evidence_ids = _unique_preserving_order(
        evidence_id
        for evidence in supporting_evidence
        if (evidence_id := _evidence_id(evidence))
    )
    vendor_count = len(vendors) or len(vendor_payloads)
    evidence_requests = _evidence_requests()
    evidence_gaps = [item for item in evidence_requests if item.get("status") in {"missing", "incomplete"}]
    review_priority = _review_priority(
        vendor_payloads=vendor_payloads,
        highest_vendor_risk_score=highest_vendor_risk_score,
        vendor_count=vendor_count,
        entity_relationship_score=entity_relationship_score,
    )

    return {
        "status": "ok" if vendor_payloads else "no_findings",
        "workflow_type": "vendor_verification",
        "review_priority": review_priority,
        "vendor_count": vendor_count,
        "vendors": vendors,
        "vendor_ids": vendor_ids,
        "highest_vendor_risk_score": highest_vendor_risk_score,
        "entity_relationship_risk_score": entity_relationship_score,
        "triggered_rules": triggered_rules,
        "supporting_evidence_count": len(supporting_evidence),
        "supporting_evidence_ids": supporting_evidence_ids,
        "evidence_requests": evidence_requests,
        "evidence_gaps": evidence_gaps,
        "next_steps": _next_steps(vendor_count, entity_relationship_score),
        "escalation_criteria": _escalation_criteria(
            review_priority=review_priority,
            highest_vendor_risk_score=highest_vendor_risk_score,
            entity_relationship_score=entity_relationship_score,
            vendor_count=vendor_count,
            triggered_rules=triggered_rules,
        ),
        "recommended_action": {
            "type": "review_vendor_verification_evidence",
            "label": _recommended_action_label(review_priority, vendor_count),
            "requires_approval": False,
            "payload": {
                "workflow_type": "vendor_verification",
                "review_priority": review_priority,
                "vendor_count": vendor_count,
                "vendor_ids": vendor_ids,
                "highest_vendor_risk_score": highest_vendor_risk_score,
                "entity_relationship_risk_score": entity_relationship_score,
                "supporting_evidence_count": len(supporting_evidence),
            },
        },
        "readiness_summary": {
            "review_scope": "vendor_verification",
            "review_priority": review_priority,
            "vendor_count": vendor_count,
            "vendor_id_count": len(vendor_ids),
            "highest_vendor_risk_score": highest_vendor_risk_score,
            "entity_relationship_risk_score": entity_relationship_score,
            "triggered_rule_count": len(triggered_rules),
            "supporting_evidence_count": len(supporting_evidence),
            "missing_evidence_count": len(evidence_gaps),
        },
        "scope_limitations": [
            "Workflow is based on deterministic vendor-risk and entity-relationship evidence only.",
            "No vendor master record, tax document, bank document, ownership document, vendor outreach, or payment change was reviewed.",
        ],
    }


def _vendor_payloads(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    vendors = payload.get("vendors")
    if isinstance(vendors, list):
        return [vendor for vendor in vendors if isinstance(vendor, dict)]
    if payload.get("vendor_name") or payload.get("vendor_id") or payload.get("vendor_risk_score") is not None:
        return [payload]
    return []


def _is_elevated_vendor_risk(payload: dict[str, Any]) -> bool:
    score = _coerce_int(payload.get("vendor_risk_score") or payload.get("risk_score"))
    if score is not None and score >= 40:
        return True
    return _normalize_priority(str(payload.get("risk_level") or "info")) in {"medium", "high", "critical"}


def _review_priority(
    vendor_payloads: list[dict[str, Any]],
    highest_vendor_risk_score: int,
    vendor_count: int,
    entity_relationship_score: int | None,
) -> str:
    return _max_priority(
        _score_priority(highest_vendor_risk_score),
        _score_priority(entity_relationship_score or 0),
        _count_priority(vendor_count),
        *(_normalize_priority(str(vendor.get("risk_level") or "info")) for vendor in vendor_payloads),
    )


def _evidence_requests() -> list[dict[str, Any]]:
    return [
        {
            "requirement_key": "vendor_master_record",
            "label": "Vendor master record and change history",
            "reason": "Master data and change history are needed to verify vendor identity, onboarding path, and payment instructions.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "tax_documentation",
            "label": "Tax documentation and TIN validation",
            "reason": "W-9 or equivalent tax records help confirm the vendor's legal identity and tax identifier.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "bank_payment_validation",
            "label": "Bank and payment instruction validation",
            "reason": "Bank account ownership, payment-routing records, and change approvals are needed before clearing payment-risk concerns.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "ownership_relationship_review",
            "label": "Ownership, employee, and related-party review",
            "reason": "Relationship evidence is needed to resolve employee-vendor overlap, shared ownership, or related-party indicators.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "invoice_payment_support",
            "label": "Recent invoice and payment support",
            "reason": "Invoice support and payment history help determine whether risk signals connect to actual disbursements.",
            "priority": "recommended",
            "status": "missing",
        },
    ]


def _next_steps(vendor_count: int, entity_relationship_score: int | None) -> list[str]:
    if vendor_count == 0:
        return ["No elevated vendor-risk payload was available for workflow review."]

    steps = [
        "Compare vendor master data, tax documentation, and payment instructions against the triggered vendor-risk evidence.",
        "Confirm onboarding approvals, recent vendor changes, and payment-routing changes before any vendor or payment action is taken.",
        "Review recent invoice and payment support for the flagged vendor population.",
    ]
    if entity_relationship_score is not None and entity_relationship_score >= 40:
        steps.append("Cross-check entity-relationship evidence for employee overlap, shared account indicators, or related-party ownership.")
    steps.append("Route unresolved high-priority vendor verification gaps to a human reviewer.")
    return steps


def _escalation_criteria(
    review_priority: str,
    highest_vendor_risk_score: int,
    entity_relationship_score: int | None,
    vendor_count: int,
    triggered_rules: list[str],
) -> list[str]:
    if vendor_count == 0:
        return []

    criteria: list[str] = []
    if review_priority in {"high", "critical"}:
        criteria.append(f"Vendor verification review priority is {review_priority}.")
    if highest_vendor_risk_score >= 70:
        criteria.append(f"Highest vendor risk score is {highest_vendor_risk_score}/100.")
    if entity_relationship_score is not None and entity_relationship_score >= 70:
        criteria.append(f"Entity relationship risk score is {entity_relationship_score}/100.")
    if vendor_count >= 3:
        criteria.append(f"Elevated vendor-risk signals span {vendor_count} vendors.")
    relationship_rules = [
        rule for rule in triggered_rules
        if any(term in rule.lower() for term in ("employee", "related", "ownership", "shared", "overlap"))
    ]
    if relationship_rules:
        criteria.append(f"Relationship-sensitive rules triggered: {', '.join(relationship_rules)}.")
    return criteria


def _recommended_action_label(review_priority: str, vendor_count: int) -> str:
    if vendor_count == 0:
        return "Review vendor verification evidence"
    if review_priority in {"high", "critical"}:
        return "Review urgent vendor verification evidence"
    return "Review vendor verification evidence"


def _entity_relationship_score(payload: dict[str, Any] | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    return _coerce_int(payload.get("entity_relationship_risk_score") or payload.get("risk_score"))


def _triggered_rules(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    rules = payload.get("triggered_rules") or payload.get("rules") or []
    if isinstance(rules, list):
        return [str(rule).strip() for rule in rules if str(rule).strip()]
    if isinstance(rules, str) and rules.strip():
        return [rules.strip()]
    return []


def _supporting_evidence(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    evidence_sources = [
        payload.get("supporting_evidence"),
        payload.get("evidence"),
        payload.get("related_entities"),
        payload.get("relationships"),
    ]
    evidence: list[dict[str, Any]] = []
    for source in evidence_sources:
        if isinstance(source, list):
            evidence.extend(item for item in source if isinstance(item, dict))
        elif isinstance(source, dict):
            evidence.append(source)
    return evidence


def _evidence_id(evidence: dict[str, Any]) -> str:
    for key in ("id", "transaction_id", "vendor_id", "employee_id", "relationship_id", "account_id"):
        value = evidence.get(key)
        if value:
            return str(value).strip()
    return ""


def _vendor_name(payload: dict[str, Any]) -> str:
    return str(payload.get("vendor_name") or payload.get("name") or "").strip()


def _vendor_id(payload: dict[str, Any]) -> str:
    return str(payload.get("vendor_id") or payload.get("id") or "").strip()


def _score_priority(score: int) -> str:
    if score >= 90:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score > 0:
        return "low"
    return "info"


def _count_priority(vendor_count: int) -> str:
    if vendor_count >= 5:
        return "critical"
    if vendor_count >= 3:
        return "high"
    if vendor_count >= 2:
        return "medium"
    if vendor_count == 1:
        return "low"
    return "info"


def _max_priority(*priorities: str) -> str:
    rank = max((_PRIORITY_RANK.get(_normalize_priority(priority), 0) for priority in priorities), default=0)
    return _PRIORITY_BY_RANK[rank]


def _normalize_priority(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"warning", "moderate"}:
        normalized = "medium"
    return normalized if normalized in _PRIORITY_RANK else "info"


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.strip().replace("%", "")
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _unique_preserving_order(values: Any) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
