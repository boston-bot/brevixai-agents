"""Tests for the standalone Brevix Intelligence MCP server."""

from __future__ import annotations

import pytest

from mcp_servers.brevix_intelligence.server import mcp


@pytest.mark.asyncio
async def test_mcp_server_registers_intelligence_tools() -> None:
    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert {
        "detect_duplicate_payments_tool",
        "analyze_vendor_concentration_tool",
        "detect_dormant_vendor_reactivation_tool",
        "calculate_cash_burn_tool",
        "summarize_control_weaknesses_tool",
        "search_irm_tool",
        "get_irm_section_tool",
        "explain_notice_type_tool",
        "summarize_collection_risk_tool",
        "recommend_records_to_gather_tool",
    }.issubset(tool_names)
