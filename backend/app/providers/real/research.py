from __future__ import annotations

from app.config import settings
from app.providers.base import ResearchDoc, ResearchProvider


class CompositeResearchProvider(ResearchProvider):
    """Real research: open web via Perplexity + EU corpus via CELLAR. STUB — wire before
    flipping PROVIDER_MODE=real."""

    def __init__(self) -> None:
        if not settings.PERPLEXITY_API_KEY:
            raise RuntimeError("PERPLEXITY_API_KEY is required for the real research provider.")

    def search(self, *, query: str, limit: int = 10) -> list[ResearchDoc]:
        raise NotImplementedError(
            "CompositeResearchProvider.search is not wired yet. "
            "Query Perplexity (open web) + CELLAR SPARQL/REST and merge results."
        )
