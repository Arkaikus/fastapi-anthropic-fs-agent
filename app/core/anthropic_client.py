from __future__ import annotations

from functools import lru_cache

import anthropic

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_anthropic_client() -> anthropic.Anthropic:
    """
    Returns a singleton Anthropic client.

    When ANTHROPIC_BASE_URL is set (e.g. http://ollama:11434/v1), the client
    transparently targets that endpoint instead of api.anthropic.com.
    The Anthropic SDK is OpenAI-API-compatible when base_url is overridden,
    which is exactly the interface Ollama exposes.
    """
    kwargs: dict = {"api_key": settings.anthropic_api_key}
    if settings.anthropic_base_url:
        kwargs["base_url"] = settings.anthropic_base_url
        logger.info("Anthropic client → custom base_url: %s", settings.anthropic_base_url)
    else:
        logger.info("Anthropic client → Anthropic cloud (default)")
    return anthropic.Anthropic(**kwargs)
