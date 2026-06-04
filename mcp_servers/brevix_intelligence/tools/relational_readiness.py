from __future__ import annotations

from typing import Any

from app.relational_readiness import build_relational_readiness_audit


def audit_relational_readiness(data_sources: dict[str, Any]) -> dict[str, Any]:
    """Audit Phase 5 relational data readiness from agent-visible payloads."""
    return build_relational_readiness_audit(data_sources)
