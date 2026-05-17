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
