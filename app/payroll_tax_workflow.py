from __future__ import annotations

import re
from typing import Any


_PRIORITY_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

_PRIORITY_BY_RANK = {rank: label for label, rank in _PRIORITY_RANK.items()}


def build_payroll_tax_review_workflow(
    procedural_payload: dict[str, Any] | None,
    issue_type: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic reviewer workflow for payroll tax procedural issues."""

    payload = procedural_payload if isinstance(procedural_payload, dict) else {}
    payroll_issue_type = _payroll_issue_type(payload, issue_type)
    source_references = _source_references(payload)
    recommended_records = _recommended_records(payload)
    tax_periods = _tax_periods(payload)
    key_amount = _coerce_float(payload.get("key_amount") or payload.get("amount_at_issue") or payload.get("balance_due"))
    deadline_days = _coerce_int(payload.get("deadline_days") or payload.get("days_until_deadline"))
    risk_level = _normalize_priority(str(payload.get("risk_level") or "info"))
    responsible_person_review_required = payroll_issue_type == "trust_fund_recovery_penalty"
    review_priority = _review_priority(
        payroll_issue_type=payroll_issue_type,
        risk_level=risk_level,
        key_amount=key_amount,
        deadline_days=deadline_days,
    )
    evidence_requests = _evidence_requests(responsible_person_review_required)
    evidence_gaps = [item for item in evidence_requests if item.get("status") in {"missing", "incomplete"}]

    return {
        "status": "ok" if payroll_issue_type else "no_findings",
        "workflow_type": "payroll_tax_review",
        "issue_type": payroll_issue_type or "unknown",
        "review_priority": review_priority,
        "responsible_person_review_required": responsible_person_review_required,
        "source_references": source_references,
        "recommended_records": recommended_records,
        "tax_periods": tax_periods,
        "key_amount": key_amount,
        "deadline_days": deadline_days,
        "evidence_requests": evidence_requests,
        "evidence_gaps": evidence_gaps,
        "next_steps": _next_steps(payroll_issue_type, responsible_person_review_required, source_references),
        "escalation_criteria": _escalation_criteria(
            payroll_issue_type=payroll_issue_type,
            review_priority=review_priority,
            key_amount=key_amount,
            deadline_days=deadline_days,
            source_references=source_references,
            responsible_person_review_required=responsible_person_review_required,
        ),
        "recommended_action": {
            "type": "review_payroll_tax_evidence",
            "label": _recommended_action_label(review_priority, payroll_issue_type),
            "requires_approval": False,
            "payload": {
                "workflow_type": "payroll_tax_review",
                "issue_type": payroll_issue_type or "unknown",
                "review_priority": review_priority,
                "responsible_person_review_required": responsible_person_review_required,
                "source_reference_count": len(source_references),
                "recommended_record_count": len(recommended_records),
                "tax_period_count": len(tax_periods),
            },
        },
        "readiness_summary": {
            "review_scope": "payroll_tax",
            "issue_type": payroll_issue_type or "unknown",
            "review_priority": review_priority,
            "responsible_person_review_required": responsible_person_review_required,
            "source_reference_count": len(source_references),
            "recommended_record_count": len(recommended_records),
            "tax_period_count": len(tax_periods),
            "missing_evidence_count": len(evidence_gaps),
        },
        "scope_limitations": [
            "Workflow is based on IRS procedural payloads and retrieved IRM sections only.",
            "No payroll ledger, EFTPS account, IRS account transcript, tax return file, or responsible-person interview was reviewed.",
        ],
    }


def is_payroll_tax_issue(payload: dict[str, Any] | None, issue_type: str | None = None) -> bool:
    return _payroll_issue_type(payload if isinstance(payload, dict) else {}, issue_type) is not None


def _payroll_issue_type(payload: dict[str, Any], issue_type: str | None) -> str | None:
    text = _normalize(
        " ".join(
            [
                str(issue_type or ""),
                str(payload.get("issue_type") or ""),
                str(payload.get("notice_type") or ""),
                str(payload.get("issue_family") or ""),
                str(payload.get("summary") or ""),
                str(payload.get("required_action") or ""),
                _stringify(payload.get("recommended_records")),
                _stringify(payload.get("records")),
                _stringify(_extract_records(payload)),
            ]
        )
    )
    if not text:
        return None
    if any(term in text for term in ("trust fund recovery penalty", "tfrp", "responsible person")):
        return "trust_fund_recovery_penalty"
    if any(
        term in text
        for term in (
            "payroll tax",
            "employment tax",
            "payroll_tax",
            "form 941",
            "941",
            "eftps",
            "federal tax deposit",
            "tax deposit",
            "payroll deposit",
        )
    ):
        return "payroll_tax"
    return None


def _review_priority(
    payroll_issue_type: str | None,
    risk_level: str,
    key_amount: float | None,
    deadline_days: int | None,
) -> str:
    return _max_priority(
        _issue_priority(payroll_issue_type),
        risk_level,
        _amount_priority(key_amount),
        _deadline_urgency(deadline_days),
    )


def _issue_priority(payroll_issue_type: str | None) -> str:
    if payroll_issue_type == "trust_fund_recovery_penalty":
        return "high"
    if payroll_issue_type == "payroll_tax":
        return "medium"
    return "info"


def _evidence_requests(responsible_person_review_required: bool) -> list[dict[str, Any]]:
    common = [
        {
            "requirement_key": "irs_payroll_tax_notice",
            "label": "IRS payroll tax notice or correspondence",
            "reason": "The original notice or letter is needed to verify the issue, tax periods, response window, and IRS contact context.",
            "priority": "required",
            "status": "incomplete",
        },
        {
            "requirement_key": "forms_941_and_940",
            "label": "Filed payroll tax returns for the affected periods",
            "reason": "Forms 941, 940, and related schedules establish reported wages, withholding, and employer tax amounts.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "eftps_deposit_history",
            "label": "EFTPS deposit confirmations and deposit schedule",
            "reason": "Deposit records are needed to reconcile federal tax deposits against reported liabilities and IRS transcript activity.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "payroll_registers",
            "label": "Payroll registers and withholding reports",
            "reason": "Payroll registers support the wage, withholding, and employer-tax amounts reported for each period.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "irs_account_transcripts",
            "label": "IRS account transcripts for payroll tax periods",
            "reason": "Transcripts help reconcile filings, deposits, assessments, penalties, credits, and IRS adjustments.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "penalty_and_payment_history",
            "label": "Penalty, payment, refund, and adjustment history",
            "reason": "Payment and penalty history is needed to separate unpaid tax, late deposits, abatements, reversals, and credits.",
            "priority": "recommended",
            "status": "missing",
        },
    ]

    if not responsible_person_review_required:
        return common

    return common + [
        {
            "requirement_key": "responsible_person_authority_records",
            "label": "Responsible-person authority and control records",
            "reason": "Officer duties, check-signing authority, payroll control, bank access, and ownership records are needed for TFRP review.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "payroll_decision_timeline",
            "label": "Payroll tax decision and cash-control timeline",
            "reason": "A timeline helps reviewers understand who controlled payroll tax decisions, payments, and cash allocation during the periods at issue.",
            "priority": "required",
            "status": "missing",
        },
    ]


def _next_steps(
    payroll_issue_type: str | None,
    responsible_person_review_required: bool,
    source_references: list[str],
) -> list[str]:
    if not payroll_issue_type:
        return ["No payroll tax procedural issue was available for workflow review."]

    steps = [
        "Confirm the payroll tax issue type, tax periods, balances, and response window against the original IRS notice or transcript.",
        "Reconcile Forms 941 or related payroll tax returns to payroll registers and EFTPS deposit confirmations.",
        "Compare IRS account transcript activity against reported liabilities, deposits, payments, penalties, credits, and adjustments.",
        "Identify missing deposits, late deposits, misapplied payments, refunds, or credits before reviewer conclusions are drafted.",
    ]
    if responsible_person_review_required:
        steps.append("Gather responsible-person authority records and build a period-specific timeline of payroll tax control.")
    if source_references:
        steps.append("Use the retrieved IRM references to frame procedural questions for the reviewer.")
    else:
        steps.append("Treat the procedural summary as incomplete until source-backed IRM sections are retrieved.")
    return steps


def _escalation_criteria(
    payroll_issue_type: str | None,
    review_priority: str,
    key_amount: float | None,
    deadline_days: int | None,
    source_references: list[str],
    responsible_person_review_required: bool,
) -> list[str]:
    if not payroll_issue_type:
        return []

    criteria: list[str] = []
    if review_priority in {"high", "critical"}:
        criteria.append(f"Payroll tax review priority is {review_priority}.")
    if responsible_person_review_required:
        criteria.append("Issue appears tied to trust fund recovery penalty or responsible-person exposure.")
    if deadline_days is not None and deadline_days <= 14:
        criteria.append(f"Response deadline is within {deadline_days} days.")
    if key_amount is not None and key_amount >= 25_000:
        criteria.append(f"Amount at issue is ${key_amount:,.2f} or more.")
    if not source_references:
        criteria.append("No source-backed IRM section was returned for procedural support.")
    return criteria


def _recommended_action_label(review_priority: str, payroll_issue_type: str | None) -> str:
    label = "Review payroll tax evidence"
    if payroll_issue_type == "trust_fund_recovery_penalty":
        label = "Review trust fund payroll tax evidence"
    if review_priority in {"high", "critical"}:
        return f"Urgent {label[0].lower()}{label[1:]}"
    return label


def _source_references(payload: dict[str, Any]) -> list[str]:
    return _unique_preserving_order(
        reference
        for record in _extract_records(payload)
        if (reference := _record_reference(record))
    )


def _extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("results", "sections", "matches", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    for key in ("result", "section", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return []


def _record_reference(record: dict[str, Any]) -> str | None:
    for key in ("irm_reference", "reference", "section_reference", "section", "section_number", "source_reference"):
        value = record.get(key)
        if value:
            return str(value).strip()
    return None


def _recommended_records(payload: dict[str, Any]) -> list[str]:
    value = payload.get("recommended_records")
    if not isinstance(value, list):
        value = payload.get("records")
    if not isinstance(value, list):
        return []
    return _unique_preserving_order(_clean_text(str(item), max_length=120) for item in value if str(item).strip())


def _tax_periods(payload: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in ("tax_period", "tax_periods", "period", "periods"):
        value = payload.get(key)
        if isinstance(value, list):
            values.extend(value)
        elif value:
            values.append(value)
    return _unique_preserving_order(_clean_text(str(value), max_length=80) for value in values if str(value).strip())


def _amount_priority(amount: float | None) -> str:
    if amount is None:
        return "info"
    if amount >= 100_000:
        return "critical"
    if amount >= 25_000:
        return "high"
    if amount >= 5_000:
        return "medium"
    if amount > 0:
        return "low"
    return "info"


def _deadline_urgency(deadline_days: int | None) -> str:
    if deadline_days is None:
        return "info"
    if deadline_days <= 7:
        return "critical"
    if deadline_days <= 14:
        return "high"
    if deadline_days <= 30:
        return "medium"
    return "low"


def _max_priority(*priorities: str) -> str:
    rank = max((_PRIORITY_RANK.get(_normalize_priority(priority), 0) for priority in priorities), default=0)
    return _PRIORITY_BY_RANK[rank]


def _normalize_priority(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"warning", "moderate"}:
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


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _clean_text(value: str, max_length: int) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip())
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "."


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(f"{key} {_stringify(item)}" for key, item in value.items())
    if isinstance(value, list):
        return " ".join(_stringify(item) for item in value)
    return str(value)


def _unique_preserving_order(values: Any) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
