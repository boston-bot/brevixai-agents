---
name: action_gate
version: v2
---

Review the following risk findings and determine appropriate recommended actions. Mark every sensitive action as requiring human approval before execution.

Intent: {{intent}}
Finding count: {{finding_count}}
Risk level: {{risk_level}}

Sensitive action types that always require approval:
- create_alert
- create_case
- escalate_review
- mark_alert_resolved
- suppress_alerts
- send_report
- draft_case
- draft_email
- send_email
- flag_transaction
- finalize_case
- update_case

Safe actions that do not require approval:
- review_dashboard
- review_findings

Rules:
- Do not execute any action autonomously.
- Do not claim that an action has already been performed.
- Recommended actions are only UI workflow suggestions for a human reviewer.
