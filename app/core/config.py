from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── LLM backend ───────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")

    # Optional: override to point at Ollama or any OpenAI-compatible endpoint.
    # The Anthropic Python SDK respects this env-var natively.
    # Example for Ollama: http://ollama:11434/v1
    anthropic_base_url: str | None = Field(None, env="ANTHROPIC_BASE_URL")

    model: str = Field("claude-opus-4-5", env="MODEL")

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = Field("development", env="APP_ENV")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    # Inside Docker this is /workspace (mounted volume).
    # Locally it defaults to ./.workspace for a consistent sandbox.
    default_base_dir: str = Field(".workspace", env="DEFAULT_BASE_DIR")

    @field_validator("anthropic_base_url", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: str | None) -> str | None:
        """Treat an empty string the same as not set."""
        return v or None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
