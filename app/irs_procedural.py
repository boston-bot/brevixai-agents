from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.irs_notice_workflow import build_irs_notice_workflow

IRS_INTENT = "irs_procedural_question"

IRS_DISCLAIMER = (
    "Disclaimer: This is general IRS procedural information based on retrieved IRM content. "
    "It is not tax, legal, or accounting advice, and it does not decide what you should do."
)

_NOTICE_CODE_RE = re.compile(r"\b(CP\s?\d{2,4}|LT\s?\d{1,4})\b", re.IGNORECASE)
_IRM_REFERENCE_RE = re.compile(r"\b(?:IRM\s*)?(\d{1,2}\.\d{1,2}(?:\.\d{1,3}){1,4})\b", re.IGNORECASE)

_IRS_ANCHOR_TERMS = (
    "irs",
    "irm",
    "notice",
    "cp504",
    "cp 504",
    "lt11",
    "lt 11",
    "cp2000",
    "cp 2000",
    "levy",
    "lien",
    "collection",
    "collections",
    "trust fund recovery penalty",
    "tfrp",
    "payroll tax",
)

_PROCEDURAL_TERMS = (
    "what is",
    "what does",
    "explain",
    "meaning",
    "mean",
    "process",
    "procedure",
    "timeline",
    "happens",
    "records",
    "documents",
    "documentation",
    "gather",
    "bring",
    "prepare",
    "checklist",
    "look up",
    "lookup",
    "section",
)

_RECORDS_TERMS = (
    "records",
    "documents",
    "documentation",
    "gather",
    "bring",
    "prepare",
    "checklist",
)

_ADVICE_POSITIONING_TERMS = (
    "can i avoid",
    "how do i avoid",
    "get out of",
    "pay less",
    "settle for",
    "deduct",
    "deduction",
    "claim a credit",
    "tax strategy",
    "legal advice",
)

ToolName = Literal["irm_section", "irs_notice_type", "irs_records_checklist", "irs_collection_risk", "irm_search", "irs_notice_extract"]

_NOTICE_TEXT_TRIGGERS = (
    "my notice says",
    "my notice reads",
    "the notice says",
    "the notice reads",
    "notice text",
    "i received a notice",
    "i got a notice",
    "here is my notice",
    "here's my notice",
    "i have a notice that",
    "notice states",
    "notice dated",
)


@dataclass(frozen=True)
class IrsToolRequest:
    tool_name: ToolName
    query: str
    limit: int = 5


def is_irs_procedural_question(message: str) -> bool:
    normalized = _normalize(message)
    if not normalized:
        return False

    if "should i" in normalized and not any(term in normalized for term in _RECORDS_TERMS):
        return False

    if any(term in normalized for term in _ADVICE_POSITIONING_TERMS):
        return False

    if _IRM_REFERENCE_RE.search(message) or _NOTICE_CODE_RE.search(message):
        return True

    has_irs_anchor = any(term in normalized for term in _IRS_ANCHOR_TERMS)
    has_procedural_term = any(term in normalized for term in _PROCEDURAL_TERMS)

    return has_irs_anchor and has_procedural_term


def classify_irs_tool_request(message: str) -> IrsToolRequest:
    reference_match = _IRM_REFERENCE_RE.search(message)
    if reference_match:
        return IrsToolRequest(tool_name="irm_section", query=reference_match.group(1))

    normalized = _normalize(message)

    if _is_notice_text_submission(message, normalized):
        return IrsToolRequest(tool_name="irs_notice_extract", query=message.strip())

    if any(term in normalized for term in _RECORDS_TERMS):
        return IrsToolRequest(tool_name="irs_records_checklist", query=_issue_type_from_message(message))

    notice_match = _NOTICE_CODE_RE.search(message)
    if notice_match:
        return IrsToolRequest(tool_name="irs_notice_type", query=notice_match.group(1).replace(" ", "").upper())

    if any(term in normalized for term in ("levy", "lien", "collection", "collections", "trust fund recovery penalty", "tfrp")):
        return IrsToolRequest(tool_name="irs_collection_risk", query=_issue_type_from_message(message))

    return IrsToolRequest(tool_name="irm_search", query=message.strip())


def _is_notice_text_submission(message: str, normalized: str) -> bool:
    has_irs_anchor = any(term in normalized for term in _IRS_ANCHOR_TERMS)
    if not has_irs_anchor:
        return False
    has_trigger = any(trigger in normalized for trigger in _NOTICE_TEXT_TRIGGERS)
    is_long_paste = len(message.strip()) > 300
    return has_trigger or is_long_paste


def synthesize_irs_answer(request: IrsToolRequest, payload: dict[str, Any]) -> str:
    if request.tool_name == "irs_notice_extract":
        return _synthesize_notice_extraction(payload)

    records = [record for record in _extract_records(payload) if _record_reference(record)]
    if request.tool_name == "irm_section":
        records = _filter_exact_reference(records, request.query)

    references = _unique_preserving_order(
        ref for record in records if (ref := _record_reference(record))
    )

    if not records:
        return (
            f"No source-backed IRM result was returned for {request.query!r}. "
            "I do not have enough retrieved IRM support to give procedural guidance for that request. "
            "irm_reference: none returned. "
            f"{IRS_DISCLAIMER}"
        )

    lines: list[str] = []
    lines.append(_opening_for_request(request))
    for index, record in enumerate(records[:3], start=1):
        reference = _record_reference(record) or "unknown"
        title = _record_title(record)
        summary = _record_summary(record)
        if title and summary:
            lines.append(f"{index}. {title}: {summary} irm_reference: {reference}.")
        elif summary:
            lines.append(f"{index}. {summary} irm_reference: {reference}.")
        elif title:
            lines.append(f"{index}. {title}. irm_reference: {reference}.")
        else:
            lines.append(f"{index}. Retrieved IRM result. irm_reference: {reference}.")

    checklist = _records_checklist(payload)
    if checklist:
        lines.append("Records to gather: " + "; ".join(checklist[:6]) + ".")

    references_text = ", ".join(references) if references else "none returned"
    lines.append(f"IRM references: {references_text}.")
    lines.append(IRS_DISCLAIMER)
    return " ".join(lines)


def _synthesize_notice_extraction(payload: dict[str, Any]) -> str:
    notice_type = payload.get("notice_type", "Unknown")
    risk_level = payload.get("risk_level", "")
    deadline_description = payload.get("deadline_description", "")
    required_action = payload.get("required_action", "")
    summary = _clean_text(str(payload.get("summary") or ""), max_length=420)
    key_amount = _coerce_float(payload.get("key_amount"))
    workflow = payload.get("workflow")

    lines: list[str] = []
    risk_label = f" [{risk_level}]" if risk_level else ""
    lines.append(f"IRS notice extraction — identified as {notice_type}{risk_label}.")

    if summary:
        lines.append(summary)
    if required_action:
        lines.append(f"Required action: {_clean_text(required_action, max_length=200)}")
    if deadline_description:
        lines.append(f"Deadline: {_clean_text(deadline_description, max_length=160)}")
    if key_amount is not None:
        lines.append(f"Amount at issue: ${key_amount:,.2f}")

    records = [record for record in _extract_records(payload) if _record_reference(record)]
    if records:
        lines.append("Related IRM sections:")
        for index, record in enumerate(records[:3], start=1):
            reference = _record_reference(record) or "unknown"
            title = _record_title(record)
            if title:
                lines.append(f"{index}. {title}. irm_reference: {reference}.")
            else:
                lines.append(f"{index}. irm_reference: {reference}.")
        references = _unique_preserving_order(
            ref for record in records if (ref := _record_reference(record))
        )
        lines.append(f"IRM references: {', '.join(references)}.")
    else:
        lines.append("irm_reference: none returned.")

    if isinstance(workflow, dict):
        next_steps = _workflow_text_items(workflow.get("next_steps"), max_length=180)
        evidence_to_gather = [
            _clean_text(str(item.get("label")), max_length=120)
            for item in workflow.get("evidence_requests", [])
            if isinstance(item, dict) and item.get("status") in {"missing", "incomplete"} and item.get("label")
        ]
        escalation_criteria = _workflow_text_items(workflow.get("escalation_criteria"), max_length=160)

        if next_steps:
            lines.append("Workflow next steps: " + "; ".join(next_steps[:4]) + ".")
        if evidence_to_gather:
            lines.append("Evidence to gather: " + "; ".join(evidence_to_gather[:5]) + ".")
        if escalation_criteria:
            lines.append("Escalation criteria: " + "; ".join(escalation_criteria[:4]) + ".")

    lines.append(IRS_DISCLAIMER)
    return " ".join(lines)


def synthesize_irs_notice_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    return build_irs_notice_workflow(payload)


def _opening_for_request(request: IrsToolRequest) -> str:
    if request.tool_name == "irm_section":
        return f"IRM section lookup for {request.query}:"
    if request.tool_name == "irs_notice_type":
        return f"IRS notice {request.query} procedural summary:"
    if request.tool_name == "irs_records_checklist":
        return f"Records-to-gather guidance for {request.query}:"
    if request.tool_name == "irs_collection_risk":
        return f"IRS collection process summary for {request.query}:"
    return f"IRM search summary for {request.query}:"


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

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

    if _record_reference(payload) or _record_summary(payload):
        return [payload]

    return []


def _filter_exact_reference(records: list[dict[str, Any]], requested_reference: str) -> list[dict[str, Any]]:
    requested = requested_reference.strip()
    return [record for record in records if _record_reference(record) == requested]


def _record_reference(record: dict[str, Any]) -> str | None:
    for key in ("irm_reference", "reference", "section_reference", "section", "section_number", "source_reference"):
        value = record.get(key)
        if value:
            return str(value).strip()
    return None


def _record_title(record: dict[str, Any]) -> str:
    for key in ("title", "heading", "section_title", "name"):
        value = record.get(key)
        if value:
            return _clean_text(str(value), max_length=160)
    return ""


def _record_summary(record: dict[str, Any]) -> str:
    for key in ("summary", "excerpt", "description", "text", "content", "body"):
        value = record.get(key)
        if value:
            return _clean_text(str(value), max_length=420)
    return ""


def _records_checklist(payload: dict[str, Any]) -> list[str]:
    value = payload.get("recommended_records")
    if not isinstance(value, list):
        value = payload.get("records")
    if not isinstance(value, list):
        return []
    return [_clean_text(str(item), max_length=120) for item in value if str(item).strip()]


def _issue_type_from_message(message: str) -> str:
    normalized = _normalize(message)
    if "trust fund recovery penalty" in normalized or "tfrp" in normalized:
        return "trust fund recovery penalty"
    if "levy" in normalized:
        return "levy"
    if "lien" in normalized:
        return "lien"
    if "payroll tax" in normalized:
        return "payroll tax"
    if "collection" in normalized or "collections" in normalized:
        return "collection"
    notice_match = _NOTICE_CODE_RE.search(message)
    if notice_match:
        return notice_match.group(1).replace(" ", "").upper()
    return message.strip()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _clean_text(value: str, max_length: int) -> str:
    cleaned = re.sub(r"\s+", " ", value.strip())
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "."


def _unique_preserving_order(values: Any) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _workflow_text_items(value: Any, max_length: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_clean_text(str(item), max_length=max_length) for item in value if str(item).strip()]


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").strip()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
