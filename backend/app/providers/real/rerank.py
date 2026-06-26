from __future__ import annotations

from app.config import settings
from app.providers.base import RankedDoc, RerankProvider


class DeterministicRerankProvider(RerankProvider):
    """Lexical/recency/source-authority scorer. STUB — implement the scoring heuristic."""

    def rerank(self, *, query: str, docs: list[dict]) -> list[RankedDoc]:
        raise NotImplementedError(
            "DeterministicRerankProvider.rerank is not wired yet. "
            "Score by lexical overlap with the query + source authority + recency."
        )


class CohereRerankProvider(RerankProvider):
    """Learned reranker via Cohere Rerank. STUB — wire before using RERANK_MODE=cohere."""

    def __init__(self) -> None:
        if not settings.COHERE_API_KEY:
            raise RuntimeError("COHERE_API_KEY is required for the Cohere reranker.")

    def rerank(self, *, query: str, docs: list[dict]) -> list[RankedDoc]:
        raise NotImplementedError(
            "CohereRerankProvider.rerank is not wired yet. Call the Cohere rerank endpoint."
        )
