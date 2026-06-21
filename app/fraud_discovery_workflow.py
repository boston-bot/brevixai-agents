from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import Settings
from app.models import BrevixAgentState
from app.prompts import load_prompt
from app.providers import ModelProvider, ProviderConfigError, ProviderRuntimeError
from app.tools.laravel import LaravelToolClient, LaravelToolError

logger = logging.getLogger("brevix.agent.fraud_discovery")

# How many playbooks to retrieve and how many evidence items / prompts to surface.
_PLAYBOOK_LIMIT = 3
_MAX_EVIDENCE_GAPS = 6
_MAX_SUGGESTED_ANSWERS = 3


def build_fraud_discovery_workflow(
    tool_client: LaravelToolClient,
    settings: Settings,
    provider: ModelProvider,
):
    _prompt = load_prompt("fraud_discovery", "v1")

    async def fraud_discovery_node(state: BrevixAgentState) -> dict[str, Any]:
        user_message = state.get("user_message", "")
        user_id = state.get("user_id", "")
        company_id = state.get("company_id", "")
        trace_id = state.get("agent_run_id")

        # ── 1. Playbook retrieval ─────────────────────────────────────────────
        playbooks: list[dict[str, Any]] = []
        playbook_fetch_error: str | None = None
        try:
            raw = await tool_client.fraud_playbook_search(
                query=user_message,
                limit=_PLAYBOOK_LIMIT,
                user_id=user_id,
                trace_id=trace_id,
                trace_metadata={"intent": "fraud_discovery", "company_id": company_id},
            )
            playbooks = raw.get("data") or []
        except (LaravelToolError, Exception) as exc:
            playbook_fetch_error = str(exc)
            logger.warning("Playbook fetch failed — proceeding without RAG context: %s", exc)

        # ── 2. Derive structured state from playbooks ─────────────────────────
        playbooks_context, evidence_gaps, suggested_answers, next_best_action = (
            _process_playbooks(playbooks, user_message)
        )

        # ── 3. Build prompt ───────────────────────────────────────────────────
        prompt = _prompt.render({
            "user_message": user_message,
            "playbooks_context": playbooks_context,
        })

        llm_context: dict[str, Any] = {
            "conversation_history": (state.get("conversation_history") or [])[-8:],
            "company_id": company_id,
            "intent": "fraud_discovery",
        }

        # ── 4. LLM call ───────────────────────────────────────────────────────
        try:
            response = await provider.generate(prompt, llm_context)
            final_response = response.text
            llm_step = _step(
                "fraud_discovery_workflow",
                step_type="llm_call",
                output_payload={
                    "playbooks_found": len(playbooks),
                    "evidence_gaps_surfaced": len(evidence_gaps),
                    "provider_name": response.provider_name,
                    "model_name": response.model_name,
                    "provider_latency_ms": response.latency_ms,
                    "tokens_input": response.tokens_input,
                    "tokens_output": response.tokens_output,
                    **({"playbook_fetch_error": playbook_fetch_error} if playbook_fetch_error else {}),
                },
            )
        except (ProviderConfigError, ProviderRuntimeError) as exc:
            logger.error("Provider failed in fraud_discovery_node: %s", exc)
            final_response = (
                "I understand your concern and want to help you investigate it carefully. "
                "I'm having trouble connecting to my analysis engine right now — "
                "please try again in a moment. No actions have been taken."
            )
            return {
                "errors": [str(exc)],
                "final_response": final_response,
                "evidence_gaps": evidence_gaps,
                "next_best_action": next_best_action,
                "suggested_answers": suggested_answers,
                "steps": [_step(
                    "fraud_discovery_workflow",
                    status="failed",
                    error_message=str(exc),
                    output_payload={"playbooks_found": len(playbooks)},
                )],
            }

        return {
            "final_response": final_response,
            "evidence_gaps": evidence_gaps,
            "next_best_action": next_best_action,
            "suggested_answers": suggested_answers,
            "tool_results": {"fraud_discovery": {"playbooks": playbooks}},
            "steps": [llm_step],
        }

    return fraud_discovery_node


# ── Helpers ────────────────────────────────────────────────────────────────────

def _process_playbooks(
    playbooks: list[dict[str, Any]],
    user_message: str,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    """Extract structured state fields and a formatted context string from playbook results.

    Returns: (playbooks_context, evidence_gaps, suggested_answers, next_best_action)
    """
    if not playbooks:
        return (
            "No specific investigation playbooks matched this query. "
            "Responding from general financial forensics knowledge.\n",
            [],
            _generic_suggested_answers(),
            None,
        )

    # Build context string for the LLM
    ctx_parts: list[str] = ["Relevant Investigation Playbooks:\n"]
    seen_docs: set[str] = set()
    all_docs: list[tuple[str, str]] = []  # (normalized_key, display_label)
    all_tests: list[str] = []

    for pb in playbooks:
        title = pb.get("title") or "Unknown"
        scheme = pb.get("scheme_name") or ""
        cat = pb.get("fraud_category") or pb.get("category") or "Unknown"
        desc = pb.get("description") or ""
        symptoms: list = pb.get("symptoms") or []
        red_flags: list = pb.get("red_flags") or []
        tests: list = pb.get("tests") or []
        docs: list = pb.get("required_documents") or pb.get("document_requests") or []
        expected: list = pb.get("expected_findings") or []
        remediation: list = pb.get("remediation") or []
        sources: list = pb.get("source_references") or []

        block = [f"### {title} ({cat})"]
        if scheme:
            block.append(f"Scheme: {scheme}")
        if desc:
            block.append(f"Description: {desc}")
        if symptoms:
            block.append(f"Symptoms: {', '.join(str(s) for s in symptoms)}")
        if red_flags:
            block.append(f"Red Flags: {', '.join(str(r) for r in red_flags)}")
        if tests:
            block.append(f"Recommended Tests: {', '.join(str(t) for t in tests)}")
        if docs:
            block.append(f"Required Documents: {', '.join(str(d) for d in docs)}")
        if expected:
            block.append(f"Expected Findings: {', '.join(str(f) for f in expected)}")
        if remediation:
            block.append(f"Remediation: {', '.join(str(r) for r in remediation)}")
        if sources:
            block.append(f"Sources: {', '.join(str(s) for s in sources)}")
        ctx_parts.append("\n".join(block))

        # Collect docs for evidence_gaps (deduplicated, preserve insertion order)
        for doc in docs:
            doc_str = str(doc).strip()
            key = doc_str.lower().replace(" ", "_").replace("/", "_")
            if key not in seen_docs:
                seen_docs.add(key)
                all_docs.append((key, doc_str))

        all_tests.extend(str(t) for t in tests)

    playbooks_context = "\n\n".join(ctx_parts) + "\n"

    # Build evidence_gaps from required documents
    evidence_gaps = [
        {
            "requirementKey": key,
            "label": label,
            "reason": _doc_reason(label),
            "priority": "required" if i < 2 else "recommended",
            "status": "missing",
            "acceptedSourceTypes": ["file_upload"],
        }
        for i, (key, label) in enumerate(all_docs[:_MAX_EVIDENCE_GAPS])
    ]

    # Build suggested_answers from tests and symptoms of the first playbook
    first_pb = playbooks[0]
    first_title = first_pb.get("title") or "this type of fraud"
    first_scheme = first_pb.get("scheme_name") or ""
    subject = first_scheme or first_title

    suggested_answers: list[dict[str, Any]] = [
        {"id": "fd_what_is", "prompt": f"What is {subject} and how does it typically occur?"},
        {"id": "fd_how_detect", "prompt": f"What are the strongest early warning signs of {subject}?"},
        {"id": "fd_what_next", "prompt": "What records should I prioritize uploading to investigate this?"},
    ][:_MAX_SUGGESTED_ANSWERS]

    # Build next_best_action — point to the first required document or intake
    next_best_action: dict[str, Any] | None = None
    if evidence_gaps:
        first_gap = evidence_gaps[0]
        next_best_action = {
            "actionKey": "upload_evidence",
            "label": f"Upload {first_gap['label']}",
            "description": first_gap["reason"],
            "route": "/evidence",
            "cta": "Upload records",
        }
    else:
        next_best_action = {
            "actionKey": "complete_intake",
            "label": "Answer the intake questionnaire",
            "description": (
                "Help Brevix understand your review objective and scope so it can "
                "tailor the analysis to your situation."
            ),
            "route": "/onboarding",
            "cta": "Start questionnaire",
        }

    return playbooks_context, evidence_gaps, suggested_answers, next_best_action


def _doc_reason(label: str) -> str:
    """Return a short reason why a given document type is valuable for fraud detection."""
    label_lower = label.lower()
    if "payroll" in label_lower:
        return "Identifies active employees, pay rates, and changes — core input for ghost employee and overtime fraud tests."
    if "employee roster" in label_lower or "employee list" in label_lower:
        return "Cross-referenced against payroll to detect ghost employees or terminated-but-still-paid staff."
    if "bank statement" in label_lower:
        return "Provides the authoritative record of cash movements for reconciliation and unauthorized transfer tests."
    if "invoice" in label_lower:
        return "Required to verify vendor legitimacy, detect duplicate invoices, and test for shell company patterns."
    if "vendor" in label_lower:
        return "Enables conflict-of-interest checks, address/bank-account deduplication, and concentration analysis."
    if "general ledger" in label_lower or "gl" in label_lower:
        return "Source of truth for manual adjustments and journal entries — key for detecting concealment activity."
    if "tax" in label_lower or "w-2" in label_lower or "1099" in label_lower:
        return "Validates worker classification and reported compensation against payroll records."
    if "time" in label_lower or "timesheet" in label_lower:
        return "Necessary for overtime fraud and labor misclassification tests."
    if "expense" in label_lower or "receipt" in label_lower:
        return "Validates business purpose and approval for discretionary spend."
    return f"Provides evidence needed to run the relevant fraud detection tests for {label}."


def _generic_suggested_answers() -> list[dict[str, Any]]:
    return [
        {"id": "fd_common", "prompt": "What are the most common types of occupational fraud in small businesses?"},
        {"id": "fd_first_step", "prompt": "What records should I gather if I suspect something is wrong?"},
        {"id": "fd_tell_me_more", "prompt": "How does Brevix analyze financial records for fraud?"},
    ]


def _step(
    step_name: str,
    step_type: str = "workflow_synthesis",
    input_payload: dict[str, Any] | None = None,
    output_payload: dict[str, Any] | None = None,
    status: str = "completed",
    error_message: str | None = None,
) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    return {
        "step_name": step_name,
        "step_type": step_type,
        "input_payload": input_payload,
        "output_payload": output_payload,
        "status": status,
        "started_at": ts,
        "completed_at": ts if status == "completed" else None,
        "error_message": error_message,
    }
