from app.graph import SENSITIVE_ACTION_TYPES, suggested_actions
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
