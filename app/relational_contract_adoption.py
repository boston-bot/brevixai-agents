from __future__ import annotations

from typing import Any


ENDPOINT_REQUIREMENTS = {
    "company_context": {
        "required_fields": ["company_id", "company_user_id or user_id"],
        "notes": "Company context must provide stable company and caller anchors for scoped graph-ready payloads.",
    },
    "transaction_lookup": {
        "required_fields": [
            "transactions[].id",
            "transactions[].company_id",
            "transactions[].company_user_id",
            "transactions[].vendor_id",
            "transactions[].bank_account_id",
            "transactions[].approved_by",
            "transactions[].document_id",
            "transactions[].date",
            "transactions[].amount",
        ],
        "notes": "Transaction payloads are the core source for payment, vendor, approver, document, and bank-account edges.",
    },
    "vendor_risk": {
        "required_fields": ["vendor_id or vendors[].vendor_id"],
        "notes": "Vendor-risk payloads should include stable vendor identifiers; vendor names are display context only.",
    },
    "entity_relationship_risk": {
        "required_fields": [
            "supporting_evidence[].employee_id",
            "supporting_evidence[].vendor_id",
            "supporting_evidence[].bank_account_id",
            "supporting_evidence[].related_vendor_id",
            "supporting_evidence[].relationship_type",
        ],
        "notes": "Entity relationship evidence should expose stable endpoints for employee, vendor, account, and related-vendor relationships.",
    },
}


CONTRACT_ENDPOINTS = {
    "vendors": ["transaction_lookup", "vendor_risk", "entity_relationship_risk"],
    "employees": ["entity_relationship_risk"],
    "bank_accounts": ["transaction_lookup", "entity_relationship_risk"],
    "payments": ["transaction_lookup"],
    "approvers": ["transaction_lookup"],
    "documents": ["transaction_lookup"],
    "company_users": ["company_context", "transaction_lookup"],
    "payment_to_vendor": ["transaction_lookup"],
    "employee_approved_payment": ["transaction_lookup"],
    "payment_to_document": ["transaction_lookup"],
    "vendor_uses_bank_account": ["transaction_lookup", "entity_relationship_risk"],
    "employee_shares_address_with_vendor": ["entity_relationship_risk"],
    "vendor_related_to_vendor": ["entity_relationship_risk"],
}


FIELD_ACTIONS = {
    "approved_by": "Join or expose a stable approver identifier on transaction payloads.",
    "document_id": "Expose the supporting document or evidence identifier on transaction payloads.",
    "vendor_id": "Expose stable vendor identifiers; do not rely on vendor display names.",
    "bank_account_id": "Expose stable bank-account identifiers for payment routing and vendor-account edges.",
    "employee_id": "Expose stable employee identifiers in entity-relationship evidence.",
    "company_user_id": "Expose a stable company-user or caller anchor alongside company_id.",
    "company_id": "Include company_id on scoped payload rows so relationship data cannot float across tenants.",
    "related_vendor_id": "Expose the stable related-vendor endpoint for vendor-to-vendor relationship evidence.",
}


def build_relational_contract_adoption_report(
    audit: dict[str, Any] | None,
    *,
    tool_failures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Map a Phase 5 readiness audit into endpoint-level Laravel payload work."""

    audit_payload = audit if isinstance(audit, dict) else {}
    failures = [failure for failure in tool_failures or [] if isinstance(failure, dict)]
    endpoint_states = _endpoint_states(audit_payload, failures)
    blocking_endpoint_count = sum(1 for endpoint in endpoint_states if endpoint["status"] != "ready")
    phase_5_ready = bool(audit_payload.get("phase_5_ready")) and not failures
    status = "ready" if phase_5_ready and blocking_endpoint_count == 0 else "blocked"

    return {
        "report_type": "relational_contract_adoption",
        "status": status,
        "phase_5_ready": phase_5_ready,
        "readiness_score": audit_payload.get("readiness_score"),
        "blocking_endpoint_count": blocking_endpoint_count,
        "endpoint_requirements": endpoint_states,
        "api_remediation_tasks": _remediation_tasks(endpoint_states),
        "acceptance_checks": [
            "Run scripts/smoke_relational_contract.py against the deployed Laravel API without --allow-blocked.",
            "Confirm the smoke JSON reports phase_5_ready=true and no tool_failures.",
            "Run .venv/bin/python -m pytest tests/test_relational_contracts.py tests/test_relational_contract_smoke.py.",
        ],
        "recommended_action": {
            "type": "update_laravel_relational_payloads",
            "label": "Update Laravel relational payloads",
            "requires_approval": False,
            "payload": {
                "report_type": "relational_contract_adoption",
                "status": status,
                "phase_5_ready": phase_5_ready,
                "blocking_endpoint_count": blocking_endpoint_count,
            },
        },
        "scope_limitations": [
            "Report is derived from the readiness audit and agent-tool responses only.",
            "No graph infrastructure, database migrations, records, alerts, cases, or writes were created.",
        ],
    }


def _endpoint_states(audit: dict[str, Any], failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    impacted: dict[str, dict[str, Any]] = {
        name: {
            "endpoint": name,
            "status": "ready",
            "required_fields": list(config["required_fields"]),
            "missing_fields": [],
            "affected_contracts": [],
            "tool_failure": None,
            "notes": config["notes"],
        }
        for name, config in ENDPOINT_REQUIREMENTS.items()
    }

    for failure in failures:
        endpoint = str(failure.get("tool") or "").strip()
        if endpoint not in impacted:
            continue
        impacted[endpoint]["status"] = "failed"
        impacted[endpoint]["tool_failure"] = {
            "error_class": failure.get("error_class"),
            "message": failure.get("message"),
        }

    for blocker in _blockers(audit):
        contract_name = str(blocker.get("contract") or "").strip()
        endpoints = CONTRACT_ENDPOINTS.get(contract_name, [])
        missing_fields = [str(field) for field in blocker.get("missing_required_fields", [])]
        for endpoint in endpoints:
            state = impacted[endpoint]
            if state["status"] == "ready":
                state["status"] = "blocked"
            state["affected_contracts"] = _unique([*state["affected_contracts"], contract_name])
            state["missing_fields"] = _unique([*state["missing_fields"], *missing_fields])

    return list(impacted.values())


def _blockers(audit: dict[str, Any]) -> list[dict[str, Any]]:
    critical = audit.get("critical_blockers")
    if isinstance(critical, list):
        return [item for item in critical if isinstance(item, dict)]
    return []


def _remediation_tasks(endpoint_states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for endpoint in endpoint_states:
        if endpoint["status"] == "ready":
            continue
        missing_fields = endpoint.get("missing_fields") or []
        actions = _actions_for_fields(missing_fields)
        if endpoint.get("tool_failure"):
            actions.append("Restore the agent-tool endpoint so the contract gate can inspect the payload.")
        tasks.append(
            {
                "task_key": f"{endpoint['endpoint']}_payload_contract",
                "endpoint": endpoint["endpoint"],
                "priority": "high" if endpoint["endpoint"] == "transaction_lookup" else "medium",
                "missing_fields": missing_fields,
                "affected_contracts": endpoint.get("affected_contracts", []),
                "actions": _unique(actions),
            }
        )
    return tasks


def _actions_for_fields(fields: list[str]) -> list[str]:
    actions = []
    for field in fields:
        actions.append(FIELD_ACTIONS.get(field, f"Expose stable {field} values in the relevant agent-tool payload."))
    return actions


def _unique(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique
