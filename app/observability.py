from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from langsmith import traceable

from app.config import Settings, get_settings
from app.models import BrevixAgentState

logger = logging.getLogger("brevix.agent.observability")


NodeFn = Callable[[BrevixAgentState], Awaitable[dict[str, Any]]]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def request_source_from_state(state: BrevixAgentState) -> str:
    page_context = state.get("page_context", {})
    source = page_context.get("source") or page_context.get("request_source") or "api"
    return str(source)


def fraud_scenario_id_from_state(state: BrevixAgentState) -> str | None:
    page_context = state.get("page_context", {})
    scenario_id = (
        page_context.get("fraud_scenario_id")
        or page_context.get("seeded_scenario_id")
        or page_context.get("scenario_id")
    )
    return str(scenario_id) if scenario_id else None


def base_trace_metadata(
    state: BrevixAgentState,
    settings: Settings | None = None,
    node_name: str | None = None,
    intent: str | None = None,
) -> dict[str, Any]:
    resolved_settings = settings or get_settings()
    metadata: dict[str, Any] = {
        "trace_id": state.get("agent_run_id") or state.get("conversation_id"),
        "user_id": state.get("user_id"),
        "company_id": state.get("company_id"),
        "intent": intent or state.get("intent"),
        "node_name": node_name,
        "environment": resolved_settings.app_env,
        "graph_version": resolved_settings.graph_version,
        "request_source": request_source_from_state(state),
        "feature_flags": resolved_settings.feature_flag_list,
        "fraud_scenario_id": fraud_scenario_id_from_state(state),
        "model_provider": resolved_settings.model_provider,
        "model_name": resolved_settings.model_name,
    }
    return {key: value for key, value in metadata.items() if value is not None}


def sanitize_node_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    state = inputs.get("state") or {}
    message = str(state.get("user_message") or "")
    return {
        "trace_id": state.get("agent_run_id") or state.get("conversation_id"),
        "company_id": state.get("company_id"),
        "user_id": state.get("user_id"),
        "intent": state.get("intent"),
        "message_length": len(message),
        "message_hash": stable_hash(message) if message else None,
        "page_context_keys": sorted((state.get("page_context") or {}).keys()),
    }


def sanitize_node_outputs(outputs: dict[str, Any]) -> dict[str, Any]:
    steps = (outputs.get("steps") or []) if isinstance(outputs, dict) else []
    return {
        "intent": outputs.get("intent") if isinstance(outputs, dict) else None,
        "finding_count": len(outputs.get("findings", [])) if isinstance(outputs, dict) else 0,
        "recommended_action_count": len(outputs.get("recommended_actions", [])) if isinstance(outputs, dict) else 0,
        "error_count": len(outputs.get("errors", [])) if isinstance(outputs, dict) else 0,
        "steps": [
            {
                "step_name": step.get("step_name"),
                "step_type": step.get("step_type"),
                "status": step.get("status"),
                "metrics": (step.get("output_payload") or {}).get("metrics"),
            }
            for step in steps
            if isinstance(step, dict)
        ],
    }


def sanitize_tool_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    params = inputs.get("params") or {}
    return {
        "path": inputs.get("path"),
        "user_id": inputs.get("user_id"),
        "trace_id": inputs.get("trace_id"),
        "param_keys": sorted(params.keys()) if isinstance(params, dict) else [],
    }


def sanitize_tool_outputs(outputs: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(outputs, dict):
        return {"payload_type": type(outputs).__name__}

    transaction_summary = outputs.get("transaction_summary")
    dashboard_summary = outputs.get("dashboard_summary")

    return {
        "payload_keys": sorted(outputs.keys()),
        "risk_score": outputs.get("risk_score"),
        "risk_level": outputs.get("risk_level"),
        "top_driver_count": len(outputs.get("top_drivers", [])) if isinstance(outputs.get("top_drivers"), list) else None,
        "transaction_total": transaction_summary.get("total") if isinstance(transaction_summary, dict) else None,
        "transaction_returned_count": transaction_summary.get("returned_count") if isinstance(transaction_summary, dict) else None,
        "dashboard_risk_score": dashboard_summary.get("risk_score") if isinstance(dashboard_summary, dict) else None,
    }


def enrich_steps_with_metrics(
    result: dict[str, Any],
    node_name: str,
    started_at: str,
    completed_at: str,
    latency_ms: float,
    settings: Settings,
) -> dict[str, Any]:
    steps = result.get("steps")
    if not isinstance(steps, list):
        return result

    for step in steps:
        if not isinstance(step, dict) or step.get("step_name") != node_name:
            continue

        step["started_at"] = started_at
        step["completed_at"] = completed_at if step.get("status") == "completed" else None
        output_payload = step.get("output_payload")
        if not isinstance(output_payload, dict):
            output_payload = {}

        tokens_in = int(output_payload.get("tokens_input", 0))
        tokens_out = int(output_payload.get("tokens_output", 0))
        metrics = {
            "latency_ms": latency_ms,
            "provider_name": output_payload.get("provider_name", settings.model_provider),
            "model_name": output_payload.get("model_name", settings.model_name),
            "provider_latency_ms": output_payload.get("provider_latency_ms", 0.0),
            "token_usage": {"input": tokens_in, "output": tokens_out, "total": tokens_in + tokens_out},
            "estimated_cost_usd": 0.0,
        }
        step["output_payload"] = {
            **output_payload,
            "metrics": metrics,
        }

    return result


def instrument_node(node_name: str, node_fn: NodeFn, settings: Settings | None = None) -> NodeFn:
    resolved_settings = settings or get_settings()

    @traceable(
        name=f"agent.node.{node_name}",
        run_type="chain",
        project_name=resolved_settings.langchain_project,
        process_inputs=sanitize_node_inputs,
        process_outputs=sanitize_node_outputs,
    )
    async def run_observed_node(state: BrevixAgentState, **_: Any) -> dict[str, Any]:
        started_at = utc_now_iso()
        start = time.perf_counter()
        status = "completed"

        try:
            result = await node_fn(state)
            return enrich_steps_with_metrics(
                result=result,
                node_name=node_name,
                started_at=started_at,
                completed_at=utc_now_iso(),
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
                settings=resolved_settings,
            )
        except Exception:
            status = "failed"
            raise
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            metadata = base_trace_metadata(state, resolved_settings, node_name=node_name)
            log_payload = {
                **metadata,
                "latency_ms": latency_ms,
                "status": status,
            }
            logger.info("agent_node_timing %s", json.dumps(log_payload, sort_keys=True))

    async def wrapper(state: BrevixAgentState) -> dict[str, Any]:
        metadata = base_trace_metadata(state, resolved_settings, node_name=node_name)
        return await run_observed_node(
            state,
            langsmith_extra={
                "metadata": metadata,
                "tags": ["brevix-ai", "agent-node", node_name],
            },
        )

    return wrapper


def summarize_usage(result: dict[str, Any], request_latency_ms: float, settings: Settings) -> dict[str, Any]:
    steps = result.get("steps", [])
    node_latencies: dict[str, float] = {}
    tool_call_count = 0
    failed_tool_call_count = 0

    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue

        if step.get("step_type") == "tool_call":
            tool_call_count += 1
            if step.get("status") == "failed":
                failed_tool_call_count += 1

        metrics = (step.get("output_payload") or {}).get("metrics") if isinstance(step.get("output_payload"), dict) else None
        if isinstance(metrics, dict) and isinstance(metrics.get("latency_ms"), (int, float)):
            node_latencies[str(step.get("step_name"))] = float(metrics["latency_ms"])

    tokens_input = 0
    tokens_output = 0
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue
        token_usage = (
            (step.get("output_payload") or {})
            .get("metrics", {})
            .get("token_usage", {})
        )
        if isinstance(token_usage, dict):
            tokens_input += int(token_usage.get("input", 0))
            tokens_output += int(token_usage.get("output", 0))

    return {
        "request_latency_ms": request_latency_ms,
        "node_latency_ms": node_latencies,
        "tool_call_count": tool_call_count,
        "failed_tool_call_count": failed_tool_call_count,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "tokens_total": tokens_input + tokens_output,
        "estimated_cost_usd": 0.0,
        "model_provider": settings.model_provider,
        "model_name": settings.model_name,
    }
