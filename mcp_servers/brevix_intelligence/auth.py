from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("brevix.mcp.auth")


def validate_company_id(company_id: str) -> str:
    if not company_id or not isinstance(company_id, str):
        raise ValueError("company_id is required.")
    stripped = company_id.strip()
    if not stripped or len(stripped) > 64:
        raise ValueError("company_id is invalid.")
    return stripped


def log_tool_call(
    *,
    tool_name: str,
    company_id: str,
    user_id: str = "",
    execution_time_ms: float = 0.0,
    status: str = "ok",
) -> None:
    logger.info(
        "mcp_tool_call %s",
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool_name": tool_name,
                "company_id": company_id,
                "user_id": user_id,
                "execution_time_ms": round(execution_time_ms, 2),
                "status": status,
            },
            sort_keys=True,
        ),
    )
