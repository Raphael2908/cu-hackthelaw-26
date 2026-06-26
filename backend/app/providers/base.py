from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(Exception):
    """Base for provider failures."""


class RetryableError(ProviderError):
    """429 / 5xx / timeout → safe to retry with backoff."""


class FatalError(ProviderError):
    """4xx validation / policy → fail fast, do not retry."""


# --- Result dataclasses ---


@dataclass
class LLMResult:
    text: str
    model: str
    tokens: int = 0
    provider_job_id: str | None = None


@dataclass
class ResearchDoc:
    title: str
    url: str
    snippet: str
    origin: str  # "web" | "cellar"


@dataclass
class RankedDoc:
    ref_id: str  # candidate id
    rank: int
    relevance_score: float


# --- Interfaces ---


class LLMProvider(ABC):
    """Used by the planner, coordinator, doc, evaluator, and synthesiser agents."""

    @abstractmethod
    def complete(self, *, model: str, system: str, prompt: str) -> LLMResult: ...


class ResearchProvider(ABC):
    """Open-web (Perplexity) and EU corpus (CELLAR) research."""

    @abstractmethod
    def search(self, *, query: str, limit: int = 10) -> list[ResearchDoc]: ...


class RerankProvider(ABC):
    """Orders the candidate pool by relevance to the task."""

    @abstractmethod
    def rerank(self, *, query: str, docs: list[dict]) -> list[RankedDoc]: ...
