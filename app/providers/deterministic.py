"""Deterministic model provider — rule-based, no external calls, stable output."""
from __future__ import annotations

import time
from typing import Any

from app.providers.base import ProviderResponse


class DeterministicProvider:
    provider_name = "deterministic"

    def __init__(self, model_name: str = "deterministic-risk-v1") -> None:
        self.model_name = model_name

    async def generate(self, prompt: str, context: dict[str, Any]) -> ProviderResponse:
        start = time.perf_counter()
        text = _explanation_from_context(context)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return ProviderResponse(
            text=text,
            provider_name=self.provider_name,
            model_name=self.model_name,
            latency_ms=latency_ms,
            tokens_input=0,
            tokens_output=0,
        )


def _explanation_from_context(context: dict[str, Any]) -> str:
    errors = context.get("errors") or []
    intent = context.get("intent")
    risk_score = context.get("risk_score", 0)
    risk_level = context.get("risk_level", "low")
    findings = context.get("findings") or []

    if errors:
        return "I could not complete the risk review right now. No alerts or cases were created."

    if intent == "unknown_or_unsupported":
        return (
            "I can help with risk, suspicious activity, vendor, transaction, and alert questions. "
            "No alerts or cases were created."
        )

    if intent == "transaction_lookup":
        return _transaction_lookup_response(context)

    if intent == "dashboard_health":
        return _dashboard_health_response(context)

    if not findings:
        return (
            f"The deterministic Brevix risk services did not return specific fraud indicators "
            f"for this request. The current risk score is {risk_score}/100 ({risk_level}). "
            "No alerts or cases were created."
        )

    first = findings[0]
    count = len(findings)
    plural = "s" if count != 1 else ""
    return (
        f"Brevix found {count} pattern{plural} worth reviewing. "
        f"The current risk score is {risk_score}/100 ({risk_level}). "
        f"The strongest signal is: {first.get('title')}. "
        "This may indicate an accounting risk, but it does not prove fraud. "
        "No alerts or cases were created."
    )


def _transaction_lookup_response(context: dict[str, Any]) -> str:
    summary = context.get("transaction_summary") or {}
    transactions = summary.get("transactions") if isinstance(summary, dict) else []
    if not isinstance(transactions, list):
        transactions = []

    total = int(summary.get("total") or 0) if isinstance(summary, dict) else 0
    returned_count = int(summary.get("returned_count") or len(transactions)) if isinstance(summary, dict) else len(transactions)
    date_from = summary.get("date_from") if isinstance(summary, dict) else None
    date_to = summary.get("date_to") if isinstance(summary, dict) else None
    range_text = f" from {date_from} to {date_to}" if date_from and date_to else ""

    if total == 0:
        return f"I did not find any transactions{range_text}. No alerts or cases were created."

    lines = []
    for tx in transactions[:5]:
        if not isinstance(tx, dict):
            continue
        date = tx.get("date") or "unknown date"
        vendor = tx.get("vendor") or "Unknown counterparty"
        amount = _format_amount(tx.get("amount"))
        status = tx.get("status") or "unknown status"
        lines.append(f"{date}: {vendor} for {amount} ({status})")

    sample = "; ".join(lines)
    if sample:
        return (
            f"I found {total} transaction{'s' if total != 1 else ''}{range_text}; "
            f"showing {min(returned_count, len(lines))}: {sample}. "
            "No alerts or cases were created."
        )

    return (
        f"I found {total} transaction{'s' if total != 1 else ''}{range_text}, "
        "but there were no displayable rows in the returned summary. No alerts or cases were created."
    )


def _format_amount(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "an unknown amount"


def _dashboard_health_response(context: dict[str, Any]) -> str:
    summary = context.get("dashboard_summary") or {}
    if not isinstance(summary, dict) or not summary:
        return "I could not find current dashboard health metrics right now. No alerts or cases were created."

    risk_score = int(summary.get("risk_score") or 0)
    total_transactions = int(summary.get("total_transactions") or 0)
    flagged_alerts = int(summary.get("flagged_alerts") or 0)
    vendors_monitored = int(summary.get("vendors_monitored") or 0)
    amount_reviewed = _format_amount(summary.get("amount_reviewed"))

    return (
        f"Your current financial health score is {risk_score}/100. "
        f"I reviewed {total_transactions} transaction{'s' if total_transactions != 1 else ''}, "
        f"{flagged_alerts} open alert{'s' if flagged_alerts != 1 else ''}, "
        f"and {vendors_monitored} monitored vendor{'s' if vendors_monitored != 1 else ''}, "
        f"covering {amount_reviewed} in activity. "
        "No alerts or cases were created."
    )
