from __future__ import annotations

from celery import chain

from app.tasks.agents import (
    coordinate,
    doc_read,
    evaluate,
    plan,
    rerank,
    synthesize,
    web_research,
)


def enqueue_pipeline(task_id: str) -> None:
    """Build and enqueue the agent chain. Each stage reads its inputs from Postgres by task_id,
    so any in-order subset chains cleanly and big payloads never hit the broker."""
    chain(
        plan.s(task_id),
        coordinate.s(),
        web_research.s(),
        doc_read.s(),
        rerank.s(),
        evaluate.s(),
        synthesize.s(),
    ).apply_async()
