from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.config import Settings, get_settings
from app.models import AgentFinding, BrevixAgentState, RecommendedAction
from app.observability import instrument_node
from app.providers import ModelProvider, get_provider
from app.tools.laravel import LaravelToolClient, LaravelToolError

SENSITIVE_ACTION_TYPES = {
    "create_alert",
    "create_case",
    "escalate_review",
    "mark_alert_resolved",
    "suppress_alerts",
    "send_report",
}


def build_graph(
    tool_client: LaravelToolClient,
    settings: Settings | None = None,
    provider: ModelProvider | None = None,
):
    resolved_settings = settings or get_settings()
    resolved_provider = provider or get_provider(resolved_settings)

    async def router_node(state: BrevixAgentState) -> dict[str, Any]:
        message = state["user_message"].lower()
        intent = "unknown_or_unsupported"

        if any(
            term in message
            for term in (
                "fraud", "suspicious", "vendor", "risk", "alert", "anomaly",
                "payment", "invoice", "duplicate", "threshold", "split", "concentration",
            )
        ):
            intent = "fraud_pattern_search"
        elif any(term in message for term in ("reconciliation", "unmatched", "mismatch")):
            intent = "reconciliation_review"

        return {
            "intent": intent,
            "steps": [
                step(
                    "router",
                    input_payload={"message": state["user_message"]},
                    output_payload={"intent": intent},
                )
            ],
        }

    async def context_loader_node(state: BrevixAgentState) -> dict[str, Any]:
        try:
            context = await tool_client.company_context(
                state["company_id"],
                state["user_id"],
                trace_id=state.get("agent_run_id"),
                trace_metadata={
                    "intent": state.get("intent"),
                    "request_source": state.get("page_context", {}).get("source"),
                },
            )
            return {
                "company_context": context,
                "steps": [
                    step(
                        "context_loader",
                        step_type="tool_call",
                        input_payload={"tool": "company_context", "company_id": state["company_id"]},
                        output_payload=minimized_context(context),
                    )
                ],
            }
        except LaravelToolError as exc:
            return {
                "errors": [str(exc)],
                "steps": [
                    step(
                        "context_loader",
                        step_type="tool_call",
                        status="failed",
                        input_payload={"tool": "company_context", "company_id": state["company_id"]},
                        error_message=str(exc),
                    )
                ],
            }

    async def fraud_analyzer_node(state: BrevixAgentState) -> dict[str, Any]:
        if state.get("intent") not in {"fraud_pattern_search", "reconciliation_review"}:
            return {
                "findings": [],
                "steps": [
                    step(
                        "fraud_analyzer",
                        output_payload={"skipped": True, "reason": "unsupported_intent"},
                    )
                ],
            }

        period = selected_period(state.get("page_context", {}))

        try:
            risk_summary = await tool_client.risk_summary(
                state["company_id"],
                state["user_id"],
                period=period,
                trace_id=state.get("agent_run_id"),
                trace_metadata={
                    "intent": state.get("intent"),
                    "request_source": state.get("page_context", {}).get("source"),
                    "fraud_scenario_id": state.get("page_context", {}).get("fraud_scenario_id"),
                },
            )
        except LaravelToolError as exc:
            return {
                "errors": [str(exc)],
                "findings": [],
                "steps": [
                    step(
                        "fraud_analyzer",
                        step_type="tool_call",
                        status="failed",
                        input_payload={"tool": "risk_summary", "period": period},
                        error_message=str(exc),
                    )
                ],
            }

        findings = findings_from_risk_summary(risk_summary)

        return {
            "tool_results": {"risk_summary": risk_summary},
            "findings": [finding.model_dump() for finding in findings],
            "steps": [
                step(
                    "fraud_analyzer",
                    step_type="tool_call",
                    input_payload={"tool": "risk_summary", "period": period},
                    output_payload={
                        "risk_score": risk_summary.get("risk_score"),
                        "risk_level": risk_summary.get("risk_level"),
                        "finding_count": len(findings),
                    },
                )
            ],
        }

    async def explanation_node(state: BrevixAgentState) -> dict[str, Any]:
        context = _build_context(state)
        prompt = _build_prompt(context)
        provider_response = await resolved_provider.generate(prompt, context)

        return {
            "final_response": provider_response.text,
            "steps": [
                step(
                    "explanation",
                    output_payload={
                        "message": provider_response.text,
                        "finding_count": len(state.get("findings", [])),
                        "provider_name": provider_response.provider_name,
                        "model_name": provider_response.model_name,
                        "provider_latency_ms": provider_response.latency_ms,
                        "tokens_input": provider_response.tokens_input,
                        "tokens_output": provider_response.tokens_output,
                    },
                )
            ],
        }

    async def action_gate_node(state: BrevixAgentState) -> dict[str, Any]:
        actions = suggested_actions(state)
        gated = []

        for action in actions:
            if action.type in SENSITIVE_ACTION_TYPES:
                action.requires_approval = True
            gated.append(action.model_dump())

        return {
            "recommended_actions": gated,
            "steps": [
                step(
                    "action_gate",
                    output_payload={
                        "action_count": len(gated),
                        "executed_actions": 0,
                        "autonomous_actions_enabled": False,
                    },
                )
            ],
        }

    async def final_response_node(state: BrevixAgentState) -> dict[str, Any]:
        return {
            "steps": [
                step(
                    "final_response",
                    output_payload={
                        "intent": state.get("intent"),
                        "finding_count": len(state.get("findings", [])),
                        "action_count": len(state.get("recommended_actions", [])),
                    },
                )
            ],
        }

    builder = StateGraph(BrevixAgentState)
    builder.add_node("router", instrument_node("router", router_node, resolved_settings))
    builder.add_node("context_loader", instrument_node("context_loader", context_loader_node, resolved_settings))
    builder.add_node("fraud_analyzer", instrument_node("fraud_analyzer", fraud_analyzer_node, resolved_settings))
    builder.add_node("explanation", instrument_node("explanation", explanation_node, resolved_settings))
    builder.add_node("action_gate", instrument_node("action_gate", action_gate_node, resolved_settings))
    builder.add_node("final_response", instrument_node("final_response", final_response_node, resolved_settings))
    builder.add_edge(START, "router")
    builder.add_edge("router", "context_loader")
    builder.add_edge("context_loader", "fraud_analyzer")
    builder.add_edge("fraud_analyzer", "explanation")
    builder.add_edge("explanation", "action_gate")
    builder.add_edge("action_gate", "final_response")
    builder.add_edge("final_response", END)

    return builder.compile()


def step(
    step_name: str,
    step_type: str = "graph_node",
    input_payload: dict[str, Any] | None = None,
    output_payload: dict[str, Any] | None = None,
    status: str = "completed",
    error_message: str | None = None,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "step_name": step_name,
        "step_type": step_type,
        "input_payload": input_payload,
        "output_payload": output_payload,
        "status": status,
        "started_at": timestamp,
        "completed_at": timestamp if status == "completed" else None,
        "error_message": error_message,
    }


def selected_period(page_context: dict[str, Any]) -> str | None:
    period = page_context.get("selected_period") or page_context.get("period")
    return str(period) if period else None


def minimized_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_id": context.get("company_id"),
        "industry": context.get("industry"),
        "available_data_sources": context.get("available_data_sources", []),
        "user_role": context.get("user_role"),
    }


def findings_from_risk_summary(risk_summary: dict[str, Any]) -> list[AgentFinding]:
    findings: list[AgentFinding] = []

    for driver in risk_summary.get("top_drivers", []):
        findings.append(
            AgentFinding(
                title=str(driver.get("driver") or "Risk pattern worth reviewing"),
                severity=normalize_severity(str(driver.get("severity") or risk_summary.get("risk_level") or "info")),
                confidence=confidence_from_risk_score(int(risk_summary.get("risk_score") or 0)),
                summary=str(driver.get("description") or "A deterministic Brevix risk service returned this driver."),
                evidence=driver.get("evidence") if isinstance(driver.get("evidence"), list) else [],
            )
        )

    return findings


def normalize_severity(severity: str) -> str:
    mapping = {
        "warning": "medium",
        "moderate": "medium",
    }
    normalized = mapping.get(severity.lower(), severity.lower())
    return normalized if normalized in {"info", "low", "medium", "high", "critical"} else "info"


def confidence_from_risk_score(score: int) -> float:
    if score >= 90:
        return 0.9
    if score >= 70:
        return 0.8
    if score >= 40:
        return 0.65
    if score > 0:
        return 0.45
    return 0.0


def _build_context(state: BrevixAgentState) -> dict[str, Any]:
    risk_summary = state.get("tool_results", {}).get("risk_summary", {})
    return {
        "intent": state.get("intent"),
        "errors": state.get("errors", []),
        "findings": state.get("findings", []),
        "risk_score": risk_summary.get("risk_score", 0),
        "risk_level": risk_summary.get("risk_level", "low"),
    }


def _build_prompt(context: dict[str, Any]) -> str:
    findings_text = (
        "\n".join(
            f"- {f.get('title')} (severity: {f.get('severity', 'unknown')})"
            for f in context.get("findings", [])
        )
        or "No specific findings returned."
    )
    return (
        "You are a financial risk analysis assistant for Brevix. Summarize the following "
        "risk analysis results for an accounting team in 2-4 concise sentences.\n\n"
        f"Intent: {context.get('intent')}\n"
        f"Risk score: {context.get('risk_score', 0)}/100 ({context.get('risk_level', 'low')})\n"
        f"Findings:\n{findings_text}\n\n"
        "Guidelines:\n"
        "- Use 'may indicate' language; never accuse of fraud\n"
        "- Be factual and professional\n"
        "- End with: No alerts or cases were created."
    )


def suggested_actions(state: BrevixAgentState) -> list[RecommendedAction]:
    if state.get("errors") or state.get("intent") == "unknown_or_unsupported":
        return []

    findings = state.get("findings", [])
    if not findings:
        return [
            RecommendedAction(
                type="review_dashboard",
                label="Review dashboard",
                requires_approval=False,
                payload={"reason": "No specific findings returned"},
            )
        ]

    return [
        RecommendedAction(
            type="review_findings",
            label="Review findings",
            requires_approval=False,
            payload={"finding_count": len(findings)},
        )
    ]
