from __future__ import annotations

from app.celery_app import celery_app
from app.config import settings
from app.db.repo import get_repo
from app.providers.base import RetryableError
from app.providers.factory import (
    get_llm_provider,
    get_rerank_provider,
    get_research_provider,
)
from app.tasks.common import agent_run

_RETRY = {
    "autoretry_for": (RetryableError,),
    "retry_backoff": True,
    "retry_jitter": True,
    "max_retries": settings.TASK_MAX_RETRIES,
}


def _query_for(task: dict) -> str:
    return f"{task.get('title', '')}\n{task.get('brief', '')}".strip()


@celery_app.task(name="tasks.plan", **_RETRY)
def plan(task_id: str) -> str:
    """Planner: decompose the brief into a plan (plan.md)."""
    repo = get_repo()
    repo.update_task(task_id, status="planning")
    task = repo.get_task(task_id)
    if task is None:
        return task_id
    with agent_run(task_id, "planner") as run:
        llm = get_llm_provider()
        res = llm.complete(
            model=settings.LLM_MODEL_PLANNER,
            system="You are a legal planning agent. Produce an ordered plan for the task.",
            prompt=f"Task type: {task['task_type']}\nBrief: {task['brief']}",
        )
        repo.update_task(task_id, plan_md=res.text)
        repo.update_agent_run(run["id"], output={"plan_md": res.text}, cost=0.0)
    return task_id


@celery_app.task(name="tasks.coordinate", **_RETRY)
def coordinate(task_id: str) -> str:
    """Coordinator: marshal the plan into research/read steps. (Linear chain in the scaffold.)"""
    repo = get_repo()
    repo.update_task(task_id, status="researching")
    with agent_run(task_id, "coordinator"):
        pass
    return task_id


@celery_app.task(name="tasks.web_research", **_RETRY)
def web_research(task_id: str) -> str:
    """Web agent: research the open web (Perplexity) + EU corpus (CELLAR)."""
    repo = get_repo()
    task = repo.get_task(task_id)
    if task is None:
        return task_id
    with agent_run(task_id, "web") as run:
        research = get_research_provider()
        docs = research.search(query=_query_for(task), limit=10)
        for d in docs:
            repo.create_candidate(
                task_id=task_id,
                origin=d.origin,
                title=d.title,
                url=d.url,
                snippet=d.snippet,
                agent_run_id=run["id"],
            )
        repo.update_agent_run(run["id"], output={"found": len(docs)})
    return task_id


@celery_app.task(name="tasks.doc_read", **_RETRY)
def doc_read(task_id: str) -> str:
    """Doc agent: read lawyer-uploaded documents into the candidate pool."""
    repo = get_repo()
    with agent_run(task_id, "doc") as run:
        documents = repo.list_documents(task_id)
        for doc in documents:
            # Real impl parses the file (PDF/DOCX → passages); mock stores a placeholder.
            repo.create_candidate(
                task_id=task_id,
                origin="upload",
                title=doc.get("filename"),
                url=None,
                snippet=f"[uploaded document: {doc.get('filename')}]",
                source_document_id=doc["id"],
                agent_run_id=run["id"],
            )
        repo.update_agent_run(run["id"], output={"documents": len(documents)})
    return task_id


@celery_app.task(name="tasks.rerank", **_RETRY)
def rerank(task_id: str) -> str:
    """Reranker agent: order the whole candidate pool by relevance."""
    repo = get_repo()
    repo.update_task(task_id, status="ranking")
    task = repo.get_task(task_id)
    if task is None:
        return task_id
    with agent_run(task_id, "reranker") as run:
        candidates = repo.list_candidates(task_id)
        provider = get_rerank_provider()
        ranked = provider.rerank(query=_query_for(task), docs=candidates)
        for r in ranked:
            repo.update_candidate(r.ref_id, rank=r.rank, relevance_score=r.relevance_score)
        repo.update_agent_run(run["id"], output={"ranked": len(ranked)})
    return task_id


@celery_app.task(name="tasks.evaluate", **_RETRY)
def evaluate(task_id: str) -> str:
    """Evaluator agent: scrutinise the top-N ranked documents (N = task.eval_doc_count)."""
    repo = get_repo()
    repo.update_task(task_id, status="evaluating")
    task = repo.get_task(task_id)
    if task is None:
        return task_id
    n = int(task.get("eval_doc_count") or settings.DEFAULT_EVAL_DOC_COUNT)
    with agent_run(task_id, "evaluator") as run:
        candidates = repo.list_candidates(task_id)  # sorted by rank
        top = [c for c in candidates if c.get("rank") is not None][:n]
        llm = get_llm_provider()
        for i, c in enumerate(top):
            res = llm.complete(
                model=settings.LLM_MODEL_EVAL,
                system="You are a legal evaluator. Assess relevance, risk, and uncertainty.",
                prompt=f"Task: {task['brief']}\nDocument: {c.get('snippet')}",
            )
            repo.update_candidate(
                c["id"],
                evaluated=True,
                eval_relevance=c.get("relevance_score"),
                eval_risk=round(0.2 + i * 0.05, 3),
                eval_uncertainty=round(max(0.05, 0.3 - i * 0.02), 3),
                eval_notes=res.text,
                use_in_synthesis=True,
            )
        repo.update_agent_run(run["id"], output={"evaluated": len(top)})
    return task_id


@celery_app.task(name="tasks.synthesize", **_RETRY)
def synthesize(task_id: str) -> str:
    """Synthesiser agent: compose the argument from the evaluated evidence."""
    repo = get_repo()
    repo.update_task(task_id, status="synthesizing")
    task = repo.get_task(task_id)
    if task is None:
        return task_id
    with agent_run(task_id, "synthesiser") as run:
        evidence = [c for c in repo.list_candidates(task_id) if c.get("use_in_synthesis")]
        bullet = "\n".join(f"- {c.get('title')}: {c.get('snippet')}" for c in evidence)
        llm = get_llm_provider()
        res = llm.complete(
            model=settings.LLM_MODEL_AGENT,
            system="You are a legal synthesiser. Draft the argument from the evidence.",
            prompt=f"Brief: {task['brief']}\nEvidence:\n{bullet}",
        )
        previous = repo.latest_output(task_id)
        version = (previous.get("version", 0) + 1) if previous else 1
        repo.create_output(task_id=task_id, version=version, content_md=res.text)
        repo.update_task(task_id, status="complete")
        repo.update_agent_run(run["id"], output={"version": version})
    return task_id
