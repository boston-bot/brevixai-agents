from __future__ import annotations

from typing import Any

import httpx


class LaravelToolError(RuntimeError):
    pass


class LaravelToolClient:
    """HTTP client for approved deterministic Laravel agent tools.

    This client intentionally exposes specific tool methods only. It never
    accepts SQL or arbitrary endpoint paths from graph state or user input.
    """

    def __init__(self, base_url: str, tool_key: str, timeout_seconds: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.tool_key = tool_key
        self.timeout_seconds = timeout_seconds

    async def company_context(self, company_id: str, user_id: str) -> dict[str, Any]:
        return await self._get(f"/api/internal/agent-tools/companies/{company_id}/context", user_id)

    async def risk_summary(self, company_id: str, user_id: str, period: str | None = None) -> dict[str, Any]:
        params = {"period": period} if period else None
        return await self._get(
            f"/api/internal/agent-tools/companies/{company_id}/risk-summary",
            user_id,
            params=params,
        )

    async def _get(
        self,
        path: str,
        user_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.tool_key:
            raise LaravelToolError("Laravel agent tool key is not configured.")

        headers = {
            "Authorization": f"Bearer {self.tool_key}",
            "Accept": "application/json",
            "X-Brevix-User-Id": user_id,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(f"{self.base_url}{path}", headers=headers, params=params)

        if response.status_code >= 400:
            raise LaravelToolError(f"Laravel tool request failed with status {response.status_code}.")

        data = response.json()
        if not isinstance(data, dict):
            raise LaravelToolError("Laravel tool returned an invalid payload.")

        return data
