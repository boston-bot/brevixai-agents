"""Tests for CORS origin selection logic in app.main._cors_origins."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.main import _cors_origins, _validate_startup_config


def _settings(**env_overrides: str):
    """Construct a Settings object with specific env var overrides.

    Environment variables take priority over the .env file in pydantic-settings,
    so this reliably controls exactly the fields under test without touching disk.
    """
    from app.config import Settings

    with patch.dict(os.environ, env_overrides, clear=False):
        return Settings()


def test_cors_wildcard_in_local_env() -> None:
    settings = _settings(APP_ENV="local", ORCHESTRATOR_ALLOWED_ORIGINS="")
    assert _cors_origins(settings) == ["*"]


def test_cors_wildcard_in_dev_env() -> None:
    settings = _settings(APP_ENV="dev", ORCHESTRATOR_ALLOWED_ORIGINS="")
    assert _cors_origins(settings) == ["*"]


def test_cors_wildcard_in_test_env() -> None:
    settings = _settings(APP_ENV="test", ORCHESTRATOR_ALLOWED_ORIGINS="")
    assert _cors_origins(settings) == ["*"]


def test_cors_raises_in_production_without_origins() -> None:
    settings = _settings(APP_ENV="production", ORCHESTRATOR_ALLOWED_ORIGINS="")
    with pytest.raises(RuntimeError, match="ORCHESTRATOR_ALLOWED_ORIGINS"):
        _cors_origins(settings)


def test_cors_raises_in_prod_shorthand_without_origins() -> None:
    settings = _settings(APP_ENV="prod", ORCHESTRATOR_ALLOWED_ORIGINS="")
    with pytest.raises(RuntimeError, match="ORCHESTRATOR_ALLOWED_ORIGINS"):
        _cors_origins(settings)


def test_cors_uses_configured_origin_in_production() -> None:
    settings = _settings(APP_ENV="production", ORCHESTRATOR_ALLOWED_ORIGINS="https://app.brevix.ai")
    assert _cors_origins(settings) == ["https://app.brevix.ai"]


def test_cors_uses_configured_origin_in_local_env() -> None:
    settings = _settings(APP_ENV="local", ORCHESTRATOR_ALLOWED_ORIGINS="https://localhost:3000")
    assert _cors_origins(settings) == ["https://localhost:3000"]


def test_cors_parses_multiple_origins() -> None:
    settings = _settings(
        APP_ENV="production",
        ORCHESTRATOR_ALLOWED_ORIGINS="https://app.brevix.ai,https://admin.brevix.ai",
    )
    assert _cors_origins(settings) == ["https://app.brevix.ai", "https://admin.brevix.ai"]


def test_cors_trims_whitespace_from_origins() -> None:
    settings = _settings(
        APP_ENV="local",
        ORCHESTRATOR_ALLOWED_ORIGINS=" https://a.example.com , https://b.example.com ",
    )
    assert _cors_origins(settings) == ["https://a.example.com", "https://b.example.com"]


def test_cors_error_message_names_the_variable() -> None:
    """The error message must name the env var so operators know exactly what to set."""
    settings = _settings(APP_ENV="production", ORCHESTRATOR_ALLOWED_ORIGINS="")
    with pytest.raises(RuntimeError, match="ORCHESTRATOR_ALLOWED_ORIGINS"):
        _cors_origins(settings)


def test_production_startup_requires_agent_service_key() -> None:
    settings = _settings(
        APP_ENV="production",
        BREVIX_AGENT_SERVICE_KEY="",
        ORCHESTRATOR_API_TOKEN="",
        BREVIX_LARAVEL_AGENT_TOOL_KEY="tool-key",
    )

    with pytest.raises(RuntimeError, match="BREVIX_AGENT_SERVICE_KEY"):
        _validate_startup_config(settings)


def test_production_startup_accepts_orchestrator_api_token_alias() -> None:
    settings = _settings(
        APP_ENV="production",
        BREVIX_AGENT_SERVICE_KEY="",
        ORCHESTRATOR_API_TOKEN="token-from-orchestrator",
        BREVIX_LARAVEL_AGENT_TOOL_KEY="tool-key",
    )

    assert settings.agent_service_key == "token-from-orchestrator"
    _validate_startup_config(settings)


def test_production_startup_requires_laravel_tool_key() -> None:
    settings = _settings(
        APP_ENV="production",
        BREVIX_AGENT_SERVICE_KEY="agent-key",
        BREVIX_LARAVEL_AGENT_TOOL_KEY="",
    )

    with pytest.raises(RuntimeError, match="BREVIX_LARAVEL_AGENT_TOOL_KEY"):
        _validate_startup_config(settings)
