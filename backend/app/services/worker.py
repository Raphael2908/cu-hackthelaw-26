from __future__ import annotations

from app.config import settings
from app.db.repo import Repo
from app.db.tables import CORPUS, SUBMISSIONS
from app.fixtures import firm_standard
from app.providers.base import LLMProvider
from app.providers.cellar import CellarConnector, get_cellar


def _make_source_lookup(repo: Repo, cellar: CellarConnector):
    """A corpus-first, Cellar-on-miss lookup the worker hands to the model (tool-use). Repo access
    stays here in the service (the provider never touches the repo): a fetched source is cached into
    the corpus so it's reused by the checker and one-click-openable via GET /api/corpus/{id}. May
    raise (Retryable/Provider) on a transient Cellar failure — the provider turns that into a tool
    note rather than aborting the review."""

    def lookup(celex: str) -> dict | None:
        for d in repo.list(CORPUS):
            if d.get("celex") == celex:
                return d
        doc = cellar.fetch_by_celex(celex)
        return repo.insert(CORPUS, doc) if doc else doc

    return lookup


def run_review(
    repo: Repo,
    *,
    task: dict,
    provider: LLMProvider,
    produced_by: str = "ai",
    cellar: CellarConnector | None = None,
) -> dict:
    """The worker (depth): review the task's target document against the firm standard and emit a
    structured submission — findings, the clauses relied on, the citations made, and the audit trail
    of sources used. No verdict (architecture.md §14.1).

    When Cellar is enabled, the worker grounds its citations: the model can fetch real EU sources by
    CELEX (tool-use) while drafting, so it cites actual law instead of a hallucinated CELEX. Off by
    default → the mock/offline path is unchanged and tool-free."""
    cellar = cellar or get_cellar()
    draft = repo.get(CORPUS, task["target_document_id"])
    if not draft:
        raise ValueError(f"Target document {task['target_document_id']} not found.")
    std = repo.get(CORPUS, task.get("firm_standard_id") or firm_standard()["id"]) or firm_standard()

    source_lookup = _make_source_lookup(repo, cellar) if settings.CELLAR_ENABLED else None
    result = provider.review_document(
        draft=draft,
        firm_standard=std,
        process_section=task.get("input_process_section", ""),
        run_index=0,
        source_lookup=source_lookup,
    )
    submission = {
        "task_id": task["id"],
        "produced_by": produced_by,
        "run_index": 0,
        "summary": result.summary,
        "findings": [
            {
                "id": f.id,
                "clause_ref": f.clause_ref,
                "statement": f.statement,
                "citation": f.citation,
            }
            for f in result.findings
        ],
        "citations": [f.citation for f in result.findings if f.citation],
        "clauses_relied_on": result.clauses_relied_on,
        "audit_sources": result.audit_sources,
    }
    return repo.insert(SUBMISSIONS, submission)
