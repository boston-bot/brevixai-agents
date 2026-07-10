from __future__ import annotations

import re
from typing import Any

_ALLOWED_CONFIDENCE = {"high", "medium"}

_MAX_PLAYBOOK_REFS = 3

_MAX_GUIDANCE_ITEMS = 6


async def retrieve_playbook_context(tool_client: Any, state: dict[str, Any]) -> dict[str, Any]:
    """Retrieve review-playbook context that frames a fraud-pattern review.

    Calls the global fraud_playbook_search Laravel tool with the user's message
    and distills the high/medium-confidence matches into reviewer guidance:
    playbook references (pinned create_investigation contract shape), recommended
    tests, document requests, and red flags to compare against deterministic
    evidence. Playbook text is guidance for the reviewer only — it is never used
    to assert that any improper activity occurred.
    """
    query = _retrieval_query(state)
    response = await tool_client.fraud_playbook_search(
        query=query,
        limit=5,
        user_id=state.get("user_id") or "mcp_service",
        trace_id=state.get("agent_run_id"),
        trace_metadata={"intent": state.get("intent")},
    )
    payload = response if isinstance(response, dict) else {}

    corpus_version = str(payload.get("corpus_version") or "").strip()
    results = [result for result in payload.get("results") or [] if isinstance(result, dict)]
    matched = [
        result
        for result in results
        if str(result.get("confidence") or "").strip().lower() in _ALLOWED_CONFIDENCE
    ][:_MAX_PLAYBOOK_REFS]

    playbook_refs = [_playbook_ref(result, corpus_version) for result in matched]
    documents = [
        result["document"]
        for result in matched
        if isinstance(result.get("document"), dict)
    ]

    return {
        "status": "matched" if playbook_refs else "no_matches",
        "retrieval_query": query,
        "corpus_version": corpus_version or None,
        "result_count": len(results),
        "playbook_refs": playbook_refs,
        "recommended_tests": _collect_document_items(documents, "tests"),
        "document_requests": _collect_document_items(documents, "document_requests"),
        "red_flags": _collect_document_items(documents, "red_flags"),
        "evidence_requests": _evidence_requests(matched),
        "disclaimer": str(payload.get("disclaimer") or "").strip() or None,
    }


def _playbook_ref(result: dict[str, Any], corpus_version: str) -> dict[str, Any]:
    matched_fields = _unique_preserving_order(
        str(field).strip()
        for citation in result.get("citations") or []
        if isinstance(citation, dict)
        for field in citation.get("fields") or []
        if str(field).strip()
    )
    return {
        "playbook_id": str(result.get("source_id") or "").strip(),
        "title": str(result.get("title") or "").strip(),
        "confidence": str(result.get("confidence") or "").strip().lower(),
        "relevance_score": _coerce_float(result.get("relevance_score")),
        "corpus_version": corpus_version,
        "matched_fields": matched_fields,
    }


def _retrieval_query(state: dict[str, Any]) -> str:
    message = str(state.get("user_message") or "").strip()
    context_terms = _context_terms(state)
    if not context_terms:
        return message

    context = "; ".join(context_terms[:10])
    query = f"{message}\nContext: {context}" if message else context
    return query[:1000].strip()


def _context_terms(state: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    page_context = state.get("page_context")
    if isinstance(page_context, dict):
        for key in ("vendor_name", "vendor", "invoice_number", "memo", "payment_memo", "category"):
            value = str(page_context.get(key) or "").strip()
            if value:
                terms.append(f"{key.replace('_', ' ')}: {value}")

    company_context = state.get("company_context")
    if isinstance(company_context, dict):
        transaction_summary = company_context.get("transaction_summary")
        transactions = transaction_summary.get("transactions") if isinstance(transaction_summary, dict) else []
        if isinstance(transactions, list):
            for transaction in transactions[:5]:
                if not isinstance(transaction, dict):
                    continue
                vendor = str(transaction.get("vendor") or "").strip()
                invoice = str(transaction.get("invoice_number") or "").strip()
                memo = str(transaction.get("memo") or "").strip()
                category = str(transaction.get("category") or "").strip()
                if vendor:
                    terms.append(f"transaction vendor: {vendor}")
                if invoice:
                    terms.append(f"invoice: {invoice}")
                if memo:
                    terms.append(f"memo: {memo}")
                if category:
                    terms.append(f"category: {category}")

    return _unique_preserving_order(terms)


def _collect_document_items(documents: list[dict[str, Any]], field: str) -> list[str]:
    return _unique_preserving_order(
        str(item).strip()
        for document in documents
        for item in document.get(field) or []
        if str(item).strip()
    )[:_MAX_GUIDANCE_ITEMS]


def _evidence_requests(matched: list[dict[str, Any]]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in matched:
        document = result.get("document") if isinstance(result.get("document"), dict) else {}
        title = str(document.get("title") or result.get("title") or "review playbook").strip()
        playbook_id = str(document.get("source_id") or result.get("source_id") or "").strip()
        for item in document.get("document_requests") or []:
            label = str(item).strip()
            if not label or label.lower() in seen:
                continue
            seen.add(label.lower())
            requests.append({
                "requirement_key": _requirement_key(label),
                "label": label,
                "reason": f"Requested by the matched review playbook '{title}' to support evidence review.",
                "priority": "recommended",
                "status": "missing",
                "source": "fraud_playbook",
                "playbook_id": playbook_id,
            })
            if len(requests) >= _MAX_GUIDANCE_ITEMS:
                return requests
    return requests


def _requirement_key(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")
    return f"playbook_{slug or 'document_request'}"


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _unique_preserving_order(values: Any) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
