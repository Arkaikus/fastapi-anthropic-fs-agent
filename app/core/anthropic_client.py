from __future__ import annotations

from functools import lru_cache

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_anthropic_client() -> AsyncAnthropic:
    """
    Returns a singleton async Anthropic client.

    When ANTHROPIC_BASE_URL is set (for example http://ollama:11434/v1), the
    client targets that endpoint instead of api.anthropic.com so the same
    agent loop can run against Anthropic-hosted or Ollama-backed models.
    """
    kwargs: dict[str, str] = {} 
    if settings.anthropic_api_key:
        kwargs.update({"api_key": settings.anthropic_api_key})
    else:
        logger.warning("Anthropic api key not set")
    if settings.anthropic_base_url:
        kwargs["base_url"] = settings.anthropic_base_url
        logger.info("Anthropic client → custom base_url: %s", settings.anthropic_base_url)
    else:
        logger.info("Anthropic client → Anthropic cloud (default)")
    return AsyncAnthropic(**kwargs)
