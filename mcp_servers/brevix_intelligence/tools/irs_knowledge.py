"""IRS Knowledge MCP tools — Phase 2.

These tools are read-only adapters over Laravel's IRM knowledge endpoints.
Laravel owns all RDS access; this module only calls approved internal agent
tool endpoints and returns source-backed, disclaimer-safe payloads.
"""

from __future__ import annotations

from app.tools.laravel import LaravelToolClient


async def search_irm(
    client: LaravelToolClient,
    topic: str,
    limit: int = 5,
    user_id: str = "mcp_service",
) -> dict:
    return await client.irm_search(topic=topic, limit=limit, user_id=user_id)


async def explain_notice_type(
    client: LaravelToolClient,
    notice_code: str,
    limit: int = 5,
    user_id: str = "mcp_service",
) -> dict:
    return await client.irs_notice_type(code=notice_code, limit=limit, user_id=user_id)


async def summarize_collection_risk(
    client: LaravelToolClient,
    issue_type: str,
    limit: int = 5,
    user_id: str = "mcp_service",
) -> dict:
    return await client.irs_collection_risk(issue_type=issue_type, limit=limit, user_id=user_id)


async def recommend_records_to_gather(
    client: LaravelToolClient,
    issue_type: str,
    limit: int = 5,
    user_id: str = "mcp_service",
) -> dict:
    return await client.irs_records_checklist(issue_type=issue_type, limit=limit, user_id=user_id)
