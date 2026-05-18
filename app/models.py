from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator, model_validator


class AgentFinding(BaseModel):
    title: str
    severity: Literal["info", "low", "medium", "high", "critical"] = "info"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    type: str
    label: str
    requires_approval: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentRunRequest(BaseModel):
    agent_run_id: str | None = None
    company_id: str
    user_id: str
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    page_context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_content_message(cls, value: Any) -> Any:
        if isinstance(value, dict) and "message" not in value and "content" in value:
            return {**value, "message": value["content"]}
        return value

    @field_validator("agent_run_id", "company_id", "user_id", "conversation_id", mode="before")
    @classmethod
    def coerce_numeric_ids(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return str(value)
        return value

    @field_validator("page_context", mode="before")
    @classmethod
    def default_page_context(cls, value: Any) -> Any:
        return {} if value is None or value == [] else value


class AgentStep(BaseModel):
    step_name: str
    step_type: str = "graph_node"
    input_payload: dict[str, Any] | None = None
    output_payload: dict[str, Any] | None = None
    status: str = "completed"
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None


class AgentRunResponse(BaseModel):
    trace_id: str | None = None
    intent: str | None = None
    message: str
    findings: list[AgentFinding] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    steps: list[AgentStep] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    model_provider: str | None = None
    model_name: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)


class BrevixAgentState(TypedDict, total=False):
    agent_run_id: str | None
    company_id: str
    user_id: str
    conversation_id: str | None
    user_message: str
    page_context: dict[str, Any]
    intent: str | None
    company_context: dict[str, Any]
    tool_results: dict[str, Any]
    findings: list[dict[str, Any]]
    recommended_actions: list[dict[str, Any]]
    final_response: str | None
    errors: list[str]
    steps: Annotated[list[dict[str, Any]], add]
    usage: dict[str, Any]
