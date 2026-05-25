from __future__ import annotations

import json
import logging
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langsmith.run_helpers import tracing_context

from app.config import Settings, get_settings
from app.graph import build_graph
from app.models import AgentRunRequest, AgentRunResponse
from app.observability import base_trace_metadata, summarize_usage
from app.tools.laravel import LaravelToolClient

logger = logging.getLogger("brevix.agent.api")

# Graph nodes that represent tool-calling work visible to the user.
_STREAM_TOOL_NODES: frozenset[str] = frozenset({
    "context_loader",
    "llm_tool_dispatch",
    "fraud_analyzer",
})


def _sse(event_type: str, payload: dict) -> str:
    return f"data: {json.dumps({'type': event_type, 'payload': payload})}\n\n"


def _build_initial_state(request: AgentRunRequest) -> dict:
    return {
        "agent_run_id": request.agent_run_id,
        "company_id": request.company_id,
        "user_id": request.user_id,
        "conversation_id": request.conversation_id,
        "user_message": request.message,
        "page_context": request.page_context,
        "conversation_history": request.conversation_history,
        "tool_results": {},
        "alert_recommendations": None,
        "case_recommendations": None,
        "pending_recommendations": None,
        "dashboard_health": None,
        "behavioral_baseline": None,
        "selected_tools": None,
        "findings": [],
        "investigative_synthesis": {},
        "recommended_actions": [],
        "degraded_tools": [],
        "errors": [],
        "steps": [],
        "next_best_action": None,
        "evidence_gaps": [],
        "scope_limitations": [],
        "readiness_summary": None,
        "suggested_answers": [],
        "recommended_workflow": None,
    }


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
        state = _build_initial_state(request)

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
            next_best_action=result.get("next_best_action"),
            evidence_gaps=result.get("evidence_gaps", []),
            scope_limitations=result.get("scope_limitations", []),
            readiness_summary=result.get("readiness_summary"),
            suggested_answers=result.get("suggested_answers", []),
            recommended_workflow=result.get("recommended_workflow"),
        )

    @app.post("/agent/run/stream")
    async def run_agent_stream(
        request: AgentRunRequest,
        _: None = Depends(validate_agent_auth),
    ) -> StreamingResponse:
        state = _build_initial_state(request)
        metadata = base_trace_metadata(state, settings)
        start = time.perf_counter()
        graph_config = {
            "metadata": metadata,
            "tags": ["brevix-ai", "langgraph", settings.graph_version],
            "run_name": "brevix_agent_graph",
        }

        async def generate():
            yield _sse("run.started", {
                "agent_run_id": state.get("agent_run_id"),
                "company_id": state["company_id"],
            })

            accumulated_findings: list[dict] = []
            accumulated_actions: list[dict] = []
            accumulated_steps: list[dict] = []
            accumulated_degraded: list[dict] = []
            accumulated_errors: list[str] = []
            accumulated_synthesis: dict = {}
            final_intent: str | None = None
            final_message = ""

            try:
                with tracing_context(
                    project_name=settings.langchain_project,
                    metadata=metadata,
                    tags=["brevix-ai", "agent-request", settings.graph_version],
                    enabled=settings.langsmith_enabled,
                ):
                    async for chunk in graph.astream(state, config=graph_config, stream_mode="updates"):
                        for node_name, node_output in chunk.items():
                            if not isinstance(node_output, dict):
                                continue

                            # Accumulate shared list fields before emitting events
                            accumulated_steps.extend(node_output.get("steps") or [])
                            accumulated_degraded.extend(node_output.get("degraded_tools") or [])
                            accumulated_errors.extend(node_output.get("errors") or [])

                            if node_name in _STREAM_TOOL_NODES:
                                yield _sse("tool.started", {"toolName": node_name})

                            if node_name == "router":
                                final_intent = node_output.get("intent")

                            elif node_name == "fraud_analyzer":
                                for finding in (node_output.get("findings") or []):
                                    accumulated_findings.append(finding)
                                    yield _sse("artifact.upsert", finding)

                            elif node_name == "investigation_synthesis":
                                accumulated_synthesis = node_output.get("investigative_synthesis") or {}

                            elif node_name == "explanation":
                                final_message = node_output.get("final_response") or ""
                                if final_message:
                                    yield _sse("message.delta", {"content": final_message})

                            elif node_name == "action_gate":
                                for action in (node_output.get("recommended_actions") or []):
                                    accumulated_actions.append(action)
                                    if action.get("requires_approval"):
                                        yield _sse("confirmation.requested", action)

                            if node_name in _STREAM_TOOL_NODES:
                                yield _sse("tool.completed", {
                                    "toolName": node_name,
                                    "success": True,
                                })

            except Exception as exc:
                logger.exception("Streaming agent run failed: %s", exc)
                yield _sse("run.error", {"message": "Agent run failed. No actions were taken."})
                return

            request_latency_ms = round((time.perf_counter() - start) * 1000, 2)
            usage = summarize_usage(
                {"steps": accumulated_steps},
                request_latency_ms,
                settings,
            )

            yield _sse("message.completed", {
                "agentRunId": state.get("agent_run_id"),
                "intent": final_intent,
                "message": final_message or "I could not complete the risk review right now.",
                "findings": accumulated_findings,
                "investigativeSynthesis": accumulated_synthesis,
                "recommendedActions": accumulated_actions,
                "degradedTools": accumulated_degraded,
                "errors": accumulated_errors,
                "steps": accumulated_steps,
                "modelProvider": settings.model_provider,
                "modelName": settings.model_name,
                "usage": usage,
            })

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
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
