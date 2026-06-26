from __future__ import annotations

from app.config import settings
from app.providers.base import LLMProvider, LLMResult


class AnthropicLLMProvider(LLMProvider):
    """Real Anthropic Claude provider. STUB — wire the SDK before flipping PROVIDER_MODE=real.

    Raises loudly at construction if the key is missing (no silent fallback to mock)."""

    def __init__(self) -> None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is required for the real LLM provider.")
        # from anthropic import Anthropic
        # self._client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def complete(self, *, model: str, system: str, prompt: str) -> LLMResult:
        raise NotImplementedError(
            "AnthropicLLMProvider.complete is not wired yet. "
            "Implement with the anthropic SDK (messages.create)."
        )
