from __future__ import annotations

from app.config import settings
from app.providers import mock
from app.providers.base import LLMProvider, RerankProvider, ResearchProvider


def get_llm_provider() -> LLMProvider:
    if settings.PROVIDER_MODE == "mock":
        return mock.MockLLMProvider()
    from app.providers.real.llm import AnthropicLLMProvider

    return AnthropicLLMProvider()


def get_research_provider() -> ResearchProvider:
    if settings.PROVIDER_MODE == "mock":
        return mock.MockResearchProvider()
    from app.providers.real.research import CompositeResearchProvider

    return CompositeResearchProvider()


def get_rerank_provider() -> RerankProvider:
    if settings.PROVIDER_MODE == "mock":
        return mock.MockRerankProvider()
    if settings.RERANK_MODE == "cohere":
        from app.providers.real.rerank import CohereRerankProvider

        return CohereRerankProvider()
    from app.providers.real.rerank import DeterministicRerankProvider

    return DeterministicRerankProvider()
