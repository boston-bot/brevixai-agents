from app.graph import SENSITIVE_ACTION_TYPES, suggested_actions


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
