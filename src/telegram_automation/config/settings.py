from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets are loaded only from the environment/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_api_id: int | None = None
    telegram_api_hash: SecretStr | None = None
    database_url: str = "sqlite+aiosqlite:///./data/telegram_automation.sqlite3"
    session_dir: Path = Path("./sessions")
    log_level: str = "INFO"
    max_concurrency: int = Field(default=2, ge=1, le=20)
    account_concurrency: int = Field(default=1, ge=1, le=1)
    min_request_interval_seconds: float = Field(default=1.0, ge=0.1, le=300.0)
    max_retries: int = Field(default=3, ge=0, le=10)
    max_flood_wait_seconds: int = Field(default=3600, ge=1, le=86_400)

    @field_validator("telegram_api_id")
    @classmethod
    def positive_api_id(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("TELEGRAM_API_ID must be positive")
        return value

    def require_telegram_credentials(self) -> tuple[int, str]:
        if self.telegram_api_id is None or self.telegram_api_hash is None:
            raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be configured")
        return self.telegram_api_id, self.telegram_api_hash.get_secret_value()
