from __future__ import annotations

import httpx
import pytest

from app.tools.laravel import LaravelToolClient, LaravelToolError


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


@pytest.mark.asyncio
async def test_laravel_tool_client_wraps_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, headers: dict, params: dict | None = None) -> httpx.Response:
            request = httpx.Request("GET", url, headers=headers)
            raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = LaravelToolClient("http://laravel.test", "tool-key", timeout_seconds=3)

    with pytest.raises(LaravelToolError, match="Laravel tool request failed"):
        await client.company_context("company-1", "user-1")


@pytest.mark.asyncio
async def test_laravel_tool_client_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, headers: dict, params: dict | None = None) -> httpx.Response:
            return httpx.Response(200, text="not json")

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = LaravelToolClient("http://laravel.test", "tool-key", timeout_seconds=3)

    with pytest.raises(LaravelToolError, match="invalid JSON"):
        await client.company_context("company-1", "user-1")


@pytest.mark.asyncio
async def test_laravel_tool_client_uses_irs_knowledge_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
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

    await client.irm_search("levy notice", limit=3, user_id="user-1")
    await client.irm_section("5.11.1.1", user_id="user-1")
    await client.irs_notice_type("CP504", limit=2, user_id="user-1")
    await client.irs_records_checklist("levy", user_id="user-1")
    await client.irs_collection_risk("trust fund recovery penalty", user_id="user-1")

    assert requests[0]["url"] == "http://laravel.test/api/internal/agent-tools/irs/irm/search"
    assert requests[0]["params"] == {"topic": "levy notice", "limit": 3}
    assert requests[1]["url"] == "http://laravel.test/api/internal/agent-tools/irs/irm/section"
    assert requests[1]["params"] == {"reference": "5.11.1.1"}
    assert requests[2]["url"] == "http://laravel.test/api/internal/agent-tools/irs/notice-type"
    assert requests[2]["params"] == {"code": "CP504", "limit": 2}
    assert requests[3]["url"] == "http://laravel.test/api/internal/agent-tools/irs/records-checklist"
    assert requests[4]["url"] == "http://laravel.test/api/internal/agent-tools/irs/collection-risk"


@pytest.mark.asyncio
async def test_laravel_tool_client_uses_fraud_playbook_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[dict] = []

    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, headers: dict, params: dict | None = None) -> httpx.Response:
            requests.append({"method": "GET", "url": url, "headers": headers, "params": params})
            return httpx.Response(200, json={"ok": True})

        async def post(self, url: str, headers: dict, json: dict | None = None) -> httpx.Response:
            requests.append({"method": "POST", "url": url, "headers": headers, "json": json})
            return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    client = LaravelToolClient("http://laravel.test", "tool-key", timeout_seconds=3)

    await client.fraud_playbook_search("duplicate invoice", limit=3, user_id="user-1", trace_id="run-1")
    await client.fraud_playbook_feedback(
        playbook_id=12,
        query_text="duplicate invoice",
        relevance_score=4,
        user_feedback="useful match",
        user_id="user-1",
        trace_id="run-1",
    )

    assert requests[0]["method"] == "GET"
    assert requests[0]["url"] == "http://laravel.test/api/internal/agent-tools/fraud/playbooks/search"
    assert requests[0]["params"] == {"query": "duplicate invoice", "limit": 3}
    assert requests[0]["headers"]["Authorization"] == "Bearer tool-key"
    assert requests[0]["headers"]["X-Brevix-User-Id"] == "user-1"
    assert requests[0]["headers"]["X-Brevix-Agent-Request-Id"] == "run-1"
    assert requests[1]["method"] == "POST"
    assert requests[1]["url"] == "http://laravel.test/api/internal/agent-tools/fraud/playbooks/feedback"
    assert requests[1]["json"] == {
        "playbook_id": 12,
        "query_text": "duplicate invoice",
        "relevance_score": 4,
        "user_feedback": "useful match",
    }
