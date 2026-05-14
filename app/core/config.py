from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    anthropic_base_url: str | None = Field(None, env="ANTHROPIC_BASE_URL")
    model: str = Field("claude-opus-4-5", env="MODEL")
    agent_max_tokens: int = Field(2048, env="AGENT_MAX_TOKENS")
    agent_max_iterations: int = Field(8, env="AGENT_MAX_ITERATIONS")
    rag_enabled: bool = Field(True, env="RAG_ENABLED")
    rag_max_files: int = Field(80, env="RAG_MAX_FILES")
    rag_max_file_chars: int = Field(4000, env="RAG_MAX_FILE_CHARS")
    rag_query_results: int = Field(5, env="RAG_QUERY_RESULTS")
    chroma_host: str = Field("localhost", env="CHROMA_HOST")
    chroma_port: int = Field(8000, env="CHROMA_PORT")
    # Preindex options: list of workspace paths to prewarm at startup
    rag_preindex_enabled: bool = Field(False, env="RAG_PREINDEX_ENABLED")
    rag_preindex_paths: list[str] = Field([], env="RAG_PREINDEX_PATHS")
    rag_background_workers: int = Field(1, env="RAG_BACKGROUND_WORKERS")
    agent_system_prompt: str = Field(
        (
            "You are a sandboxed filesystem agent. "
            "Use the available filesystem tools when they help complete the task, "
            "stay inside the provided workspace, and finish with a concise final answer."
        ),
        env="AGENT_SYSTEM_PROMPT",
    )

    app_env: str = Field("development", env="APP_ENV")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    default_base_dir: str = Field(".workspace", env="DEFAULT_BASE_DIR")

    @field_validator("anthropic_base_url", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: str | None) -> str | None:
        return v or None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
