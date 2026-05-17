"""Model provider interface for Brevix AI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class ProviderConfigError(Exception):
    """Raised when a provider cannot be initialized due to missing or invalid config."""


@dataclass
class ProviderResponse:
    text: str
    provider_name: str
    model_name: str
    latency_ms: float
    tokens_input: int = 0
    tokens_output: int = 0

    @property
    def tokens_total(self) -> int:
        return self.tokens_input + self.tokens_output


@runtime_checkable
class ModelProvider(Protocol):
    provider_name: str
    model_name: str

    async def generate(self, prompt: str, context: dict[str, Any]) -> ProviderResponse: ...
