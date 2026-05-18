"""Tests for model provider abstraction."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.providers import DeterministicProvider, ProviderConfigError, ProviderResponse, get_provider
from app.providers.openai_compat import OpenAIProvider


# ---------------------------------------------------------------------------
# Default / configuration
# ---------------------------------------------------------------------------

def test_deterministic_is_default_provider() -> None:
    settings = Settings()
    assert settings.model_provider == "deterministic"


def test_get_provider_returns_deterministic_by_default() -> None:
    settings = Settings()
    provider = get_provider(settings)
    assert isinstance(provider, DeterministicProvider)


def test_get_provider_uses_model_name_from_settings() -> None:
    settings = Settings()
    provider = get_provider(settings)
    assert provider.model_name == settings.model_name


def test_get_provider_raises_for_unknown_provider() -> None:
    settings = Settings(BREVIX_AGENT_MODEL_PROVIDER="unknown_llm")
    with pytest.raises(ProviderConfigError, match="Unknown model provider"):
        get_provider(settings)


# ---------------------------------------------------------------------------
# DeterministicProvider
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deterministic_provider_returns_stable_output() -> None:
    provider = DeterministicProvider()
    context = {
        "intent": "fraud_pattern_search",
        "errors": [],
        "findings": [{"title": "Duplicate invoice", "severity": "critical"}],
        "risk_score": 95,
        "risk_level": "critical",
    }
    r1 = await provider.generate("any prompt", context)
    r2 = await provider.generate("any prompt", context)
    assert r1.text == r2.text


@pytest.mark.asyncio
async def test_deterministic_provider_metadata() -> None:
    provider = DeterministicProvider(model_name="deterministic-test-v1")
    context = {
        "intent": "fraud_pattern_search",
        "errors": [],
        "findings": [{"title": "Split payment"}],
        "risk_score": 80,
        "risk_level": "high",
    }
    response = await provider.generate("prompt", context)
    assert response.provider_name == "deterministic"
    assert response.model_name == "deterministic-test-v1"
    assert response.latency_ms >= 0.0
    assert response.tokens_input == 0
    assert response.tokens_output == 0
    assert response.tokens_total == 0


@pytest.mark.asyncio
async def test_deterministic_provider_with_findings() -> None:
    provider = DeterministicProvider()
    context = {
        "intent": "fraud_pattern_search",
        "errors": [],
        "findings": [{"title": "Vendor concentration"}, {"title": "Round dollar payments"}],
        "risk_score": 70,
        "risk_level": "high",
    }
    response = await provider.generate("prompt", context)
    assert "2 patterns" in response.text
    assert "may indicate" in response.text
    assert "does not prove fraud" in response.text
    assert "No alerts or cases were created." in response.text


@pytest.mark.asyncio
async def test_deterministic_provider_with_no_findings() -> None:
    provider = DeterministicProvider()
    context = {
        "intent": "fraud_pattern_search",
        "errors": [],
        "findings": [],
        "risk_score": 10,
        "risk_level": "low",
    }
    response = await provider.generate("prompt", context)
    assert "No alerts or cases were created." in response.text
    assert "does not prove fraud" not in response.text


@pytest.mark.asyncio
async def test_deterministic_provider_with_errors() -> None:
    provider = DeterministicProvider()
    context = {
        "intent": "fraud_pattern_search",
        "errors": ["tool timeout"],
        "findings": [],
        "risk_score": 0,
        "risk_level": "low",
    }
    response = await provider.generate("prompt", context)
    assert "could not complete" in response.text.lower()
    assert "No alerts or cases were created." in response.text


@pytest.mark.asyncio
async def test_deterministic_provider_with_unsupported_intent() -> None:
    provider = DeterministicProvider()
    context = {
        "intent": "unknown_or_unsupported",
        "errors": [],
        "findings": [],
        "risk_score": 0,
        "risk_level": "low",
    }
    response = await provider.generate("prompt", context)
    assert "No alerts or cases were created." in response.text
    assert "does not prove fraud" not in response.text


@pytest.mark.asyncio
async def test_deterministic_provider_with_transaction_lookup() -> None:
    provider = DeterministicProvider()
    context = {
        "intent": "transaction_lookup",
        "errors": [],
        "transaction_summary": {
            "date_from": "2026-05-14",
            "date_to": "2026-05-18",
            "total": 1,
            "returned_count": 1,
            "transactions": [
                {
                    "date": "2026-05-17",
                    "vendor": "Acme Supplies",
                    "amount": 125.5,
                    "status": "completed",
                }
            ],
        },
    }

    response = await provider.generate("prompt", context)

    assert "I found 1 transaction from 2026-05-14 to 2026-05-18" in response.text
    assert "Acme Supplies" in response.text
    assert "$125.50" in response.text
    assert "No alerts or cases were created." in response.text


@pytest.mark.asyncio
async def test_deterministic_provider_with_dashboard_health() -> None:
    provider = DeterministicProvider()
    context = {
        "intent": "dashboard_health",
        "errors": [],
        "dashboard_summary": {
            "risk_score": 42,
            "total_transactions": 128,
            "flagged_alerts": 3,
            "vendors_monitored": 18,
            "amount_reviewed": 125000.75,
        },
    }

    response = await provider.generate("prompt", context)

    assert "Your current financial health score is 42/100" in response.text
    assert "128 transactions" in response.text
    assert "3 open alerts" in response.text
    assert "$125,000.75" in response.text
    assert "No alerts or cases were created." in response.text


# ---------------------------------------------------------------------------
# ProviderResponse
# ---------------------------------------------------------------------------

def test_provider_response_tokens_total() -> None:
    r = ProviderResponse(
        text="hello",
        provider_name="openai",
        model_name="gpt-4o",
        latency_ms=120.5,
        tokens_input=50,
        tokens_output=30,
    )
    assert r.tokens_total == 80


def test_provider_response_zero_tokens_by_default() -> None:
    r = ProviderResponse(
        text="hello",
        provider_name="deterministic",
        model_name="deterministic-risk-v1",
        latency_ms=0.1,
    )
    assert r.tokens_input == 0
    assert r.tokens_output == 0
    assert r.tokens_total == 0


# ---------------------------------------------------------------------------
# OpenAIProvider — safe failure without API key
# ---------------------------------------------------------------------------

def test_openai_provider_fails_without_api_key() -> None:
    with pytest.raises(ProviderConfigError, match="OPENAI_API_KEY"):
        OpenAIProvider(api_key="")


def test_openai_provider_fails_with_none_key() -> None:
    with pytest.raises((ProviderConfigError, TypeError)):
        OpenAIProvider(api_key=None)  # type: ignore[arg-type]


def test_openai_provider_accepts_valid_key() -> None:
    provider = OpenAIProvider(api_key="sk-test-key", model_name="gpt-4o")
    assert provider.provider_name == "openai"
    assert provider.model_name == "gpt-4o"


def test_get_provider_openai_without_key_raises() -> None:
    settings = Settings(BREVIX_AGENT_MODEL_PROVIDER="openai", OPENAI_API_KEY="")
    with pytest.raises(ProviderConfigError, match="OPENAI_API_KEY"):
        get_provider(settings)


# ---------------------------------------------------------------------------
# CI / integration contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_response_contract_unchanged_with_deterministic_provider() -> None:
    from app.graph import build_graph
    from app.providers import DeterministicProvider
    from tests.fakes import FakeLaravelToolClient, base_state

    provider = DeterministicProvider()
    graph = build_graph(FakeLaravelToolClient(), provider=provider)
    result = await graph.ainvoke(base_state())

    assert "message" in result or "final_response" in result
    assert isinstance(result.get("findings", []), list)
    assert isinstance(result.get("recommended_actions", []), list)
    assert isinstance(result.get("steps", []), list)
    assert isinstance(result.get("errors", []), list)


@pytest.mark.asyncio
async def test_provider_metadata_flows_into_usage() -> None:
    from app.graph import build_graph
    from app.observability import summarize_usage
    from app.providers import DeterministicProvider
    from tests.fakes import FakeLaravelToolClient, base_state

    provider = DeterministicProvider()
    graph = build_graph(FakeLaravelToolClient(), provider=provider)
    result = await graph.ainvoke(base_state())

    settings = Settings()
    usage = summarize_usage(result, 10.0, settings)
    assert "model_provider" in usage
    assert "model_name" in usage
    assert "tokens_input" in usage
    assert "tokens_output" in usage
    assert "tokens_total" in usage
    assert usage["tokens_input"] == 0
    assert usage["tokens_total"] == 0
