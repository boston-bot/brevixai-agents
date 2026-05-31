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


def build_irs_notice_workflow(extraction_payload: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic reviewer workflow from an IRS notice extraction payload."""

    notice_type = _clean_notice_type(extraction_payload.get("notice_type"))
    risk_level = _normalize_priority(str(extraction_payload.get("risk_level") or "medium"))
    deadline_days = _coerce_int(extraction_payload.get("deadline_days"))
    key_amount = _coerce_float(extraction_payload.get("key_amount"))
    issue_family = _issue_family(extraction_payload)
    deadline_urgency = _deadline_urgency(deadline_days)
    review_priority = _max_priority(risk_level, deadline_urgency, _amount_priority(key_amount))
    source_references = _source_references(extraction_payload)

    evidence_requests = _evidence_requests(issue_family)
    next_steps = _next_steps(
        notice_type=notice_type,
        issue_family=issue_family,
        deadline_days=deadline_days,
        source_references=source_references,
    )
    escalation_criteria = _escalation_criteria(
        notice_type=notice_type,
        issue_family=issue_family,
        risk_level=risk_level,
        deadline_days=deadline_days,
        key_amount=key_amount,
        source_references=source_references,
    )

    missing_evidence = [
        item for item in evidence_requests if item.get("status") in {"missing", "incomplete"}
    ]

    return {
        "status": "ok",
        "workflow_type": "irs_notice_review",
        "notice_type": notice_type,
        "issue_family": issue_family,
        "review_priority": review_priority,
        "deadline_urgency": deadline_urgency,
        "deadline_days": deadline_days,
        "key_amount": key_amount,
        "evidence_requests": evidence_requests,
        "evidence_gaps": missing_evidence,
        "next_steps": next_steps,
        "escalation_criteria": escalation_criteria,
        "source_references": source_references,
        "recommended_action": {
            "type": "prepare_irs_notice_review",
            "label": _recommended_action_label(notice_type, review_priority),
            "requires_approval": False,
            "payload": {
                "workflow_type": "irs_notice_review",
                "notice_type": notice_type,
                "review_priority": review_priority,
                "evidence_gap_count": len(missing_evidence),
            },
        },
        "readiness_summary": {
            "review_scope": issue_family,
            "review_priority": review_priority,
            "deadline_urgency": deadline_urgency,
            "missing_evidence_count": len(missing_evidence),
            "source_reference_count": len(source_references),
        },
        "scope_limitations": [
            "Workflow is based on extracted notice text and retrieved IRM sections only.",
            "No IRS account transcript, uploaded original notice file, or taxpayer records were reviewed.",
        ],
    }


def _clean_notice_type(value: Any) -> str:
    text = str(value or "Unknown").strip().upper()
    return text or "Unknown"


def _issue_family(payload: dict[str, Any]) -> str:
    notice_type = _clean_notice_type(payload.get("notice_type"))
    text = " ".join(
        str(payload.get(key) or "")
        for key in ("summary", "required_action", "irm_search_topic", "deadline_description")
    ).lower()

    if notice_type == "CP2000" or "underreport" in text or "proposed change" in text:
        return "underreporter"
    if any(term in text for term in ("payroll", "trust fund", "941", "tfrp")):
        return "payroll_tax"
    if notice_type in {"CP504", "LT11", "LT 11", "1058"} or any(
        term in text for term in ("levy", "lien", "collection", "seizure", "balance due")
    ):
        return "collection"
    return "general_notice"


def _evidence_requests(issue_family: str) -> list[dict[str, Any]]:
    common = [
        {
            "requirement_key": "original_irs_notice",
            "label": "Original IRS notice or letter",
            "reason": "Pasted text can scope the review, but the original notice is needed to verify the code, tax period, balance, and deadline.",
            "priority": "required",
            "status": "incomplete",
        },
        {
            "requirement_key": "tax_period_records",
            "label": "Records for the notice tax period",
            "reason": "Source records are needed to tie the notice issue to the relevant period.",
            "priority": "required",
            "status": "missing",
        },
        {
            "requirement_key": "irs_account_transcript",
            "label": "IRS account transcript for the notice period",
            "reason": "Transcript history helps reconcile assessed balances, payments, penalties, and IRS correspondence.",
            "priority": "recommended",
            "status": "missing",
        },
        {
            "requirement_key": "prior_correspondence",
            "label": "Prior IRS correspondence and payment confirmations",
            "reason": "Earlier notices, installment agreements, or payment confirmations may affect the procedural posture.",
            "priority": "recommended",
            "status": "missing",
        },
    ]

    family_specific = {
        "collection": [
            {
                "requirement_key": "collection_status_records",
                "label": "Collection status records",
                "reason": "Levy, lien, installment agreement, or currently-not-collectible records help scope collection exposure.",
                "priority": "required",
                "status": "missing",
            }
        ],
        "underreporter": [
            {
                "requirement_key": "income_support",
                "label": "Income forms and return support",
                "reason": "Payer forms, return workpapers, and supporting documents are needed for underreporter comparisons.",
                "priority": "required",
                "status": "missing",
            }
        ],
        "payroll_tax": [
            {
                "requirement_key": "payroll_tax_deposits",
                "label": "Payroll tax filings and deposit history",
                "reason": "Forms 941, EFTPS confirmations, and payroll registers are needed for payroll tax notice review.",
                "priority": "required",
                "status": "missing",
            }
        ],
    }

    return common + family_specific.get(issue_family, [])


def _next_steps(
    notice_type: str,
    issue_family: str,
    deadline_days: int | None,
    source_references: list[str],
) -> list[str]:
    steps = [
        f"Confirm the extracted notice type ({notice_type}) against the original IRS notice.",
        "Verify the tax period, balance, deadline, and required action before any response is prepared.",
    ]

    if deadline_days is not None:
        if deadline_days <= 14:
            steps.append(f"Prioritize reviewer triage because the extracted deadline is within {deadline_days} days.")
        else:
            steps.append(f"Calendar the extracted response window of {deadline_days} days for reviewer tracking.")

    if issue_family == "collection":
        steps.append("Gather collection status records, payment history, and any installment agreement documentation.")
    elif issue_family == "underreporter":
        steps.append("Gather payer forms, filed return support, and workpapers for the proposed adjustment period.")
    elif issue_family == "payroll_tax":
        steps.append("Gather payroll tax returns, EFTPS confirmations, payroll registers, and deposit schedules.")
    else:
        steps.append("Gather tax period records and prior IRS correspondence before reviewer analysis.")

    if source_references:
        steps.append("Use the retrieved IRM references to frame procedural questions for the reviewer.")
    else:
        steps.append("Treat the procedural summary as incomplete until source-backed IRM sections are retrieved.")

    return steps


def _escalation_criteria(
    notice_type: str,
    issue_family: str,
    risk_level: str,
    deadline_days: int | None,
    key_amount: float | None,
    source_references: list[str],
) -> list[str]:
    criteria: list[str] = []

    if deadline_days is not None and deadline_days <= 14:
        criteria.append(f"Response deadline is within {deadline_days} days.")
    if risk_level in {"high", "critical"}:
        criteria.append(f"Extracted risk level is {risk_level}.")
    if issue_family == "collection" or notice_type in {"CP504", "LT11", "LT 11"}:
        criteria.append("Notice appears tied to collection enforcement such as levy or lien procedures.")
    if key_amount is not None and key_amount >= 10_000:
        criteria.append(f"Amount at issue is ${key_amount:,.2f} or more.")
    if not source_references:
        criteria.append("No source-backed IRM section was returned for procedural support.")

    return criteria


def _recommended_action_label(notice_type: str, review_priority: str) -> str:
    if review_priority in {"high", "critical"}:
        return f"Prepare urgent {notice_type} notice review"
    return f"Prepare {notice_type} notice review"


def _deadline_urgency(deadline_days: int | None) -> str:
    if deadline_days is None:
        return "medium"
    if deadline_days <= 7:
        return "critical"
    if deadline_days <= 14:
        return "high"
    if deadline_days <= 30:
        return "medium"
    return "low"


def _amount_priority(key_amount: float | None) -> str:
    if key_amount is None:
        return "info"
    if key_amount >= 50_000:
        return "critical"
    if key_amount >= 10_000:
        return "high"
    if key_amount >= 1_000:
        return "medium"
    return "low"


def _max_priority(*priorities: str) -> str:
    rank = max(_PRIORITY_RANK.get(_normalize_priority(priority), 0) for priority in priorities)
    return _PRIORITY_BY_RANK[rank]


def _normalize_priority(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "warning":
        normalized = "medium"
    return normalized if normalized in _PRIORITY_RANK else "medium"


def _source_references(payload: dict[str, Any]) -> list[str]:
    references: list[str] = []
    for key in ("results", "sections", "matches", "items"):
        value = payload.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            reference = _record_reference(item)
            if reference and reference not in references:
                references.append(reference)
    return references


def _record_reference(record: dict[str, Any]) -> str | None:
    for key in ("irm_reference", "reference", "section_reference", "section", "section_number", "source_reference"):
        value = record.get(key)
        if value:
            return str(value).strip()
    return None


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
