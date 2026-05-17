---
name: action_gate
version: v1
---

Review the following risk findings and determine appropriate recommended actions. Mark any sensitive actions as requiring human approval before execution.

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

Safe actions that do not require approval:
- review_dashboard
- review_findings

Return a list of recommended actions with their approval requirements. Do not execute any action autonomously.
