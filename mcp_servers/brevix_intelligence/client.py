from __future__ import annotations

from app.tools.laravel import LaravelToolClient
from .config import get_mcp_settings

_MCP_USER_ID = "mcp_service"


def get_laravel_client() -> LaravelToolClient:
    settings = get_mcp_settings()
    return LaravelToolClient(
        base_url=settings.laravel_base_url,
        tool_key=settings.laravel_tool_key,
        timeout_seconds=settings.http_timeout_seconds,
    )


async def fetch_transactions(
    client: LaravelToolClient,
    company_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    user_id: str = _MCP_USER_ID,
) -> list[dict]:
    result = await client.transaction_lookup(
        company_id=company_id,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return result.get("transactions", [])
