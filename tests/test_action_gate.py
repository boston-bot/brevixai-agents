from app.graph import SENSITIVE_ACTION_TYPES, build_create_investigation_action, suggested_actions
from app.models import RecommendedAction


def test_sensitive_action_types_are_explicitly_listed_for_approval_gate() -> None:
    assert "create_alert" in SENSITIVE_ACTION_TYPES
    assert "create_case" in SENSITIVE_ACTION_TYPES


def test_phase_one_suggested_actions_do_not_create_records() -> None:
    actions = suggested_actions(
        {
            "intent": "fraud_pattern_search",
            "findings": [{"title": "Possible unusual activity"}],
            "errors": [],
        }
    )

    assert actions[0].type == "review_findings"
    assert actions[0].requires_approval is False


def test_action_gate_marks_sensitive_actions_as_approval_only() -> None:
    # Phase 1 does not produce create actions, but the gate still hardens any
    # sensitive action shape before Laravel persists it for human approval.
    sensitive = {"create_alert", "create_case"}

    assert sensitive.issubset(SENSITIVE_ACTION_TYPES)


def test_send_email_in_sensitive_action_types() -> None:
    assert "send_email" in SENSITIVE_ACTION_TYPES


def test_case_mutating_tools_in_sensitive_action_types() -> None:
    assert "finalize_case" in SENSITIVE_ACTION_TYPES
    assert "update_case" in SENSITIVE_ACTION_TYPES


def test_full_approval_required_default_set_is_present() -> None:
    required = {"draft_case", "draft_email", "send_email", "flag_transaction", "finalize_case", "update_case"}
    assert required.issubset(SENSITIVE_ACTION_TYPES)


def test_send_email_action_requires_approval_at_gate() -> None:
    """send_email must never execute without human approval."""
    action = RecommendedAction(type="send_email", label="Send report email", requires_approval=False, payload={})
    # Replicate the gate logic from action_gate_node.
    if action.type in SENSITIVE_ACTION_TYPES:
        action.requires_approval = True
    assert action.requires_approval is True


def test_finalize_case_action_requires_approval_at_gate() -> None:
    action = RecommendedAction(type="finalize_case", label="Finalize case", requires_approval=False, payload={})
    if action.type in SENSITIVE_ACTION_TYPES:
        action.requires_approval = True
    assert action.requires_approval is True


def test_update_case_action_requires_approval_at_gate() -> None:
    action = RecommendedAction(type="update_case", label="Update case", requires_approval=False, payload={})
    if action.type in SENSITIVE_ACTION_TYPES:
        action.requires_approval = True
    assert action.requires_approval is True


def test_review_findings_does_not_require_approval() -> None:
    """Non-sensitive actions must not be escalated to requiring approval."""
    action = RecommendedAction(type="review_findings", label="Review findings", requires_approval=False, payload={})
    if action.type in SENSITIVE_ACTION_TYPES:
        action.requires_approval = True
    assert action.requires_approval is False


def _high_priority_workflow_state() -> dict:
    return {
        "intent": "fraud_pattern_search",
        "errors": [],
        "findings": [
            {
                "title": "Vendor Concentration",
                "severity": "medium",
                "confidence": 0.7,
                "summary": "Elevated vendor concentration risk signal.",
                "evidence": [{"vendor_id": "vendor-9"}],
            }
        ],
        "next_best_action": {
            "type": "review_vendor_verification_evidence",
            "label": "Review urgent vendor verification evidence",
            "requires_approval": False,
            "payload": {
                "workflow_type": "vendor_verification",
                "review_priority": "high",
                "vendor_count": 3,
                "vendor_ids": ["vendor-9", "vendor-12"],
                "highest_vendor_risk_score": 82,
            },
        },
        "readiness_summary": {
            "review_scope": "vendor_verification",
            "review_priority": "high",
            "vendor_count": 3,
        },
        "recommended_workflow": "vendor_verification",
        "scope_limitations": [
            "Workflow is based on deterministic vendor-risk and entity-relationship evidence only.",
        ],
    }


def _high_severity_finding_state() -> dict:
    return {
        "intent": "fraud_pattern_search",
        "errors": [],
        "findings": [
            {
                "id": "finding-42",
                "title": "Duplicate Payment",
                "severity": "high",
                "confidence": 0.9,
                "summary": "Duplicate payment risk signal with transaction evidence.",
                "evidence": [{"transaction_id": "txn-1"}, {"transaction_id": "txn-2"}],
            }
        ],
    }


def test_create_investigation_in_sensitive_action_types() -> None:
    assert "create_investigation" in SENSITIVE_ACTION_TYPES


def test_create_investigation_emitted_when_workflow_review_priority_is_high() -> None:
    actions = suggested_actions(_high_priority_workflow_state())

    types = [action.type for action in actions]
    assert types[0] == "review_vendor_verification_evidence"
    assert "create_investigation" in types

    investigation = next(action for action in actions if action.type == "create_investigation")
    assert investigation.requires_approval is True


def test_create_investigation_emitted_for_high_severity_finding_with_evidence() -> None:
    actions = suggested_actions(_high_severity_finding_state())

    types = [action.type for action in actions]
    assert types[0] == "review_findings"
    assert "create_investigation" in types

    investigation = next(action for action in actions if action.type == "create_investigation")
    assert investigation.requires_approval is True
    assert investigation.payload["reason_codes"] == ["high_severity_finding_with_evidence"]


def test_create_investigation_not_emitted_below_priority_threshold() -> None:
    state = _high_priority_workflow_state()
    state["next_best_action"]["payload"]["review_priority"] = "medium"
    state["readiness_summary"]["review_priority"] = "medium"

    actions = suggested_actions(state)

    assert [action.type for action in actions] == ["review_vendor_verification_evidence"]
    assert build_create_investigation_action(state) is None


def test_create_investigation_not_emitted_for_high_severity_finding_without_evidence() -> None:
    state = _high_severity_finding_state()
    state["findings"][0]["evidence"] = []

    actions = suggested_actions(state)

    assert [action.type for action in actions] == ["review_findings"]
    assert build_create_investigation_action(state) is None


def test_create_investigation_not_emitted_for_readiness_intents() -> None:
    """Readiness audits emit high-severity findings that describe data gaps, not risk signals."""
    state = _high_severity_finding_state()
    state["intent"] = "relational_readiness_audit"

    assert build_create_investigation_action(state) is None


def test_create_investigation_payload_matches_laravel_contract() -> None:
    action = build_create_investigation_action(_high_severity_finding_state())

    assert action is not None
    payload = action.payload
    # Keys read by AgentActionExecutorService::createInvestigation.
    assert isinstance(payload["title"], str) and payload["title"]
    assert isinstance(payload["summary"], str) and payload["summary"]
    assert payload["category"] in {
        "revenue", "expense", "payroll", "tax", "fraud", "reconciliation",
        "controls", "vendor_payments", "cash_flow", "unsure",
    }
    assert payload["priority"] in {"low", "medium", "high", "critical"}
    assert isinstance(payload["scope_limitations"], list) and payload["scope_limitations"]
    assert isinstance(payload["reason_codes"], list) and payload["reason_codes"]
    assert payload["evidence_refs"] == ["txn-1", "txn-2"]
    assert payload["finding_id"] == "finding-42"
    assert payload["priority"] == "high"


def test_create_investigation_payload_carries_capped_playbook_refs() -> None:
    state = _high_severity_finding_state()
    state["playbook_refs"] = [
        {"playbook_id": "p-1", "title": "High confidence review", "confidence": "high"},
        {"playbook_id": "p-low", "title": "Low confidence review", "confidence": "low"},
        {"playbook_id": "p-2", "title": "Medium confidence review", "confidence": "medium"},
        {"playbook_id": "p-3", "title": "Another high confidence review", "confidence": "high"},
        {"playbook_id": "p-4", "title": "Excess high confidence review", "confidence": "high"},
    ]
    state["retrieval_query"] = "Review duplicate invoice payments."

    action = build_create_investigation_action(state)

    assert action is not None
    assert action.payload["retrieval_query"] == "Review duplicate invoice payments."
    assert action.payload["playbook_refs"] == [
        {"playbook_id": "p-1", "title": "High confidence review", "confidence": "high"},
        {"playbook_id": "p-2", "title": "Medium confidence review", "confidence": "medium"},
        {"playbook_id": "p-3", "title": "Another high confidence review", "confidence": "high"},
    ]


def test_create_investigation_payload_omits_playbooks_without_matching_refs() -> None:
    state = _high_severity_finding_state()
    state["playbook_refs"] = [
        {"playbook_id": "p-low", "title": "Low confidence review", "confidence": "low"},
    ]
    state["retrieval_query"] = "Review duplicate invoice payments."

    action = build_create_investigation_action(state)

    assert action is not None
    assert "playbook_refs" not in action.payload
    assert "retrieval_query" not in action.payload


def test_create_investigation_workflow_payload_uses_canonical_category_and_evidence_refs() -> None:
    action = build_create_investigation_action(_high_priority_workflow_state())

    assert action is not None
    assert action.payload["category"] == "vendor_payments"
    assert action.payload["priority"] == "high"
    # No high-severity finding available: evidence refs fall back to workflow payload ids
    # and no finding_id is asserted.
    assert action.payload["evidence_refs"] == ["vendor-9", "vendor-12"]
    assert "finding_id" not in action.payload
    assert action.payload["scope_limitations"] == [
        "Workflow is based on deterministic vendor-risk and entity-relationship evidence only.",
    ]


def test_create_investigation_rationale_uses_product_language() -> None:
    """Rationale must speak in risk-signal/finding/review terms and never assert wrongdoing."""
    for state in (_high_priority_workflow_state(), _high_severity_finding_state()):
        action = build_create_investigation_action(state)
        assert action is not None
        summary = action.payload["summary"].lower()
        assert any(term in summary for term in ("risk signal", "finding", "review", "scope limitation"))
        assert "fraud" not in summary
        assert "fraud" not in action.payload["title"].lower()


def test_create_investigation_action_requires_approval_at_gate() -> None:
    action = build_create_investigation_action(_high_severity_finding_state())

    assert action is not None
    assert action.requires_approval is True
    # Replicate the gate logic from action_gate_node: the gate hardens it as well.
    action.requires_approval = False
    if action.type in SENSITIVE_ACTION_TYPES:
        action.requires_approval = True
    assert action.requires_approval is True
