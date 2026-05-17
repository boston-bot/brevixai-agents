from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    agent_service_key: str = Field(default="", alias="BREVIX_AGENT_SERVICE_KEY")
    laravel_base_url: str = Field(default="http://localhost:8000", alias="BREVIX_LARAVEL_BASE_URL")
    laravel_agent_tool_key: str = Field(default="", alias="BREVIX_LARAVEL_AGENT_TOOL_KEY")
    http_timeout_seconds: float = Field(default=20.0, alias="HTTP_TIMEOUT_SECONDS")
    log_level: str = Field(default="info", alias="LOG_LEVEL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
