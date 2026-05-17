from __future__ import annotations

import httpx
import pytest

from app.tools.laravel import LaravelToolClient


@pytest.mark.asyncio
async def test_laravel_tool_client_uses_internal_agent_tool_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict] = []

    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, headers: dict, params: dict | None = None) -> httpx.Response:
            requests.append({"url": url, "headers": headers, "params": params})
            return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = LaravelToolClient("http://laravel.test", "tool-key", timeout_seconds=3)

    await client.company_context("company-1", "user-1")
    await client.risk_summary("company-1", "user-1", period="2026-05")

    assert requests[0]["url"] == "http://laravel.test/api/internal/agent-tools/companies/company-1/context"
    assert requests[1]["url"] == "http://laravel.test/api/internal/agent-tools/companies/company-1/risk-summary"
    assert requests[1]["params"] == {"period": "2026-05"}
    assert requests[0]["headers"]["Authorization"] == "Bearer tool-key"
    assert requests[0]["headers"]["X-Brevix-User-Id"] == "user-1"
