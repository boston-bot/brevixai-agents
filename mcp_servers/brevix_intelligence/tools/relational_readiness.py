from __future__ import annotations

from typing import Any

from app.relational_contract_adoption import build_relational_contract_adoption_report
from app.relational_readiness import build_relational_readiness_audit


def audit_relational_readiness(data_sources: dict[str, Any]) -> dict[str, Any]:
    """Audit Phase 5 relational data readiness from agent-visible payloads."""
    return build_relational_readiness_audit(data_sources)


def build_relational_contract_adoption(
    data_sources: dict[str, Any],
    tool_failures: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create endpoint-level Laravel payload adoption tasks from agent-visible payloads."""
    audit = build_relational_readiness_audit(data_sources)
    return build_relational_contract_adoption_report(audit, tool_failures=tool_failures)
