from __future__ import annotations

from app.providers.base import (
    LLMProvider,
    LLMResult,
    RankedDoc,
    RerankProvider,
    ResearchDoc,
    ResearchProvider,
)


class MockLLMProvider(LLMProvider):
    """Deterministic canned completions — no network. Echoes a short, structured response so the
    pipeline produces stable, inspectable output in mock mode."""

    def complete(self, *, model: str, system: str, prompt: str) -> LLMResult:
        head = prompt.strip().splitlines()[0] if prompt.strip() else ""
        text = f"[mock:{model}] {head[:200]}"
        return LLMResult(text=text, model=model, tokens=len(prompt.split()))


class MockResearchProvider(ResearchProvider):
    def search(self, *, query: str, limit: int = 10) -> list[ResearchDoc]:
        n = min(limit, 4)
        docs: list[ResearchDoc] = []
        for i in range(n):
            origin = "cellar" if i % 2 == 0 else "web"
            docs.append(
                ResearchDoc(
                    title=f"[mock {origin}] result {i + 1} for {query[:40]}",
                    url=f"https://example.test/{origin}/{i + 1}",
                    snippet=f"Canned {origin} snippet {i + 1} relevant to: {query[:80]}",
                    origin=origin,
                )
            )
        return docs


class MockRerankProvider(RerankProvider):
    def rerank(self, *, query: str, docs: list[dict]) -> list[RankedDoc]:
        # Deterministic: preserve incoming order, descending relevance.
        total = len(docs)
        return [
            RankedDoc(
                ref_id=d["id"],
                rank=i + 1,
                relevance_score=round(1.0 - i / max(total, 1), 4),
            )
            for i, d in enumerate(docs)
        ]
