from __future__ import annotations

import logging
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from langsmith.run_helpers import tracing_context

from app.config import Settings, get_settings
from app.graph import build_graph
from app.models import AgentRunRequest, AgentRunResponse
from app.observability import base_trace_metadata, summarize_usage
from app.tools.laravel import LaravelToolClient

logger = logging.getLogger("brevix.agent.api")


def _cors_origins(settings: Settings) -> list[str]:
    """Return the allowed CORS origins for the given settings.

    In production (APP_ENV=production|prod), raises RuntimeError when
    ORCHESTRATOR_ALLOWED_ORIGINS is not explicitly set — wildcard CORS is
    never permitted in production.  In all other environments, falls back
    to ["*"] so local development works without configuration.
    """
    if settings.allowed_origins_list:
        return settings.allowed_origins_list
    if settings.is_production:
        raise RuntimeError(
            "ORCHESTRATOR_ALLOWED_ORIGINS must be explicitly set in production. "
            "Refusing to start with a wildcard CORS policy."
        )
    return ["*"]


def _validate_startup_config(settings: Settings) -> None:
    """Fail fast on production settings that would make Rex chat unusable."""
    if not settings.is_production:
        return

    missing = []
    if not settings.agent_service_key:
        missing.append("BREVIX_AGENT_SERVICE_KEY or ORCHESTRATOR_API_TOKEN")
    if not settings.laravel_agent_tool_key:
        missing.append("BREVIX_LARAVEL_AGENT_TOOL_KEY")

    if missing:
        raise RuntimeError(
            f"Missing required production configuration: {', '.join(missing)}."
        )


def create_app() -> FastAPI:
    settings = get_settings()
    _validate_startup_config(settings)

    tool_client = LaravelToolClient(
        base_url=settings.laravel_base_url,
        tool_key=settings.laravel_agent_tool_key,
        timeout_seconds=settings.http_timeout_seconds,
    )
    graph = build_graph(tool_client, settings=settings)

    app = FastAPI(
        title="Brevix AI Agent Service",
        version="0.1.0",
        description="Phase 1 LangGraph orchestration service for deterministic Brevix Laravel tools.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        body_keys: list[str] = []
        try:
            body = await request.json()
            if isinstance(body, dict):
                body_keys = sorted(str(key) for key in body.keys())
        except Exception:
            body_keys = []

        errors = [
            {
                "loc": error.get("loc"),
                "type": error.get("type"),
                "msg": error.get("msg"),
            }
            for error in exc.errors()
        ]
        logger.warning(
            "agent.request.validation_failed path=%s method=%s body_keys=%s errors=%s",
            request.url.path,
            request.method,
            body_keys,
            errors,
            extra={"path": request.url.path, "method": request.method, "body_keys": body_keys, "errors": errors},
        )
        return await request_validation_exception_handler(request, exc)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/agent/run", response_model=AgentRunResponse)
    async def run_agent(
        request: AgentRunRequest,
        _: None = Depends(validate_agent_auth),
    ) -> AgentRunResponse:
        state = {
            "agent_run_id": request.agent_run_id,
            "company_id": request.company_id,
            "user_id": request.user_id,
            "conversation_id": request.conversation_id,
            "user_message": request.message,
            "page_context": request.page_context,
            "tool_results": {},
            "findings": [],
            "investigative_synthesis": {},
            "recommended_actions": [],
            "degraded_tools": [],
            "errors": [],
            "steps": [],
        }

        metadata = base_trace_metadata(state, settings)
        start = time.perf_counter()
        with tracing_context(
            project_name=settings.langchain_project,
            metadata=metadata,
            tags=["brevix-ai", "agent-request", settings.graph_version],
            enabled=settings.langsmith_enabled,
        ):
            result = await graph.ainvoke(
                state,
                config={
                    "metadata": metadata,
                    "tags": ["brevix-ai", "langgraph", settings.graph_version],
                    "run_name": "brevix_agent_graph",
                },
            )
        request_latency_ms = round((time.perf_counter() - start) * 1000, 2)
        usage = summarize_usage(result, request_latency_ms, settings)

        return AgentRunResponse(
            trace_id=request.agent_run_id,
            intent=result.get("intent"),
            message=result.get("final_response") or "I could not complete the risk review right now.",
            findings=result.get("findings", []),
            investigative_synthesis=result.get("investigative_synthesis", {}),
            recommended_actions=result.get("recommended_actions", []),
            steps=result.get("steps", []),
            degraded_tools=result.get("degraded_tools", []),
            errors=result.get("errors", []),
            model_provider=settings.model_provider,
            model_name=settings.model_name,
            usage=usage,
        )

    return app


async def validate_agent_auth(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.agent_service_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent service authentication is not configured.",
        )

    expected = f"Bearer {settings.agent_service_key}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


app = create_app()
