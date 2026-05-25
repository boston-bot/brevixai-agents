from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    agent_service_key: str = Field(default="", alias="BREVIX_AGENT_SERVICE_KEY")
    orchestrator_api_token: str = Field(default="", alias="ORCHESTRATOR_API_TOKEN")
    laravel_base_url: str = Field(default="http://localhost:8000", alias="BREVIX_LARAVEL_BASE_URL")
    laravel_agent_tool_key: str = Field(default="", alias="BREVIX_LARAVEL_AGENT_TOOL_KEY")
    http_timeout_seconds: float = Field(default=20.0, alias="HTTP_TIMEOUT_SECONDS")
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    langchain_tracing_v2: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str = Field(default="", alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="brevix-ai", alias="LANGCHAIN_PROJECT")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    graph_version: str = Field(default="phase-2-observability-v1", alias="BREVIX_AGENT_GRAPH_VERSION")
    feature_flags: str = Field(default="", alias="BREVIX_AGENT_FEATURE_FLAGS")
    model_provider: str = Field(default="deterministic", alias="BREVIX_AGENT_MODEL_PROVIDER")
    model_name: str = Field(default="deterministic-risk-v1", alias="BREVIX_AGENT_MODEL_NAME")
    model_timeout_seconds: float = Field(default=30.0, alias="BREVIX_AGENT_MODEL_TIMEOUT_SECONDS")
    structured_outputs: bool = Field(default=True, alias="BREVIX_AGENT_STRUCTURED_OUTPUTS")

    allowed_origins: str = Field(default="", alias="ORCHESTRATOR_ALLOWED_ORIGINS")
    approval_required_tools: str = Field(
        default="draft_case,draft_email,send_email,flag_transaction,finalize_case,update_case",
        alias="ORCHESTRATOR_APPROVAL_REQUIRED_TOOLS",
    )
    checkpointer: str = Field(default="", alias="ORCHESTRATOR_CHECKPOINTER")

    @property
    def langsmith_enabled(self) -> bool:
        return self.langchain_tracing_v2 and bool(self.langchain_api_key)

    @property
    def feature_flag_list(self) -> list[str]:
        return [flag.strip() for flag in self.feature_flags.split(",") if flag.strip()]

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def approval_required_tools_list(self) -> list[str]:
        return [t.strip() for t in self.approval_required_tools.split(",") if t.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"production", "prod"}

    @model_validator(mode="after")
    def use_orchestrator_api_token_alias(self) -> "Settings":
        if not self.agent_service_key and self.orchestrator_api_token:
            self.agent_service_key = self.orchestrator_api_token
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
