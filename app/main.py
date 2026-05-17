from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status

from app.config import Settings, get_settings
from app.graph import build_graph
from app.models import AgentRunRequest, AgentRunResponse
from app.tools.laravel import LaravelToolClient


def create_app() -> FastAPI:
    settings = get_settings()
    tool_client = LaravelToolClient(
        base_url=settings.laravel_base_url,
        tool_key=settings.laravel_agent_tool_key,
        timeout_seconds=settings.http_timeout_seconds,
    )
    graph = build_graph(tool_client)

    app = FastAPI(
        title="Brevix AI Agent Service",
        version="0.1.0",
        description="Phase 1 LangGraph orchestration service for deterministic Brevix Laravel tools.",
    )

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
            "recommended_actions": [],
            "errors": [],
            "steps": [],
        }

        result = await graph.ainvoke(state)

        return AgentRunResponse(
            intent=result.get("intent"),
            message=result.get("final_response") or "I could not complete the risk review right now.",
            findings=result.get("findings", []),
            recommended_actions=result.get("recommended_actions", []),
            steps=result.get("steps", []),
            errors=result.get("errors", []),
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
