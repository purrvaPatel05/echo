from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from environment variables / .env. Never hard-code secrets."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5"
    database_url: str = "postgresql+asyncpg://echo:echo@localhost:5432/echo"
    redis_url: str = "redis://localhost:6379/0"
    # "inline" runs parse/match after the HTTP response inside the API process (no Redis needed);
    # "celery" hands them to a worker: `celery -A app.celery_app worker`.
    job_backend: Literal["inline", "celery"] = "inline"
    claude_timeout_seconds: float = 60.0
    # Ask the API to re-run a safety-declined request on another model server-side.
    claude_server_fallback: bool = True


settings = Settings()
