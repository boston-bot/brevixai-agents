from __future__ import annotations

from typing import Any


ENTITY_ORDER = [
    "vendors",
    "employees",
    "bank_accounts",
    "payments",
    "approvers",
    "documents",
    "company_users",
]

RELATIONSHIP_ORDER = [
    "payment_to_vendor",
    "employee_approved_payment",
    "payment_to_document",
    "vendor_uses_bank_account",
    "employee_shares_address_with_vendor",
    "vendor_related_to_vendor",
]


def build_relational_readiness_audit(data_sources: dict[str, Any] | None = None) -> dict[str, Any]:
    """Audit whether current payloads are ready for Phase 5 graph intelligence."""

    sources = data_sources if isinstance(data_sources, dict) else {}
    transactions = _transactions_from_sources(sources)
    vendor_payloads = _vendor_payloads(sources.get("vendor_risk"))
    entity_payload = sources.get("entity_relationship_risk") if isinstance(sources.get("entity_relationship_risk"), dict) else {}
    entity_evidence = _entity_evidence(entity_payload)
    company_context = sources.get("company_context") if isinstance(sources.get("company_context"), dict) else {}

    entity_contracts = [
        _vendors_contract(transactions, vendor_payloads, entity_evidence),
        _employees_contract(entity_evidence),
        _bank_accounts_contract(transactions, entity_evidence),
        _payments_contract(transactions),
        _approvers_contract(transactions),
        _documents_contract(transactions, entity_evidence),
        _company_users_contract(company_context, transactions),
    ]
    relationship_contracts = [
        _payment_to_vendor_contract(transactions, vendor_payloads, entity_evidence),
        _employee_approved_payment_contract(transactions),
        _payment_to_document_contract(transactions),
        _vendor_uses_bank_account_contract(transactions, entity_evidence),
        _employee_shares_address_with_vendor_contract(entity_evidence),
        _vendor_related_to_vendor_contract(entity_evidence),
    ]
    critical_blockers = _critical_blockers(entity_contracts, relationship_contracts)
    readiness_score = _readiness_score(entity_contracts, relationship_contracts)
    phase_5_ready = not critical_blockers and all(
        contract["status"] == "ready"
        for contract in [*entity_contracts, *relationship_contracts]
        if contract.get("required_for_phase_5")
    )
    status = "ready" if phase_5_ready else "blocked" if critical_blockers else "partial"

    return {
        "status": status,
        "audit_type": "relational_readiness",
        "phase_5_ready": phase_5_ready,
        "readiness_score": readiness_score,
        "entity_contracts": entity_contracts,
        "relationship_contracts": relationship_contracts,
        "critical_blockers": critical_blockers,
        "readiness_summary": {
            "phase_5_ready": phase_5_ready,
            "status": status,
            "readiness_score": readiness_score,
            "entity_ready_count": sum(1 for contract in entity_contracts if contract["status"] == "ready"),
            "entity_contract_count": len(entity_contracts),
            "relationship_ready_count": sum(1 for contract in relationship_contracts if contract["status"] == "ready"),
            "relationship_contract_count": len(relationship_contracts),
            "critical_blocker_count": len(critical_blockers),
            "transaction_sample_count": len(transactions),
        },
        "recommended_action": {
            "type": "prepare_relational_data_contracts",
            "label": "Prepare relational data contracts",
            "requires_approval": False,
            "payload": {
                "audit_type": "relational_readiness",
                "phase_5_ready": phase_5_ready,
                "status": status,
                "critical_blocker_count": len(critical_blockers),
                "readiness_score": readiness_score,
            },
        },
        "recommended_next_steps": _recommended_next_steps(critical_blockers, entity_contracts, relationship_contracts),
        "scope_limitations": [
            "Audit is based on agent-visible payloads only; it does not inspect Laravel migrations or database catalogs.",
            "A ready result means current payload contracts look graph-ready, not that graph infrastructure has been implemented.",
        ],
    }


def synthesize_relational_readiness_answer(audit: dict[str, Any]) -> str:
    if not isinstance(audit, dict) or not audit:
        return "I could not complete the relational readiness audit. No graph infrastructure was created."

    summary = audit.get("readiness_summary") if isinstance(audit.get("readiness_summary"), dict) else {}
    status = str(audit.get("status") or "unknown")
    phase_5_ready = bool(audit.get("phase_5_ready"))
    score = audit.get("readiness_score")
    blockers = audit.get("critical_blockers") if isinstance(audit.get("critical_blockers"), list) else []
    next_steps = audit.get("recommended_next_steps") if isinstance(audit.get("recommended_next_steps"), list) else []

    ready_text = "ready" if phase_5_ready else "not ready"
    lines = [
        f"Phase 5 relational readiness audit: {ready_text} (status: {status}, score: {score})."
    ]
    lines.append(
        "Entity contracts ready: "
        f"{summary.get('entity_ready_count', 0)}/{summary.get('entity_contract_count', 0)}. "
        "Relationship contracts ready: "
        f"{summary.get('relationship_ready_count', 0)}/{summary.get('relationship_contract_count', 0)}."
    )

    if blockers:
        blocker_text = "; ".join(
            _blocker_text(blocker)
            for blocker in blockers[:5]
            if isinstance(blocker, dict)
        )
        if blocker_text:
            lines.append("Critical blockers: " + blocker_text + ".")

    if next_steps:
        lines.append("Next steps: " + "; ".join(str(step) for step in next_steps[:4]) + ".")

    lines.append("No graph database, graph infrastructure, alerts, cases, or data changes were created.")
    return " ".join(lines)


def _blocker_text(blocker: dict[str, Any]) -> str:
    missing = blocker.get("missing_required_fields")
    missing_text = ""
    if isinstance(missing, list) and missing:
        missing_text = f" missing {', '.join(str(item) for item in missing)}"
    return f"{blocker.get('contract', 'unknown contract')} is {blocker.get('status', 'not ready')}{missing_text}"


def _transactions_from_sources(sources: dict[str, Any]) -> list[dict[str, Any]]:
    direct = sources.get("transactions")
    if isinstance(direct, list):
        return [item for item in direct if isinstance(item, dict)]

    lookup = sources.get("transaction_lookup")
    if isinstance(lookup, dict) and isinstance(lookup.get("transactions"), list):
        return [item for item in lookup["transactions"] if isinstance(item, dict)]

    context = sources.get("company_context")
    if isinstance(context, dict):
        transaction_summary = context.get("transaction_summary")
        if isinstance(transaction_summary, dict) and isinstance(transaction_summary.get("transactions"), list):
            return [item for item in transaction_summary["transactions"] if isinstance(item, dict)]

    return []


def _vendor_payloads(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    vendors = payload.get("vendors")
    if isinstance(vendors, list):
        return [item for item in vendors if isinstance(item, dict)]
    if payload.get("vendor_id") or payload.get("vendor_name") or payload.get("vendor_risk_score") is not None:
        return [payload]
    return []


def _entity_evidence(payload: dict[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for key in ("supporting_evidence", "related_entities", "relationships", "entities"):
        value = payload.get(key)
        if isinstance(value, list):
            evidence.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            evidence.append(value)
    return evidence


def _vendors_contract(
    transactions: list[dict[str, Any]],
    vendor_payloads: list[dict[str, Any]],
    entity_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    vendor_id_count = _records_with_any_field([*transactions, *vendor_payloads, *entity_evidence], ("vendor_id",))
    vendor_name_count = _records_with_any_field([*transactions, *vendor_payloads], ("vendor", "vendor_name", "name"))
    status = "ready" if vendor_id_count > 0 else "partial" if vendor_name_count > 0 else "missing"
    return _contract(
        "vendors",
        status=status,
        required_for_phase_5=True,
        present_fields=_present_fields([*transactions, *vendor_payloads, *entity_evidence], ("vendor_id", "vendor", "vendor_name")),
        missing_required_fields=[] if vendor_id_count > 0 else ["vendor_id"],
        evidence_count=vendor_id_count or vendor_name_count,
        notes=_status_note(status, "Stable vendor_id is available.", "Vendor names are present, but stable vendor_id coverage is missing."),
    )


def _employees_contract(entity_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    employee_id_count = _records_with_any_field(entity_evidence, ("employee_id",))
    status = "ready" if employee_id_count > 0 else "missing"
    return _contract(
        "employees",
        status=status,
        required_for_phase_5=True,
        present_fields=_present_fields(entity_evidence, ("employee_id", "employee_name")),
        missing_required_fields=[] if employee_id_count > 0 else ["employee_id"],
        evidence_count=employee_id_count,
        notes=_status_note(status, "Stable employee_id is available.", "No stable employee_id evidence is visible."),
    )


def _bank_accounts_contract(transactions: list[dict[str, Any]], entity_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    records = [*transactions, *entity_evidence]
    bank_account_count = _records_with_any_field(records, ("bank_account_id", "account_id"))
    status = "ready" if bank_account_count > 0 else "missing"
    return _contract(
        "bank_accounts",
        status=status,
        required_for_phase_5=True,
        present_fields=_present_fields(records, ("bank_account_id", "account_id", "account_last4")),
        missing_required_fields=[] if bank_account_count > 0 else ["bank_account_id"],
        evidence_count=bank_account_count,
        notes=_status_note(status, "Stable bank account identifier is available.", "No stable bank account identifier is visible."),
    )


def _payments_contract(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    base_required = ("id", "date", "amount")
    graph_required = ("company_id", "vendor_id", "approved_by", "document_id", "bank_account_id", "company_user_id")
    required = (*base_required, *graph_required)
    missing = [field for field in required if _records_with_any_field(transactions, (field,)) == 0]
    missing_base = [field for field in base_required if field in missing]
    status = "ready" if transactions and not missing else "partial" if transactions and not missing_base else "missing"
    return _contract(
        "payments",
        status=status,
        required_for_phase_5=True,
        present_fields=_present_fields(
            transactions,
            ("id", "transaction_id", "company_id", "vendor_id", "date", "amount", "approved_by", "document_id", "bank_account_id", "company_user_id", "status"),
        ),
        missing_required_fields=missing,
        evidence_count=len(transactions),
        notes=_status_note(status, "Payment sample includes required graph identifiers.", "Payment sample is missing required graph identifiers."),
    )


def _approvers_contract(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    has_field = any("approved_by" in transaction for transaction in transactions)
    approved_count = _records_with_any_field(transactions, ("approved_by",))
    status = "ready" if approved_count > 0 else "partial" if has_field else "missing"
    return _contract(
        "approvers",
        status=status,
        required_for_phase_5=True,
        present_fields=_present_fields(transactions, ("approved_by", "approver_id")),
        missing_required_fields=[] if approved_count > 0 else ["approved_by"],
        evidence_count=approved_count,
        notes=_status_note(status, "Approval identifier is available on payments.", "approved_by is not populated on payments."),
    )


def _documents_contract(transactions: list[dict[str, Any]], entity_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    records = [*transactions, *entity_evidence]
    has_field = any("document_id" in record for record in records)
    document_count = _records_with_any_field(records, ("document_id",))
    status = "ready" if document_count > 0 else "partial" if has_field else "missing"
    return _contract(
        "documents",
        status=status,
        required_for_phase_5=True,
        present_fields=_present_fields(records, ("document_id", "source_document_id")),
        missing_required_fields=[] if document_count > 0 else ["document_id"],
        evidence_count=document_count,
        notes=_status_note(status, "Document identifier is available.", "document_id is not populated on payments or evidence."),
    )


def _company_users_contract(company_context: dict[str, Any], transactions: list[dict[str, Any]]) -> dict[str, Any]:
    records = [company_context, *transactions]
    user_count = _records_with_any_field(records, ("company_user_id", "user_id"))
    company_count = _records_with_any_field(records, ("company_id",))
    status = "ready" if user_count > 0 and company_count > 0 else "partial" if company_count > 0 else "missing"
    missing = []
    if user_count == 0:
        missing.append("company_user_id")
    if company_count == 0:
        missing.append("company_id")
    return _contract(
        "company_users",
        status=status,
        required_for_phase_5=True,
        present_fields=_present_fields(records, ("company_user_id", "user_id", "company_id", "user_role")),
        missing_required_fields=missing,
        evidence_count=max(user_count, company_count),
        notes=_status_note(status, "Company/user anchor is available.", "Company/user anchor is incomplete."),
    )


def _payment_to_vendor_contract(
    transactions: list[dict[str, Any]],
    vendor_payloads: list[dict[str, Any]],
    entity_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    payment_count = _records_with_any_field(transactions, ("id", "transaction_id"))
    stable_vendor_count = _records_with_any_field(transactions, ("vendor_id",))
    named_vendor_count = _records_with_any_field(transactions, ("vendor", "vendor_name"))
    evidence_vendor_count = _records_with_any_field([*vendor_payloads, *entity_evidence], ("vendor_id",))
    status = "ready" if payment_count and stable_vendor_count else "partial" if payment_count and (named_vendor_count or evidence_vendor_count) else "missing"
    return _relationship(
        "payment_to_vendor",
        status=status,
        required_for_phase_5=True,
        required_fields=["payment.id", "payment.vendor_id"],
        present_fields=_present_fields(transactions, ("id", "transaction_id", "vendor_id", "vendor", "vendor_name")),
        missing_required_fields=[] if status == "ready" else ["vendor_id"],
        evidence_count=stable_vendor_count or named_vendor_count or evidence_vendor_count,
    )


def _employee_approved_payment_contract(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    approved_count = _records_with_any_field(transactions, ("approved_by",))
    status = "ready" if approved_count > 0 else "missing"
    return _relationship(
        "employee_approved_payment",
        status=status,
        required_for_phase_5=True,
        required_fields=["payment.id", "payment.approved_by"],
        present_fields=_present_fields(transactions, ("id", "transaction_id", "approved_by")),
        missing_required_fields=[] if approved_count > 0 else ["approved_by"],
        evidence_count=approved_count,
    )


def _payment_to_document_contract(transactions: list[dict[str, Any]]) -> dict[str, Any]:
    document_count = _records_with_any_field(transactions, ("document_id",))
    status = "ready" if document_count > 0 else "missing"
    return _relationship(
        "payment_to_document",
        status=status,
        required_for_phase_5=True,
        required_fields=["payment.id", "payment.document_id"],
        present_fields=_present_fields(transactions, ("id", "transaction_id", "document_id")),
        missing_required_fields=[] if document_count > 0 else ["document_id"],
        evidence_count=document_count,
    )


def _vendor_uses_bank_account_contract(transactions: list[dict[str, Any]], entity_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    records = [*transactions, *entity_evidence]
    linked_count = sum(
        1 for record in records
        if _has_any_field(record, ("vendor_id",)) and _has_any_field(record, ("bank_account_id", "account_id"))
    )
    status = "ready" if linked_count > 0 else "missing"
    return _relationship(
        "vendor_uses_bank_account",
        status=status,
        required_for_phase_5=True,
        required_fields=["vendor_id", "bank_account_id"],
        present_fields=_present_fields(records, ("vendor_id", "bank_account_id", "account_id")),
        missing_required_fields=[] if linked_count > 0 else ["bank_account_id"],
        evidence_count=linked_count,
    )


def _employee_shares_address_with_vendor_contract(entity_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    linked_count = sum(
        1 for record in entity_evidence
        if _has_any_field(record, ("employee_id",)) and _has_any_field(record, ("vendor_id",))
    )
    status = "ready" if linked_count > 0 else "missing"
    return _relationship(
        "employee_shares_address_with_vendor",
        status=status,
        required_for_phase_5=False,
        required_fields=["employee_id", "vendor_id", "relationship_type"],
        present_fields=_present_fields(entity_evidence, ("employee_id", "vendor_id", "relationship_type", "address_id")),
        missing_required_fields=[] if linked_count > 0 else ["employee_id", "vendor_id"],
        evidence_count=linked_count,
    )


def _vendor_related_to_vendor_contract(entity_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    linked_count = sum(
        1 for record in entity_evidence
        if _has_any_field(record, ("vendor_id",)) and _has_any_field(record, ("related_vendor_id", "counterparty_vendor_id"))
    )
    status = "ready" if linked_count > 0 else "missing"
    return _relationship(
        "vendor_related_to_vendor",
        status=status,
        required_for_phase_5=False,
        required_fields=["vendor_id", "related_vendor_id"],
        present_fields=_present_fields(entity_evidence, ("vendor_id", "related_vendor_id", "counterparty_vendor_id", "relationship_id")),
        missing_required_fields=[] if linked_count > 0 else ["related_vendor_id"],
        evidence_count=linked_count,
    )


def _critical_blockers(entity_contracts: list[dict[str, Any]], relationship_contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for contract in [*entity_contracts, *relationship_contracts]:
        if not contract.get("required_for_phase_5"):
            continue
        if contract.get("status") == "ready":
            continue
        blockers.append(
            {
                "contract": contract["name"],
                "status": contract["status"],
                "missing_required_fields": contract.get("missing_required_fields", []),
                "reason": contract.get("notes") or f"{contract['name']} is not ready for Phase 5.",
            }
        )
    return blockers


def _recommended_next_steps(
    critical_blockers: list[dict[str, Any]],
    entity_contracts: list[dict[str, Any]],
    relationship_contracts: list[dict[str, Any]],
) -> list[str]:
    if not critical_blockers:
        return [
            "Keep Phase 5 inside PostgreSQL first and validate relationship queries before adding graph infrastructure.",
            "Add integration tests that assert stable identifiers across vendors, payments, approvers, documents, employees, and bank accounts.",
        ]

    missing_fields = {
        field
        for blocker in critical_blockers
        for field in blocker.get("missing_required_fields", [])
    }
    steps: list[str] = []
    if "approved_by" in missing_fields:
        steps.append("Expose a stable approval identifier on payment or transaction payloads, either from transaction data or a joined approval table.")
    if "document_id" in missing_fields:
        steps.append("Add a document evidence identifier and link it to payment or transaction records before building document graph edges.")
    if "vendor_id" in missing_fields:
        steps.append("Expose stable vendor_id values in transaction payloads so payment-to-vendor edges do not depend on vendor names.")
    if "bank_account_id" in missing_fields:
        steps.append("Expose stable bank account identifiers for vendor payment routing before vendor-to-account edges are treated as graph-ready.")
    if "employee_id" in missing_fields:
        steps.append("Expose stable employee_id values for approver and employee-vendor relationship edges.")
    if "company_user_id" in missing_fields:
        steps.append("Expose a stable company_user_id or user_id anchor for company-scoped review and approval relationships.")

    steps.append("Re-run the relational readiness audit after payload contracts include the missing identifiers.")
    return _unique_preserving_order(steps)


def _contract(
    name: str,
    status: str,
    required_for_phase_5: bool,
    present_fields: list[str],
    missing_required_fields: list[str],
    evidence_count: int,
    notes: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "required_for_phase_5": required_for_phase_5,
        "present_fields": present_fields,
        "missing_required_fields": missing_required_fields,
        "evidence_count": evidence_count,
        "notes": notes,
    }


def _relationship(
    name: str,
    status: str,
    required_for_phase_5: bool,
    required_fields: list[str],
    present_fields: list[str],
    missing_required_fields: list[str],
    evidence_count: int,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "required_for_phase_5": required_for_phase_5,
        "required_fields": required_fields,
        "present_fields": present_fields,
        "missing_required_fields": missing_required_fields,
        "evidence_count": evidence_count,
    }


def _readiness_score(entity_contracts: list[dict[str, Any]], relationship_contracts: list[dict[str, Any]]) -> float:
    contracts = [
        contract for contract in [*entity_contracts, *relationship_contracts]
        if contract.get("required_for_phase_5")
    ]
    if not contracts:
        return 0.0
    points = 0.0
    for contract in contracts:
        if contract["status"] == "ready":
            points += 1.0
        elif contract["status"] == "partial":
            points += 0.5
    return round(points / len(contracts), 2)


def _records_with_any_field(records: list[dict[str, Any]], fields: tuple[str, ...]) -> int:
    return sum(1 for record in records if _has_any_field(record, fields))


def _has_any_field(record: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(record.get(field) not in {None, ""} for field in fields)


def _present_fields(records: list[dict[str, Any]], fields: tuple[str, ...]) -> list[str]:
    return [
        field for field in fields
        if any(field in record and record.get(field) not in {None, ""} for record in records)
    ]


def _status_note(status: str, ready_note: str, not_ready_note: str) -> str:
    if status == "ready":
        return ready_note
    return not_ready_note


def _unique_preserving_order(values: Any) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
