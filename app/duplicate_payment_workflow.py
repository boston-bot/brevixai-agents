from __future__ import annotations

from collections import Counter
from typing import Any


_PRIORITY_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_PRIORITY_BY_RANK = {rank: label for label, rank in _PRIORITY_RANK.items()}


def build_duplicate_payment_review_workflow(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a deterministic reviewer workflow from duplicate payment findings."""

    duplicate_findings = [_normalize_finding(finding) for finding in findings if _is_duplicate_payment_finding(finding)]
    duplicate_findings = [finding for finding in duplicate_findings if finding]

    vendors = _unique_preserving_order(
        vendor
        for finding in duplicate_findings
        for vendor in _finding_vendors(finding)
        if vendor
    )
    transaction_ids = _unique_preserving_order(
        txn_id
        for finding in duplicate_findings
        for txn_id in _finding_transaction_ids(finding)
        if txn_id
    )
    duplicate_count = len(duplicate_findings)
    total_amount_exposure = round(sum(_finding_amount_exposure(finding) for finding in duplicate_findings), 2)
    highest_confidence = max((_coerce_float(finding.get("confidence")) or 0.0 for finding in duplicate_findings), default=0.0)
    highest_severity = _max_priority(*(_normalize_priority(str(finding.get("severity") or "info")) for finding in duplicate_findings))
    review_priority = _max_priority(
        highest_severity,
        _confidence_priority(highest_confidence),
        _amount_priority(total_amount_exposure),
        _count_priority(duplicate_count),
    )
    escalation_criteria = _escalation_criteria(
        duplicate_findings=duplicate_findings,
        highest_confidence=highest_confidence,
        total_amount_exposure=total_amount_exposure,
        vendors=vendors,
    )
    evidence_requests = _evidence_requests()
    evidence_gaps = [item for item in evidence_requests if item.get("status") in {"missing", "incomplete"}]

    return {
        "status": "ok" if duplicate_count else "no_findings",
        "workflow_type": "duplicate_payment_review",
        "review_priority": review_priority,
        "duplicate_count": duplicate_count,
        "vendors": vendors,
        "transaction_ids": transaction_ids,
        "total_amount_exposure": total_amount_exposure,
        "highest_confidence": highest_confidence,
        "evidence_requests": evidence_requests,
        "evidence_gaps": evidence_gaps,
        "next_steps": _next_steps(duplicate_count),
        "escalation_criteria": escalation_criteria,
        "recommended_action": {
            "type": "review_duplicate_payment_evidence",
            "label": _recommended_action_label(review_priority, duplicate_count),
            "requires_approval": False,
            "payload": {
                "workflow_type": "duplicate_payment_review",
                "review_priority": review_priority,
                "duplicate_count": duplicate_count,
                "transaction_ids": transaction_ids,
                "vendor_count": len(vendors),
                "total_amount_exposure": total_amount_exposure,
            },
        },
        "readiness_summary": {
            "review_scope": "duplicate_payment",
            "review_priority": review_priority,
            "duplicate_count": duplicate_count,
            "transaction_count": len(transaction_ids),
            "vendor_count": len(vendors),
            "missing_evidence_count": len(evidence_gaps),
            "total_amount_exposure": total_amount_exposure,
        },
        "scope_limitations": [
            "Workflow is based on deterministic duplicate-payment findings and their evidence only.",
            "No transaction detail lookup, invoice file, vendor statement, refund record, or bank clearing record was reviewed.",
        ],
    }


def _is_duplicate_payment_finding(finding: dict[str, Any]) -> bool:
    title = str(finding.get("title") or "").strip().lower()
    evidence = finding.get("evidence")
    has_transaction_evidence = isinstance(evidence, list) and any(
        isinstance(item, dict) and item.get("transaction_id") for item in evidence
    )
    return title == "duplicate payment" and has_transaction_evidence


def _normalize_finding(finding: dict[str, Any]) -> dict[str, Any]:
    return finding if isinstance(finding, dict) else {}


def _evidence_requests() -> list[dict[str, Any]]:
    return [
        {
            "requirement_key": "invoice_documentation",
            "label": "Invoice documentation for each flagged transaction",
            "reason": "Invoices are needed to confirm whether the flagged payments correspond to the same obligation.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "payment_status",
            "label": "Payment status and clearing records",
            "reason": "Payment status confirms whether both transactions cleared, failed, reversed, or remain pending.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "void_or_refund_activity",
            "label": "Void, reversal, refund, or credit activity",
            "reason": "Offsetting activity can explain a duplicate-looking payment without requiring remediation.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "vendor_confirmation",
            "label": "Vendor confirmation or statement",
            "reason": "Vendor confirmation helps verify whether both payments were received and applied.",
            "priority": "recommended",
            "status": "missing",
        },
    ]


def _next_steps(duplicate_count: int) -> list[str]:
    if duplicate_count == 0:
        return ["No duplicate payment findings were available for workflow review."]
    return [
        "Compare invoice documentation for each flagged transaction pair.",
        "Confirm payment status, clearing date, and whether either payment was voided, reversed, refunded, or credited.",
        "Check vendor statement or confirmation before concluding that an overpayment occurred.",
        "Route unresolved high-priority duplicate pairs to a human reviewer for remediation decisions.",
    ]


def _escalation_criteria(
    duplicate_findings: list[dict[str, Any]],
    highest_confidence: float,
    total_amount_exposure: float,
    vendors: list[str],
) -> list[str]:
    if not duplicate_findings:
        return []

    criteria: list[str] = []
    if highest_confidence >= 0.80:
        criteria.append(f"Highest duplicate-payment confidence is {highest_confidence:.2f}.")
    if _has_same_invoice_or_memo(duplicate_findings):
        criteria.append("At least one flagged pair shares the same invoice number or memo.")
    if total_amount_exposure >= 10_000:
        criteria.append(f"Potential duplicate amount exposure is ${total_amount_exposure:,.2f} or more.")
    repeated_vendors = _repeated_vendors(duplicate_findings)
    if repeated_vendors:
        criteria.append(f"Repeated duplicate-payment findings involve: {', '.join(repeated_vendors)}.")
    if len(vendors) > 1:
        criteria.append("Duplicate-payment findings span multiple vendors.")
    return criteria


def _finding_vendors(finding: dict[str, Any]) -> list[str]:
    vendors: list[str] = []
    for item in finding.get("evidence", []):
        if isinstance(item, dict) and item.get("vendor"):
            vendors.append(str(item["vendor"]).strip())
    return _unique_preserving_order(vendors)


def _finding_transaction_ids(finding: dict[str, Any]) -> list[str]:
    transaction_ids: list[str] = []
    for item in finding.get("evidence", []):
        if isinstance(item, dict) and item.get("transaction_id"):
            transaction_ids.append(str(item["transaction_id"]).strip())
    return _unique_preserving_order(transaction_ids)


def _finding_amount_exposure(finding: dict[str, Any]) -> float:
    amounts = [
        amount
        for item in finding.get("evidence", [])
        if isinstance(item, dict) and (amount := _coerce_float(item.get("amount"))) is not None and amount > 0
    ]
    return min(amounts) if amounts else 0.0


def _has_same_invoice_or_memo(findings: list[dict[str, Any]]) -> bool:
    for finding in findings:
        invoices = _non_empty_values(finding, "invoice_number")
        memos = _non_empty_values(finding, "memo")
        if len(invoices) != len(set(invoices)) or len(memos) != len(set(memos)):
            return True
    return False


def _non_empty_values(finding: dict[str, Any], key: str) -> list[str]:
    values: list[str] = []
    for item in finding.get("evidence", []):
        if isinstance(item, dict) and item.get(key):
            values.append(str(item[key]).strip().lower())
    return [value for value in values if value]


def _repeated_vendors(findings: list[dict[str, Any]]) -> list[str]:
    vendor_counter = Counter(
        vendor
        for finding in findings
        for vendor in _finding_vendors(finding)
    )
    return [vendor for vendor, count in vendor_counter.items() if count > 1]


def _recommended_action_label(review_priority: str, duplicate_count: int) -> str:
    if duplicate_count == 0:
        return "Review duplicate payment evidence"
    if review_priority in {"high", "critical"}:
        return "Review urgent duplicate payment evidence"
    return "Review duplicate payment evidence"


def _confidence_priority(confidence: float) -> str:
    if confidence >= 0.90:
        return "critical"
    if confidence >= 0.80:
        return "high"
    if confidence >= 0.65:
        return "medium"
    if confidence > 0:
        return "low"
    return "info"


def _amount_priority(amount: float) -> str:
    if amount >= 50_000:
        return "critical"
    if amount >= 10_000:
        return "high"
    if amount >= 1_000:
        return "medium"
    if amount > 0:
        return "low"
    return "info"


def _count_priority(duplicate_count: int) -> str:
    if duplicate_count >= 5:
        return "critical"
    if duplicate_count >= 3:
        return "high"
    if duplicate_count >= 2:
        return "medium"
    if duplicate_count == 1:
        return "low"
    return "info"


def _max_priority(*priorities: str) -> str:
    rank = max((_PRIORITY_RANK.get(_normalize_priority(priority), 0) for priority in priorities), default=0)
    return _PRIORITY_BY_RANK[rank]


def _normalize_priority(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "warning":
        normalized = "medium"
    return normalized if normalized in _PRIORITY_RANK else "info"


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").strip()
    try:
        return float(value)
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
