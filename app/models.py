from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator, model_validator


def _extract_message_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and item.get("type") in {None, "text", "input_text", "output_text"}:
                    parts.append(text)
        text = "\n".join(part.strip() for part in parts if part.strip())
        return text or None

    return None


def _extract_message_from_messages(messages: Any) -> str | None:
    if not isinstance(messages, list):
        return None

    fallback: str | None = None
    user_message: str | None = None
    for message in messages:
        if not isinstance(message, dict):
            continue

        text = _extract_message_text(message.get("content"))
        if not text:
            continue

        fallback = text
        if message.get("role") == "user":
            user_message = text

    return user_message or fallback


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


class DegradedTool(BaseModel):
    tool: str
    error_class: str
    message: str
    affected_confidence: bool = True


class InvestigationSynthesis(BaseModel):
    investigative_summary: str = ""
    correlated_findings: list[dict[str, Any]] = Field(default_factory=list)
    reinforcing_signals: list[dict[str, Any]] = Field(default_factory=list)
    conflicting_signals: list[dict[str, Any]] = Field(default_factory=list)
    investigation_priority: Literal["low", "medium", "high", "critical"] = "low"
    recommended_investigation_focus: list[str] = Field(default_factory=list)
    supporting_domains: list[str] = Field(default_factory=list)
    evidence_summary: list[dict[str, Any]] = Field(default_factory=list)


class AgentRunRequest(BaseModel):
    agent_run_id: str | None = None
    company_id: str
    user_id: str
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    page_context: dict[str, Any] = Field(default_factory=dict)
    conversation_history: list[dict[str, Any]] | None = None

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_content_message(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "message" in value:
            return value

        for key in ("content", "input"):
            extracted = _extract_message_text(value.get(key)) or _extract_message_from_messages(value.get(key))
            if extracted is not None:
                return {**value, "message": extracted}

        extracted = _extract_message_from_messages(value.get("messages"))
        if extracted is not None:
            return {**value, "message": extracted}

        return value

    @field_validator("message", mode="after")
    @classmethod
    def strip_and_require_message_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must contain non-whitespace text")
        return stripped

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
    investigative_synthesis: InvestigationSynthesis = Field(default_factory=InvestigationSynthesis)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    steps: list[AgentStep] = Field(default_factory=list)
    degraded_tools: list[DegradedTool] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    model_provider: str | None = None
    model_name: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    next_best_action: dict[str, Any] | None = None
    evidence_gaps: list[dict[str, Any]] = Field(default_factory=list)
    scope_limitations: list[str] = Field(default_factory=list)
    readiness_summary: dict[str, Any] | None = None
    suggested_answers: list[dict[str, Any]] = Field(default_factory=list)
    recommended_workflow: str | None = None


class BrevixAgentState(TypedDict, total=False):
    agent_run_id: str | None
    company_id: str
    user_id: str
    conversation_id: str | None
    user_message: str
    page_context: dict[str, Any]
    conversation_history: list[dict[str, Any]] | None
    intent: str | None
    company_context: dict[str, Any]
    tool_results: dict[str, Any]
    alert_recommendations: dict[str, Any] | None
    case_recommendations: dict[str, Any] | None
    pending_recommendations: dict[str, Any] | None
    dashboard_health: dict[str, Any] | None
    behavioral_baseline: dict[str, Any] | None
    selected_tools: list[str] | None
    findings: list[dict[str, Any]]
    investigative_synthesis: dict[str, Any]
    recommended_actions: list[dict[str, Any]]
    final_response: str | None
    irs_answer: str | None
    degraded_tools: Annotated[list[dict[str, Any]], add]
    errors: list[str]
    steps: Annotated[list[dict[str, Any]], add]
    usage: dict[str, Any]
    next_best_action: dict[str, Any] | None
    evidence_gaps: list[dict[str, Any]]
    scope_limitations: list[str]
    readiness_summary: dict[str, Any] | None
    suggested_answers: list[dict[str, Any]]
    recommended_workflow: str | None
