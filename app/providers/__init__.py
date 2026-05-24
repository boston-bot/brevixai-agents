from __future__ import annotations

from app.providers.base import ModelProvider, ProviderConfigError, ProviderResponse, ProviderRuntimeError
from app.providers.deterministic import DeterministicProvider

__all__ = [
    "DeterministicProvider",
    "ModelProvider",
    "ProviderConfigError",
    "ProviderResponse",
    "ProviderRuntimeError",
    "get_provider",
]


def get_provider(settings) -> ModelProvider:
    """Return the configured model provider.

    Raises ProviderConfigError for unknown provider names or missing config.
    """
    name = settings.model_provider
    model = settings.model_name
    timeout = settings.model_timeout_seconds

    if name == "deterministic":
        return DeterministicProvider(model_name=model)

    if name == "openai":
        from app.providers.openai_compat import OpenAIProvider

        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model_name=model,
            timeout_seconds=timeout,
        )

    raise ProviderConfigError(
        f"Unknown model provider: '{name}'. "
        "Supported providers: deterministic, openai. "
        "Set BREVIX_AGENT_MODEL_PROVIDER in your environment."
    )
