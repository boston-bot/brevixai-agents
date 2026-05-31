"""Tests for IRS Knowledge MCP tool adapters."""

from __future__ import annotations

import pytest

from mcp_servers.brevix_intelligence.tools.irs_knowledge import (
    explain_notice_type,
    recommend_records_to_gather,
    search_irm,
    summarize_collection_risk,
)


class FakeIrmClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def irm_search(self, topic: str, limit: int, user_id: str) -> dict:
        self.calls.append(("irm_search", {"topic": topic, "limit": limit, "user_id": user_id}))
        return {"status": "ok", "query": topic, "results": [{"irm_reference": "5.11.1.1"}]}

    async def irs_notice_type(self, code: str, limit: int, user_id: str) -> dict:
        self.calls.append(("irs_notice_type", {"code": code, "limit": limit, "user_id": user_id}))
        return {"status": "ok", "notice_code": code, "results": [{"irm_reference": "5.1.10.3"}]}

    async def irs_collection_risk(self, issue_type: str, limit: int, user_id: str) -> dict:
        self.calls.append(("irs_collection_risk", {"issue_type": issue_type, "limit": limit, "user_id": user_id}))
        return {"status": "ok", "issue_type": issue_type, "severity": "critical", "results": []}

    async def irs_records_checklist(self, issue_type: str, limit: int, user_id: str) -> dict:
        self.calls.append(("irs_records_checklist", {"issue_type": issue_type, "limit": limit, "user_id": user_id}))
        return {"status": "ok", "issue_type": issue_type, "recommended_records": ["Notice"], "results": []}


@pytest.mark.asyncio
async def test_search_irm_delegates_to_laravel_client() -> None:
    client = FakeIrmClient()

    result = await search_irm(client, "levy notice", limit=3, user_id="user-1")

    assert result["query"] == "levy notice"
    assert client.calls == [("irm_search", {"topic": "levy notice", "limit": 3, "user_id": "user-1"})]


@pytest.mark.asyncio
async def test_explain_notice_type_delegates_to_laravel_client() -> None:
    client = FakeIrmClient()

    result = await explain_notice_type(client, "CP504")

    assert result["notice_code"] == "CP504"
    assert client.calls[0][0] == "irs_notice_type"


@pytest.mark.asyncio
async def test_summarize_collection_risk_delegates_to_laravel_client() -> None:
    client = FakeIrmClient()

    result = await summarize_collection_risk(client, "levy")

    assert result["severity"] == "critical"
    assert client.calls[0][0] == "irs_collection_risk"


@pytest.mark.asyncio
async def test_recommend_records_to_gather_delegates_to_laravel_client() -> None:
    client = FakeIrmClient()

    result = await recommend_records_to_gather(client, "payroll tax")

    assert result["recommended_records"] == ["Notice"]
    assert client.calls[0][0] == "irs_records_checklist"
