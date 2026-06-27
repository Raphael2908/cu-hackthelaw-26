from __future__ import annotations

from app.config import settings
from app.providers.base import LLMProvider
from app.providers.mock import MockLLMProvider


def get_llm_provider() -> LLMProvider:
    """Mock unless PROVIDER_MODE=real. The real impl is imported lazily so the mock path never pulls
    the Anthropic SDK, and the real impl raises if its key is missing — no silent fallback."""
    if settings.PROVIDER_MODE == "mock":
        return MockLLMProvider()
    from app.providers.real.anthropic_llm import AnthropicLLMProvider

    return AnthropicLLMProvider()
