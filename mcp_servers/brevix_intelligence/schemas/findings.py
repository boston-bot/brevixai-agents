from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .evidence import EvidenceItem


class Finding(BaseModel):
    risk_type: str
    severity: Literal["info", "low", "medium", "high", "critical"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool_name: str
    company_id: str
    findings: list[Finding] = Field(default_factory=list)
    analyzed_at: str
    status: Literal["ok", "no_data", "error"] = "ok"
    error: str | None = None
