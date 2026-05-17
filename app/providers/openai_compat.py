"""OpenAI-compatible model provider.

This provider is disabled by default and requires:
  - BREVIX_AGENT_MODEL_PROVIDER=openai
  - OPENAI_API_KEY set in the environment
  - The openai package installed: pip install -e '.[llm]'

It is never imported unless explicitly selected, so tests and CI that
use the deterministic provider incur no import or network cost here.
"""
from __future__ import annotations

import time
from typing import Any

from app.providers.base import ProviderConfigError, ProviderResponse


class OpenAIProvider:
    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o",
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key:
            raise ProviderConfigError(
                "OPENAI_API_KEY is required when BREVIX_AGENT_MODEL_PROVIDER=openai. "
                "Set OPENAI_API_KEY in your .env file or environment, "
                "or switch back to BREVIX_AGENT_MODEL_PROVIDER=deterministic."
            )
        self._api_key = api_key
        self.model_name = model_name
        self._timeout = timeout_seconds

    async def generate(self, prompt: str, context: dict[str, Any]) -> ProviderResponse:
        try:
            import openai
        except ImportError:
            raise ProviderConfigError(
                "The 'openai' package is required for the openai provider. "
                "Install it with: pip install -e '.[llm]'"
            )

        start = time.perf_counter()
        client = openai.AsyncOpenAI(api_key=self._api_key, timeout=self._timeout)
        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.1,
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        choice = response.choices[0]
        usage = response.usage
        return ProviderResponse(
            text=choice.message.content or "",
            provider_name=self.provider_name,
            model_name=self.model_name,
            latency_ms=latency_ms,
            tokens_input=usage.prompt_tokens if usage else 0,
            tokens_output=usage.completion_tokens if usage else 0,
        )
