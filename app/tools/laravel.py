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

    _CACHE_TTL_SECONDS = 60

    def __init__(self, base_url: str, tool_key: str, timeout_seconds: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.tool_key = tool_key
        self.timeout_seconds = timeout_seconds
        # Per-instance request-lifecycle cache: {key: (result, expiry_ts)}
        self._cache: dict[str, tuple[dict[str, Any], float]] = {}

    async def company_context(
        self,
        company_id: str,
        user_id: str,
        dashboard_context: bool = False,
        transaction_filters: dict[str, Any] | None = None,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] | None = None
        if dashboard_context or transaction_filters is not None:
            params = {}

        if dashboard_context and params is not None:
            params["include_dashboard"] = "1"

        if transaction_filters is not None and params is not None:
            params.update({
                "include_transactions": "1",
                **{
                    key: value
                    for key, value in transaction_filters.items()
                    if key in {"date_from", "date_to", "limit"} and value is not None
                },
            })

        _kwargs: dict[str, Any] = {
            "params": params,
            "trace_id": trace_id,
            "trace_metadata": {
                "tool_name": "company_context",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            "langsmith_extra": self._langsmith_extra(
                "company_context",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        }
        _path = f"/api/internal/agent-tools/companies/{company_id}/context"
        if params is None:
            return await self._cached_get(f"company_context:{company_id}", _path, user_id, **_kwargs)
        return await self._get(_path, user_id, **_kwargs)

    async def risk_summary(
        self,
        company_id: str,
        user_id: str,
        period: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = {"period": period} if period else None
        cache_key = f"risk_summary:{company_id}:{period or 'default'}"
        return await self._cached_get(
            cache_key,
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

    async def vendor_risk(
        self,
        company_id: str,
        user_id: str,
        vendor: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = {"vendor": vendor} if vendor else None
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/vendor-risk",
            user_id,
            params=params,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "vendor_risk",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "vendor_risk",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def reconciliation_risk(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/reconciliation-risk",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "reconciliation_risk",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "reconciliation_risk",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def entity_relationship_risk(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/entity-relationship-risk",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "entity_relationship_risk",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "entity_relationship_risk",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def aggregate_risk_summary(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/aggregate-risk-summary",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "aggregate_risk_summary",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "aggregate_risk_summary",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def alert_recommendations(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/alert-recommendations",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "alert_recommendations",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "alert_recommendations",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def case_recommendations(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/case-recommendations",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "case_recommendations",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "case_recommendations",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def pending_recommendations(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/pending-recommendations",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "pending_recommendations",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "pending_recommendations",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def dashboard_health(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/dashboard",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "dashboard_health",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "dashboard_health",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def transaction_lookup(
        self,
        company_id: str,
        user_id: str,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int | None = None,
        vendor: str | None = None,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if limit is not None:
            params["limit"] = limit
        if vendor:
            params["vendor"] = vendor
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/transactions",
            user_id,
            params=params or None,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "transaction_lookup",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "transaction_lookup",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def transaction_detail(
        self,
        company_id: str,
        user_id: str,
        ids: list[str] | None = None,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # PHP expects ids[] for array query params
        params: list[tuple[str, str]] | None = None
        if ids:
            params = [("ids[]", txn_id) for txn_id in ids[:20]]
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/transaction-detail",
            user_id,
            params=params,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "transaction_detail",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "transaction_detail",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def behavioral_baseline(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/company/{company_id}/behavioral-baseline",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "behavioral_baseline",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "behavioral_baseline",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def onboarding_context(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cache_key = f"onboarding_context:{company_id}"
        return await self._cached_get(
            cache_key,
            f"/api/internal/agent-tools/companies/{company_id}/onboarding-context",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "onboarding_context",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "onboarding_context",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def evidence_requirements(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cache_key = f"evidence_requirements:{company_id}"
        return await self._cached_get(
            cache_key,
            f"/api/internal/agent-tools/companies/{company_id}/evidence-requirements",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "evidence_requirements",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "evidence_requirements",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def data_source_status(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/companies/{company_id}/data-source-status",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "data_source_status",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "data_source_status",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def first_snapshot(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/companies/{company_id}/first-snapshot",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "first_snapshot",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "first_snapshot",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def action_plan(
        self,
        company_id: str,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/internal/agent-tools/companies/{company_id}/action-plan",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "action_plan",
                "company_id": company_id,
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "action_plan",
                company_id,
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def process_registry(
        self,
        user_id: str,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            "/api/internal/agent-tools/process-registry",
            user_id,
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "process_registry",
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "process_registry",
                "",
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def irm_search(
        self,
        topic: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            "/api/internal/agent-tools/irs/irm/search",
            user_id,
            params={"topic": topic, "limit": limit},
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "irm_search",
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "irm_search",
                "",
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def irm_section(
        self,
        reference: str,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            "/api/internal/agent-tools/irs/irm/section",
            user_id,
            params={"reference": reference},
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "irm_section",
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "irm_section",
                "",
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def irs_notice_type(
        self,
        code: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            "/api/internal/agent-tools/irs/notice-type",
            user_id,
            params={"code": code, "limit": limit},
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "irs_notice_type",
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "irs_notice_type",
                "",
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def irs_records_checklist(
        self,
        issue_type: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            "/api/internal/agent-tools/irs/records-checklist",
            user_id,
            params={"issue_type": issue_type, "limit": limit},
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "irs_records_checklist",
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "irs_records_checklist",
                "",
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def irs_collection_risk(
        self,
        issue_type: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._get(
            "/api/internal/agent-tools/irs/collection-risk",
            user_id,
            params={"issue_type": issue_type, "limit": limit},
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "irs_collection_risk",
                **(trace_metadata or {}),
            },
            langsmith_extra=self._langsmith_extra(
                "irs_collection_risk",
                "",
                user_id,
                trace_id,
                trace_metadata,
            ),
        )

    async def irs_notice_extract(
        self,
        text: str,
        limit: int = 5,
        user_id: str = "mcp_service",
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._post(
            "/api/internal/agent-tools/irs/notice/extract",
            user_id,
            json_body={"text": text, "limit": limit},
            trace_id=trace_id,
            trace_metadata={
                "tool_name": "irs_notice_extract",
                **(trace_metadata or {}),
            },
        )

    @traceable(
        name="agent.tool.laravel_get",
        run_type="tool",
        process_inputs=sanitize_tool_inputs,
        process_outputs=sanitize_tool_outputs,
    )
    async def _post(
        self,
        path: str,
        user_id: str,
        json_body: dict[str, Any] | None = None,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if not self.tool_key:
            raise LaravelToolError("Laravel agent tool key is not configured.")

        headers = {
            "Authorization": f"Bearer {self.tool_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
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
                try:
                    response = await client.post(
                        f"{self.base_url}{path}",
                        headers=headers,
                        json=json_body,
                    )
                except httpx.RequestError as exc:
                    status = "failed"
                    raise LaravelToolError(f"Laravel tool request failed: {exc.__class__.__name__}.") from exc

            if response.status_code >= 400:
                status = "failed"
                raise LaravelToolError(f"Laravel tool request failed with status {response.status_code}.")

            try:
                data = response.json()
            except ValueError as exc:
                status = "failed"
                raise LaravelToolError("Laravel tool returned an invalid JSON payload.") from exc

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

    async def _cached_get(
        self,
        cache_key: str,
        path: str,
        user_id: str,
        params: dict[str, Any] | None = None,
        trace_id: str | None = None,
        trace_metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        cached = self._cache.get(cache_key)
        if cached is not None:
            result, expiry = cached
            if time.monotonic() < expiry:
                return result
        data = await self._get(path, user_id, params=params, trace_id=trace_id, trace_metadata=trace_metadata, **kwargs)
        self._cache[cache_key] = (data, time.monotonic() + self._CACHE_TTL_SECONDS)
        return data

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
                try:
                    response = await client.get(
                        f"{self.base_url}{path}",
                        headers=headers,
                        params=params,
                    )
                except httpx.RequestError as exc:
                    status = "failed"
                    raise LaravelToolError(f"Laravel tool request failed: {exc.__class__.__name__}.") from exc

            if response.status_code >= 400:
                status = "failed"
                raise LaravelToolError(f"Laravel tool request failed with status {response.status_code}.")

            try:
                data = response.json()
            except ValueError as exc:
                status = "failed"
                raise LaravelToolError("Laravel tool returned an invalid JSON payload.") from exc

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
