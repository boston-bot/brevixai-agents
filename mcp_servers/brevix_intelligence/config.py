from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Laravel API — shares the same env vars as the main app
    laravel_base_url: str = Field(default="http://localhost:8000", alias="BREVIX_LARAVEL_BASE_URL")
    laravel_tool_key: str = Field(default="", alias="BREVIX_LARAVEL_AGENT_TOOL_KEY")
    http_timeout_seconds: float = Field(default=20.0, alias="HTTP_TIMEOUT_SECONDS")
    app_env: str = Field(default="local", alias="APP_ENV")

    # Duplicate payment thresholds
    duplicate_amount_tolerance: float = Field(default=0.01, alias="MCP_DUPLICATE_AMOUNT_TOLERANCE")
    duplicate_date_window_days: int = Field(default=30, alias="MCP_DUPLICATE_DATE_WINDOW_DAYS")

    # Vendor concentration threshold (fraction of total spend)
    vendor_concentration_threshold: float = Field(default=0.30, alias="MCP_VENDOR_CONCENTRATION_THRESHOLD")

    # Dormant vendor gap in days before reactivation is flagged
    dormant_vendor_days: int = Field(default=90, alias="MCP_DORMANT_VENDOR_DAYS")

    # Control weakness: minimum amount to flag missing approvals/docs
    control_weakness_min_amount: float = Field(default=1000.0, alias="MCP_CONTROL_WEAKNESS_MIN_AMOUNT")
    # Control weakness: single-approver dominance threshold
    control_weakness_approver_dominance: float = Field(default=0.80, alias="MCP_CONTROL_WEAKNESS_APPROVER_DOMINANCE")

    # Maximum transactions to fetch per tool call
    max_transactions: int = Field(default=500, alias="MCP_MAX_TRANSACTIONS")


@lru_cache
def get_mcp_settings() -> MCPSettings:
    return MCPSettings()
