from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.config import Settings, get_settings
from app.investigation_synthesis import synthesize_investigation
from app.models import AgentFinding, BrevixAgentState, RecommendedAction
from app.observability import instrument_node
from app.prompts import load_prompt
from app.providers import ModelProvider, get_provider
from app.tools.laravel import LaravelToolClient, LaravelToolError

logger = logging.getLogger("brevix.agent.graph")

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

    # Load prompt templates once at graph-build time — fail early if any are missing.
    _router_prompt = load_prompt("router", "v1")
    _fraud_analyzer_prompt = load_prompt("fraud_analyzer_summary", "v1")
    _investigation_synthesis_prompt = load_prompt("investigation_synthesis", "v1")
    _explanation_prompt = load_prompt("explanation", "v1")
    _action_gate_prompt = load_prompt("action_gate", "v1")

    async def router_node(state: BrevixAgentState) -> dict[str, Any]:
        message = state["user_message"].lower()
        intent = "unknown_or_unsupported"

        if any(term in message for term in ("financial health", "overview", "dashboard", "current health")):
            intent = "dashboard_health"
        elif any(term in message for term in ("reconciliation", "unmatched", "mismatch")):
            intent = "reconciliation_review"
        elif is_transaction_lookup(message):
            intent = "transaction_lookup"
        elif any(
            term in message
            for term in (
                "fraud", "suspicious", "vendor", "risk", "alert", "anomaly",
                "payment", "invoice", "duplicate", "threshold", "split", "concentration",
            )
        ):
            intent = "fraud_pattern_search"

        return {
            "intent": intent,
            "steps": [
                step(
                    "router",
                    input_payload={"message": state["user_message"]},
                    output_payload={"intent": intent, **_router_prompt.metadata},
                )
            ],
        }

    async def context_loader_node(state: BrevixAgentState) -> dict[str, Any]:
        transaction_filters = (
            transaction_filters_from_message(state["user_message"])
            if state.get("intent") == "transaction_lookup"
            else None
        )
        dashboard_context = state.get("intent") == "dashboard_health"

        try:
            context = await tool_client.company_context(
                state["company_id"],
                state["user_id"],
                dashboard_context=dashboard_context,
                transaction_filters=transaction_filters,
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
        if state.get("intent") == "dashboard_health":
            findings = dashboard_findings_from_context(state.get("company_context", {}))
            return {
                "findings": [finding.model_dump() for finding in findings],
                "steps": [
                    step(
                        "fraud_analyzer",
                        output_payload={
                            "skipped": True,
                            "reason": "dashboard_health_intent",
                            "finding_count": len(findings),
                        },
                    )
                ],
            }

        if state.get("intent") == "transaction_lookup":
            findings = transaction_findings_from_context(state.get("company_context", {}))
            return {
                "findings": [finding.model_dump() for finding in findings],
                "steps": [
                    step(
                        "fraud_analyzer",
                        output_payload={
                            "skipped": True,
                            "reason": "transaction_lookup_intent",
                            "finding_count": len(findings),
                        },
                    )
                ],
            }

        if state.get("intent") not in {"fraud_pattern_search", "reconciliation_review"}:
            return {
                "findings": [],
                "steps": [
                    step(
                        "fraud_analyzer",
                        output_payload={"skipped": True, "reason": f"{state.get('intent')}_intent"},
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

        # Determine if a specific vendor was queried or mentioned
        vendor_findings = []
        vendor_risk_data = None
        vendor_name_query = state.get("page_context", {}).get("vendor_name") or state.get("page_context", {}).get("vendor")
        
        if not vendor_name_query:
            msg = state["user_message"].lower()
            for seeded_vendor in ["mega vendor", "northstar consulting", "roundhouse services", "acme supplies", "brightline labs", "clean vendor"]:
                if seeded_vendor in msg:
                    casing_map = {
                        "mega vendor": "Mega Vendor LLC",
                        "northstar consulting": "Northstar Consulting",
                        "roundhouse services": "Roundhouse Services",
                        "acme supplies": "Acme Supplies",
                        "brightline labs": "Brightline Labs",
                        "clean vendor": "Clean Vendor"
                    }
                    vendor_name_query = casing_map[seeded_vendor]
                    break

        try:
            vendor_risk_data = await tool_client.vendor_risk(
                state["company_id"],
                state["user_id"],
                vendor=vendor_name_query,
                trace_id=state.get("agent_run_id"),
                trace_metadata={
                    "intent": state.get("intent"),
                    "request_source": state.get("page_context", {}).get("source"),
                }
            )
        except Exception as exc:
            logger.warning("Failed to retrieve vendor risk: %s", exc)

        if vendor_risk_data:
            if "vendors" in vendor_risk_data:
                for v in vendor_risk_data["vendors"]:
                    if v.get("vendor_risk_score", 0) >= 40:
                        vendor_findings.append(
                            AgentFinding(
                                title=f"High Vendor Concentration/Risk: {v.get('vendor_name')}",
                                severity=normalize_severity(v.get('risk_level', 'medium')),
                                confidence=confidence_from_risk_score(v.get('vendor_risk_score', 0)),
                                summary=f"Deterministic vendor risk score is {v.get('vendor_risk_score')}/100. Recommended action: {v.get('recommended_next_action')}",
                                evidence=[
                                    {
                                        "type": "vendor_risk_analysis",
                                        "vendor_name": v.get("vendor_name"),
                                        "triggered_rules": v.get("triggered_rules"),
                                        "supporting_evidence": v.get("supporting_evidence")
                                    }
                                ]
                            )
                        )
            else:
                v = vendor_risk_data
                vendor_findings.append(
                    AgentFinding(
                        title=f"Vendor Risk Audit: {v.get('vendor_name')}",
                        severity=normalize_severity(v.get('risk_level', 'low')),
                        confidence=confidence_from_risk_score(v.get('vendor_risk_score', 0)),
                        summary=f"Vendor '{v.get('vendor_name')}' deterministic risk score is {v.get('vendor_risk_score')}/100. Action guidance: {v.get('recommended_next_action')}",
                        evidence=[
                            {
                                "type": "vendor_risk_analysis",
                                "vendor_name": v.get("vendor_name"),
                                "triggered_rules": v.get("triggered_rules"),
                                "supporting_evidence": v.get("supporting_evidence")
                            }
                        ]
                    )
                )

        # Retrieve reconciliation risk data
        reconciliation_risk_data = None
        recon_findings = []
        try:
            reconciliation_risk_data = await tool_client.reconciliation_risk(
                state["company_id"],
                state["user_id"],
                trace_id=state.get("agent_run_id"),
                trace_metadata={
                    "intent": state.get("intent"),
                    "request_source": state.get("page_context", {}).get("source"),
                }
            )
        except Exception as exc:
            logger.warning("Failed to retrieve reconciliation risk: %s", exc)

        if reconciliation_risk_data:
            recon_score = reconciliation_risk_data.get("reconciliation_risk_score", 0)
            if recon_score >= 40:
                recon_findings.append(
                    AgentFinding(
                        title="High Reconciliation Anomaly Risk",
                        severity=normalize_severity(reconciliation_risk_data.get('risk_level', 'medium')),
                        confidence=confidence_from_risk_score(recon_score),
                        summary=f"Deterministic reconciliation risk score is {recon_score}/100. Action guidance: {reconciliation_risk_data.get('recommended_next_action')}",
                        evidence=[
                            {
                                "type": "reconciliation_risk_analysis",
                                "score": recon_score,
                                "triggered_rules": reconciliation_risk_data.get("triggered_rules"),
                                "supporting_evidence": reconciliation_risk_data.get("supporting_evidence")
                            }
                        ]
                    )
                )

        # Retrieve entity relationship risk data
        entity_relationship_risk_data = None
        entity_findings = []
        try:
            entity_relationship_risk_data = await tool_client.entity_relationship_risk(
                state["company_id"],
                state["user_id"],
                trace_id=state.get("agent_run_id"),
                trace_metadata={
                    "intent": state.get("intent"),
                    "request_source": state.get("page_context", {}).get("source"),
                }
            )
        except Exception as exc:
            logger.warning("Failed to retrieve entity relationship risk: %s", exc)

        if entity_relationship_risk_data:
            entity_score = entity_relationship_risk_data.get("entity_relationship_risk_score", 0)
            if entity_score >= 40:
                entity_findings.append(
                    AgentFinding(
                        title="High Entity Relationship Risk",
                        severity=normalize_severity(entity_relationship_risk_data.get('risk_level', 'medium')),
                        confidence=confidence_from_risk_score(entity_score),
                        summary=f"Deterministic entity relationship risk score is {entity_score}/100. Action guidance: {entity_relationship_risk_data.get('recommended_next_action')}",
                        evidence=[
                            {
                                "type": "entity_relationship_risk_analysis",
                                "score": entity_score,
                                "triggered_rules": entity_relationship_risk_data.get("triggered_rules"),
                                "supporting_evidence": entity_relationship_risk_data.get("supporting_evidence"),
                                "related_entities": entity_relationship_risk_data.get("related_entities")
                            }
                        ]
                    )
                )

        # Retrieve aggregate risk summary
        aggregate_risk_data = None
        try:
            aggregate_risk_data = await tool_client.aggregate_risk_summary(
                state["company_id"],
                state["user_id"],
                trace_id=state.get("agent_run_id"),
                trace_metadata={
                    "intent": state.get("intent"),
                    "request_source": state.get("page_context", {}).get("source"),
                }
            )
        except Exception as exc:
            logger.warning("Failed to retrieve aggregate risk summary: %s", exc)

        # Merge findings
        all_findings = []
        for f in findings:
            all_findings.append(f.model_dump())
        for f in vendor_findings:
            all_findings.append(f.model_dump())
        for f in recon_findings:
            all_findings.append(f.model_dump())
        for f in entity_findings:
            all_findings.append(f.model_dump())

        # Compile steps
        steps_list = [
            step(
                "fraud_analyzer",
                step_type="tool_call",
                input_payload={"tool": "risk_summary", "period": period},
                output_payload={
                    "risk_score": risk_summary.get("risk_score"),
                    "risk_level": risk_summary.get("risk_level"),
                    "finding_count": len(findings),
                    **_fraud_analyzer_prompt.metadata,
                },
            )
        ]
        if vendor_risk_data:
            steps_list.append(
                step(
                    "vendor_risk_analysis",
                    step_type="tool_call",
                    input_payload={"tool": "vendor_risk", "vendor": vendor_name_query},
                    output_payload={
                        "queried_vendor": vendor_name_query,
                        "vendor_findings_count": len(vendor_findings),
                    }
                )
            )
        if reconciliation_risk_data:
            steps_list.append(
                step(
                    "reconciliation_risk_analysis",
                    step_type="tool_call",
                    input_payload={"tool": "reconciliation_risk"},
                    output_payload={
                        "reconciliation_risk_score": recon_score,
                        "reconciliation_findings_count": len(recon_findings),
                    }
                )
            )
        if entity_relationship_risk_data:
            steps_list.append(
                step(
                    "entity_relationship_risk_analysis",
                    step_type="tool_call",
                    input_payload={"tool": "entity_relationship_risk"},
                    output_payload={
                        "entity_relationship_risk_score": entity_score,
                        "entity_findings_count": len(entity_findings),
                    }
                )
            )
        if aggregate_risk_data:
            steps_list.append(
                step(
                    "aggregate_risk_summary",
                    step_type="tool_call",
                    input_payload={"tool": "aggregate_risk_summary"},
                    output_payload={
                        "overall_risk_score": aggregate_risk_data.get("overall_risk_score"),
                        "overall_risk_level": aggregate_risk_data.get("overall_risk_level"),
                    }
                )
            )

        tool_results = {"risk_summary": risk_summary}
        if vendor_risk_data:
            tool_results["vendor_risk"] = vendor_risk_data
        if reconciliation_risk_data:
            tool_results["reconciliation_risk"] = reconciliation_risk_data
        if entity_relationship_risk_data:
            tool_results["entity_relationship_risk"] = entity_relationship_risk_data
        if aggregate_risk_data:
            tool_results["aggregate_risk_summary"] = aggregate_risk_data
            if aggregate_risk_data.get("alert_recommendations"):
                tool_results["alert_recommendations"] = aggregate_risk_data.get("alert_recommendations")
            if aggregate_risk_data.get("case_recommendations"):
                tool_results["case_recommendations"] = aggregate_risk_data.get("case_recommendations")

        return {
            "tool_results": tool_results,
            "findings": all_findings,
            "steps": steps_list,
        }

    async def investigation_synthesis_node(state: BrevixAgentState) -> dict[str, Any]:
        start = time.perf_counter()
        tool_results = state.get("tool_results", {})
        synthesis = synthesize_investigation(tool_results, state.get("findings", []))
        synthesis_latency_ms = round((time.perf_counter() - start) * 1000, 2)

        _investigation_synthesis_prompt.render({
            "source_domains": ", ".join(synthesis.supporting_domains) or "none",
            "deterministic_input_summary": synthesis_input_summary(tool_results),
        })

        return {
            "investigative_synthesis": synthesis.model_dump(),
            "steps": [
                step(
                    "investigation_synthesis",
                    output_payload={
                        "source_domains_used": synthesis.supporting_domains,
                        "investigation_priority": synthesis.investigation_priority,
                        "correlated_finding_count": len(synthesis.correlated_findings),
                        "reinforcing_signal_count": len(synthesis.reinforcing_signals),
                        "conflicting_signal_count": len(synthesis.conflicting_signals),
                        "evidence_summary_count": len(synthesis.evidence_summary),
                        "synthesis_latency_ms": synthesis_latency_ms,
                        "provider_name": resolved_provider.provider_name,
                        "model_name": resolved_provider.model_name,
                        "provider_latency_ms": 0.0,
                        "tokens_input": 0,
                        "tokens_output": 0,
                        **_investigation_synthesis_prompt.metadata,
                    },
                )
            ],
        }

    async def explanation_node(state: BrevixAgentState) -> dict[str, Any]:
        context = _build_context(state)
        findings_text = (
            "\n".join(
                f"- {f.get('title')} (severity: {f.get('severity', 'unknown')})"
                for f in context.get("findings", [])
            )
            or "No specific findings returned."
        )
        prompt = _explanation_prompt.render({
            "intent": str(context.get("intent") or ""),
            "risk_score": str(context.get("risk_score", 0)),
            "risk_level": str(context.get("risk_level", "low")),
            "findings_text": findings_text,
        })
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
                        **_explanation_prompt.metadata,
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
                        **_action_gate_prompt.metadata,
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
    builder.add_node(
        "investigation_synthesis",
        instrument_node("investigation_synthesis", investigation_synthesis_node, resolved_settings),
    )
    builder.add_node("explanation", instrument_node("explanation", explanation_node, resolved_settings))
    builder.add_node("action_gate", instrument_node("action_gate", action_gate_node, resolved_settings))
    builder.add_node("final_response", instrument_node("final_response", final_response_node, resolved_settings))
    builder.add_edge(START, "router")
    builder.add_edge("router", "context_loader")
    builder.add_edge("context_loader", "fraud_analyzer")
    builder.add_edge("fraud_analyzer", "investigation_synthesis")
    builder.add_edge("investigation_synthesis", "explanation")
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


def is_transaction_lookup(message: str) -> bool:
    transaction_terms = ("transaction", "transactions", "ledger", "activity")
    lookup_terms = ("what", "show", "list", "pull", "recent", "last", "latest", "history")
    if not any(term in message for term in transaction_terms):
        return False

    risk_terms = ("fraud", "suspicious", "risk", "alert", "anomaly", "duplicate", "split", "threshold")
    if any(term in message for term in risk_terms):
        return False

    return any(term in message for term in lookup_terms)


def transaction_filters_from_message(message: str) -> dict[str, Any]:
    normalized = message.lower()
    filters: dict[str, Any] = {"limit": 10}

    days_match = re.search(r"\blast\s+(\d{1,3})\s+days?\b", normalized)
    if days_match:
        days = max(1, min(int(days_match.group(1)), 90))
        today = datetime.now(timezone.utc).date()
        filters["date_from"] = (today - timedelta(days=days - 1)).isoformat()
        filters["date_to"] = today.isoformat()

    count_match = re.search(r"\blast\s+(\d{1,2})\s+transactions?\b", normalized)
    if count_match:
        filters["limit"] = max(1, min(int(count_match.group(1)), 20))

    return filters


def minimized_context(context: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "company_id": context.get("company_id"),
        "industry": context.get("industry"),
        "available_data_sources": context.get("available_data_sources", []),
        "user_role": context.get("user_role"),
    }
    transaction_summary = context.get("transaction_summary")
    if isinstance(transaction_summary, dict):
        payload["transaction_summary"] = {
            "total": transaction_summary.get("total"),
            "returned_count": transaction_summary.get("returned_count"),
            "date_from": transaction_summary.get("date_from"),
            "date_to": transaction_summary.get("date_to"),
        }
    dashboard_summary = context.get("dashboard_summary")
    if isinstance(dashboard_summary, dict):
        payload["dashboard_summary"] = {
            "risk_score": dashboard_summary.get("risk_score"),
            "total_transactions": dashboard_summary.get("total_transactions"),
            "flagged_alerts": dashboard_summary.get("flagged_alerts"),
            "vendors_monitored": dashboard_summary.get("vendors_monitored"),
            "amount_reviewed": dashboard_summary.get("amount_reviewed"),
        }

    return payload


def synthesis_input_summary(tool_results: dict[str, Any]) -> str:
    if not tool_results:
        return "No deterministic risk outputs were available."

    summaries: list[str] = []
    for domain, payload in tool_results.items():
        if isinstance(payload, dict):
            keys = ", ".join(sorted(str(key) for key in payload.keys())[:8])
            summaries.append(f"{domain}: keys [{keys}]")
        elif isinstance(payload, list):
            summaries.append(f"{domain}: {len(payload)} item(s)")
        else:
            summaries.append(f"{domain}: {type(payload).__name__}")
    return "; ".join(summaries)


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


def dashboard_findings_from_context(company_context: dict[str, Any]) -> list[AgentFinding]:
    dashboard_summary = company_context.get("dashboard_summary") if isinstance(company_context, dict) else None
    if not isinstance(dashboard_summary, dict):
        return []

    risk_score = int(dashboard_summary.get("risk_score") or 0)
    total_transactions = int(dashboard_summary.get("total_transactions") or 0)
    flagged_alerts = int(dashboard_summary.get("flagged_alerts") or 0)
    vendors_monitored = int(dashboard_summary.get("vendors_monitored") or 0)
    amount_reviewed = float(dashboard_summary.get("amount_reviewed") or 0)

    return [
        AgentFinding(
            title="Financial health summary",
            severity=normalize_severity(severity_from_risk_score(risk_score)),
            confidence=1.0,
            summary=(
                f"Dashboard health is {risk_score}/100 across {total_transactions} transactions, "
                f"{flagged_alerts} open alerts, and {vendors_monitored} monitored vendors."
            ),
            evidence=[
                {"type": "dashboard_metric", "label": f"Risk score: {risk_score}/100"},
                {"type": "dashboard_metric", "label": f"Transactions reviewed: {total_transactions}"},
                {"type": "dashboard_metric", "label": f"Open alerts: {flagged_alerts}"},
                {"type": "dashboard_metric", "label": f"Vendors monitored: {vendors_monitored}"},
                {"type": "dashboard_metric", "label": f"Activity reviewed: ${amount_reviewed:,.2f}"},
            ],
        )
    ]


def transaction_findings_from_context(company_context: dict[str, Any]) -> list[AgentFinding]:
    transaction_summary = company_context.get("transaction_summary") if isinstance(company_context, dict) else None
    if not isinstance(transaction_summary, dict):
        return []

    total = int(transaction_summary.get("total") or 0)
    returned_count = int(transaction_summary.get("returned_count") or 0)
    date_from = transaction_summary.get("date_from")
    date_to = transaction_summary.get("date_to")

    evidence = [
        {"type": "transaction_summary", "label": f"Transactions matched: {total}"},
        {"type": "transaction_summary", "label": f"Rows returned: {returned_count}"},
    ]
    if date_from and date_to:
        evidence.append({"type": "transaction_summary", "label": f"Date range: {date_from} to {date_to}"})

    return [
        AgentFinding(
            title="Transaction lookup summary",
            severity="info",
            confidence=1.0,
            summary=f"Returned {returned_count} of {total} matching transactions from the ledger.",
            evidence=evidence,
        )
    ]


def severity_from_risk_score(score: int) -> str:
    if score >= 90:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score > 0:
        return "low"
    return "info"


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
    company_context = state.get("company_context", {})
    return {
        "intent": state.get("intent"),
        "errors": state.get("errors", []),
        "findings": state.get("findings", []),
        "investigative_synthesis": state.get("investigative_synthesis", {}),
        "risk_score": risk_summary.get("risk_score", 0),
        "risk_level": risk_summary.get("risk_level", "low"),
        "transaction_summary": company_context.get("transaction_summary") if isinstance(company_context, dict) else None,
        "dashboard_summary": company_context.get("dashboard_summary") if isinstance(company_context, dict) else None,
    }


def suggested_actions(state: BrevixAgentState) -> list[RecommendedAction]:
    if state.get("errors") or state.get("intent") in {"unknown_or_unsupported", "transaction_lookup", "dashboard_health"}:
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
