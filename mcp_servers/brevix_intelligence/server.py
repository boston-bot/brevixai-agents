"""Brevix Intelligence MCP Server — Phase 1: Fraud Intelligence.

Runs as a stdio subprocess. LangGraph agents connect via langchain-mcp-adapters.

Usage:
    python -m mcp_servers.brevix_intelligence.server
"""

from __future__ import annotations

import time
from typing import Any

from mcp.server.fastmcp import FastMCP

from .auth import log_tool_call, validate_company_id
from .client import get_laravel_client
from .tools.cash_burn import calculate_cash_burn
from .tools.control_weaknesses import summarize_control_weaknesses
from .tools.dormant_vendor import detect_dormant_vendor_reactivation
from .tools.duplicate_payments import detect_duplicate_payments
from .tools.irs_knowledge import (
    explain_notice_type,
    recommend_records_to_gather,
    search_irm,
    summarize_collection_risk,
)
from .tools.vendor_concentration import analyze_vendor_concentration

mcp = FastMCP(
    "brevix_intelligence",
    instructions=(
        "Brevix AI financial intelligence tools. "
        "Deterministic fraud detection, risk analysis, and IRS procedural intelligence. "
        "All tools are read-only and return structured JSON findings with evidence."
    ),
)


@mcp.tool()
async def detect_duplicate_payments_tool(
    company_id: str,
    start_date: str,
    end_date: str,
    user_id: str = "",
) -> dict[str, Any]:
    """Detect likely duplicate vendor payments within a date range.

    Compares transactions by vendor name, amount, date proximity, invoice number,
    and memo similarity using deterministic scoring. Returns structured findings
    with confidence scores and evidence.

    Args:
        company_id: The company to analyze. Required.
        start_date: Start of the date range (YYYY-MM-DD).
        end_date: End of the date range (YYYY-MM-DD).
        user_id: Optional caller identity for audit logging.
    """
    company_id = validate_company_id(company_id)
    client = get_laravel_client()
    start = time.perf_counter()

    result = await detect_duplicate_payments(client, company_id, start_date, end_date, user_id=user_id or "mcp_service")

    log_tool_call(
        tool_name="detect_duplicate_payments",
        company_id=company_id,
        user_id=user_id,
        execution_time_ms=(time.perf_counter() - start) * 1000,
        status=result.status,
    )
    return result.model_dump()


@mcp.tool()
async def analyze_vendor_concentration_tool(
    company_id: str,
    start_date: str,
    end_date: str,
    user_id: str = "",
) -> dict[str, Any]:
    """Identify vendors receiving an unusually high percentage of company spend.

    Calculates each vendor's share of total outflow and flags any vendor whose
    concentration exceeds the configured threshold (default: 30%).

    Args:
        company_id: The company to analyze. Required.
        start_date: Start of the date range (YYYY-MM-DD).
        end_date: End of the date range (YYYY-MM-DD).
        user_id: Optional caller identity for audit logging.
    """
    company_id = validate_company_id(company_id)
    client = get_laravel_client()
    start = time.perf_counter()

    result = await analyze_vendor_concentration(client, company_id, start_date, end_date, user_id=user_id or "mcp_service")

    log_tool_call(
        tool_name="analyze_vendor_concentration",
        company_id=company_id,
        user_id=user_id,
        execution_time_ms=(time.perf_counter() - start) * 1000,
        status=result.status,
    )
    return result.model_dump()


@mcp.tool()
async def detect_dormant_vendor_reactivation_tool(
    company_id: str,
    user_id: str = "",
) -> dict[str, Any]:
    """Detect vendors that were dormant for a long period and then became active again.

    Scans vendor transaction history for gaps exceeding the dormancy threshold
    (default: 90 days) followed by new activity. Returns findings with the gap
    length and surrounding transactions as evidence.

    Args:
        company_id: The company to analyze. Required.
        user_id: Optional caller identity for audit logging.
    """
    company_id = validate_company_id(company_id)
    client = get_laravel_client()
    start = time.perf_counter()

    result = await detect_dormant_vendor_reactivation(client, company_id, user_id=user_id or "mcp_service")

    log_tool_call(
        tool_name="detect_dormant_vendor_reactivation",
        company_id=company_id,
        user_id=user_id,
        execution_time_ms=(time.perf_counter() - start) * 1000,
        status=result.status,
    )
    return result.model_dump()


@mcp.tool()
async def calculate_cash_burn_tool(
    company_id: str,
    user_id: str = "",
) -> dict[str, Any]:
    """Analyze cash outflow trends to detect burn acceleration or unusual spend increases.

    Aggregates monthly outflows and detects consistent month-over-month increases.
    Returns findings when burn rate is accelerating, with monthly trend data as evidence.

    Args:
        company_id: The company to analyze. Required.
        user_id: Optional caller identity for audit logging.
    """
    company_id = validate_company_id(company_id)
    client = get_laravel_client()
    start = time.perf_counter()

    result = await calculate_cash_burn(client, company_id, user_id=user_id or "mcp_service")

    log_tool_call(
        tool_name="calculate_cash_burn",
        company_id=company_id,
        user_id=user_id,
        execution_time_ms=(time.perf_counter() - start) * 1000,
        status=result.status,
    )
    return result.model_dump()


@mcp.tool()
async def summarize_control_weaknesses_tool(
    company_id: str,
    user_id: str = "",
) -> dict[str, Any]:
    """Identify operational control weaknesses such as missing approvals, missing
    documentation, and approval concentration (segregation of duties issues).

    Only analyzes transactions at or above the configured minimum amount threshold
    (default: $1,000). Returns separate findings for each weakness type detected.

    Args:
        company_id: The company to analyze. Required.
        user_id: Optional caller identity for audit logging.
    """
    company_id = validate_company_id(company_id)
    client = get_laravel_client()
    start = time.perf_counter()

    result = await summarize_control_weaknesses(client, company_id, user_id=user_id or "mcp_service")

    log_tool_call(
        tool_name="summarize_control_weaknesses",
        company_id=company_id,
        user_id=user_id,
        execution_time_ms=(time.perf_counter() - start) * 1000,
        status=result.status,
    )
    return result.model_dump()


@mcp.tool()
async def search_irm_tool(topic: str, limit: int = 5, user_id: str = "") -> dict[str, Any]:
    """Search parsed Internal Revenue Manual sections by topic."""
    client = get_laravel_client()
    start = time.perf_counter()

    result = await search_irm(client, topic, limit=limit, user_id=user_id or "mcp_service")

    log_tool_call(
        tool_name="search_irm",
        company_id="global",
        user_id=user_id,
        execution_time_ms=(time.perf_counter() - start) * 1000,
        status=result.get("status", "ok"),
    )
    return result


@mcp.tool()
async def explain_notice_type_tool(notice_code: str, limit: int = 5, user_id: str = "") -> dict[str, Any]:
    """Explain an IRS notice type using source-backed IRM sections."""
    client = get_laravel_client()
    start = time.perf_counter()

    result = await explain_notice_type(client, notice_code, limit=limit, user_id=user_id or "mcp_service")

    log_tool_call(
        tool_name="explain_notice_type",
        company_id="global",
        user_id=user_id,
        execution_time_ms=(time.perf_counter() - start) * 1000,
        status=result.get("status", "ok"),
    )
    return result


@mcp.tool()
async def summarize_collection_risk_tool(issue_type: str, limit: int = 5, user_id: str = "") -> dict[str, Any]:
    """Summarize IRS collection risk for an issue type using IRM sources."""
    client = get_laravel_client()
    start = time.perf_counter()

    result = await summarize_collection_risk(client, issue_type, limit=limit, user_id=user_id or "mcp_service")

    log_tool_call(
        tool_name="summarize_collection_risk",
        company_id="global",
        user_id=user_id,
        execution_time_ms=(time.perf_counter() - start) * 1000,
        status=result.get("status", "ok"),
    )
    return result


@mcp.tool()
async def recommend_records_to_gather_tool(issue_type: str, limit: int = 5, user_id: str = "") -> dict[str, Any]:
    """Recommend records to gather for an IRS issue type using IRM sources."""
    client = get_laravel_client()
    start = time.perf_counter()

    result = await recommend_records_to_gather(client, issue_type, limit=limit, user_id=user_id or "mcp_service")

    log_tool_call(
        tool_name="recommend_records_to_gather",
        company_id="global",
        user_id=user_id,
        execution_time_ms=(time.perf_counter() - start) * 1000,
        status=result.get("status", "ok"),
    )
    return result


if __name__ == "__main__":
    mcp.run()
