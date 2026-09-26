from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHRONO_", env_file=".env", extra="ignore")

    aws_region: str = "us-east-1"
    allowed_account_ids: list[str] = Field(default_factory=list)
    managed_tag_key: str = "chrono-architect:managed"
    managed_tag_value: str = "true"
    approval_ttl_minutes: int = 30
    analysis_days: int = 14
    monitor_seconds: int = 300
    audit_dir: Path = Path("audit-data")

    mcp_command: str = "uvx"
    mcp_args: list[str] = Field(default_factory=lambda: ["awslabs.aws-api-mcp-server@latest"])
    mcp_read_only: bool = True
    mcp_tool: str = "call_aws"
    analyzer_aws_profile: str | None = None
    executor_aws_profile: str | None = None
