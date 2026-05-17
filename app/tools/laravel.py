from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from langsmith import traceable

from app.config import get_settings
from app.observability import sanitize_tool_inputs, sanitize_tool_outputs


class LaravelToolError(RuntimeError):
    pass


logger = logging.getLogger("brevix.agent.tools")


class LaravelToolClient:
    """HTTP client for approved deterministic Laravel agent tools.

    This client intentionally exposes specific tool methods only. It never
    accepts SQL or arbitrary endpoint paths from graph state or user input.
    """

    def __init__(self, base_url: str, tool_key: str, timeout_seconds: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.tool_key = tool_key
        self.timeout_seconds = timeout_seconds

    async def company_context(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/companies/{company_id}/context",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "company_context",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "company_context",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def risk_summary(
        self,
        company_id: str,
        user_id: str,
        period: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = {"period": period} if period else None
        return await self._get(
            f"/api/internal/agent-tools/companies/{company_id}/risk-summary",
            user_id,
            params=params,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "risk_summary",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "risk_summary",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    @traceable(
        name="agent.tool.laravel_get",
        run_type="tool",
        process_inputs=sanitize_tool_inputs,
        process_outputs=sanitize_tool_outputs,
    )
    async def _get(
        self,
        path: str,
        user_id: str,
        params: dict[str, Any] | None = None,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if not self.tool_key:
            raise LaravelToolError("Laravel agent tool key is not configured.")

        headers = {
            "Authorization": f"Bearer {self.tool_key}",
            "Accept": "application/json",
            "X-Brevix-User-Id": user_id,
        }
        if trace_id:
            headers["X-Brevix-Agent-Request-Id"] = trace_id

        settings = get_settings()
        metadata = {
            "trace_id": trace_id,
            "user_id": user_id,
            "tool_endpoint": path,
            "environment": settings.app_env,
            "graph_version": settings.graph_version,
            "feature_flags": settings.feature_flag_list,
            "model_name": settings.model_name,
            **(trace_metadata or {}),
        }
        start = time.perf_counter()
        status = "completed"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url}{path}",
                    headers=headers,
                    params=params,
                )

            if response.status_code >= 400:
                status = "failed"
                raise LaravelToolError(f"Laravel tool request failed with status {response.status_code}.")

            data = response.json()
            if not isinstance(data, dict):
                status = "failed"
                raise LaravelToolError("Laravel tool returned an invalid payload.")

            return data
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "agent_tool_timing %s",
                json.dumps(
                    {
                        **{key: value for key, value in metadata.items() if value is not None},
                        "latency_ms": latency_ms,
                        "status": status,
                    },
                    sort_keys=True,
                ),
            )

    def _langsmith_extra(
        self,
        tool_name: str,
        company_id: str,
        user_id: str,
        trace_id: str | None,
        trace_metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        settings = get_settings()
        metadata = {
            "trace_id": trace_id,
            "user_id": user_id,
            "company_id": company_id,
            "tool_name": tool_name,
            "environment": settings.app_env,
            "graph_version": settings.graph_version,
            "feature_flags": settings.feature_flag_list,
            "model_name": settings.model_name,
            **(trace_metadata or {}),
        }
        return {
            "metadata": {key: value for key, value in metadata.items() if value is not None},
            "tags": ["brevix-ai", "agent-tool", tool_name],
        }
