from __future__ import annotations

from app.core.celery_app import celery_app
from app.db.repo import get_repo
from app.providers.factory import get_llm_provider
from app.services import coordinator


@celery_app.task(name="dispatch.run", bind=True, max_retries=2, default_retry_delay=5)
def run_dispatch_task(self, task_id: str) -> None:
    """Off-request execution of one AI/hybrid task's worker→checker→ranker pipeline.

    Only the serializable `task_id` crosses the process boundary; the worker rebuilds the repo and
    provider from their per-process factories (`get_repo()` opens a `SqliteRepo` against the shared
    file; `get_llm_provider()` is cheap). `_background_dispatch` already wraps the pipeline in
    fail-safe escalation (architecture.md §14.6), so a failure escalates to a human and is recorded
    in the audit log — never silently dropped. The Celery `max_retries` covers transient broker /
    infrastructure errors before that safety net is reached.
    """
    repo, provider = get_repo(), get_llm_provider()
    coordinator._background_dispatch(repo, task_id, provider)
