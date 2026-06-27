from __future__ import annotations

from app.config import settings
from app.core.stream import publish_delta
from app.db.repo import Repo
from app.db.tables import CORPUS, SUBMISSIONS
from app.providers.base import LLMProvider
from app.providers.cellar import CellarConnector, get_cellar
from app.services.task_spec import build_task_spec


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
    """The worker (depth): execute the task the planner delegated and emit a structured submission.
    The task is no longer fixed to "review against the firm standard" — its kind, instruction and
    checklist come from the process-map section (architecture.md §6) via ``build_task_spec``. The
    submission always carries the universal ``findings`` (the checkable claims the checker reads),
    plus the type-specific ``payload`` + ``output_kind``. No verdict (architecture.md §14.1).

    When Cellar is enabled, the worker grounds its citations: the model can fetch real EU sources by
    CELEX (tool-use) while working, so it cites actual law instead of a hallucinated CELEX. Off by
    default → the mock/offline path is unchanged and tool-free."""
    cellar = cellar or get_cellar()
    spec = build_task_spec(repo, task)
    if not spec.documents:
        raise ValueError(f"Target document {task.get('target_document_id')} not found.")

    source_lookup = _make_source_lookup(repo, cellar) if settings.CELLAR_ENABLED else None
    # Relay the model's thinking to the cockpit's "With AI" lane only when we're running off-request
    # (a real Celery worker with Redis); inline/offline dispatch stays callback-free. Best-effort
    # and transient — never persisted into the submission or the audit record (architecture.md §14).
    on_delta = (
        (lambda text: publish_delta(task["id"], {"type": "delta", "text": text}))
        if settings.ASYNC_DISPATCH
        else None
    )
    result = provider.run_task(
        **spec.run_kwargs(run_index=0, source_lookup=source_lookup), on_delta=on_delta
    )
    if on_delta is not None:
        publish_delta(task["id"], {"type": "done"})  # closes the SSE stream cleanly
    submission = {
        "task_id": task["id"],
        "produced_by": produced_by,
        "run_index": 0,
        "summary": result.summary,
        "output_kind": result.output_kind,
        "payload": result.payload,
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
