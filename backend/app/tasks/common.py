from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from app.core.context import set_agent_run_id, set_task_id
from app.db.repo import get_repo


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def agent_run(task_id: str, agent: str, **input_fields: Any) -> Iterator[dict]:
    """Lifecycle wrapper for one agent stage: creates an `agent_runs` row, flips it
    running → succeeded|failed, and binds correlation context. Yields the run row so the caller
    can stash `output`/`cost` via `get_repo().update_agent_run(...)`."""
    repo = get_repo()
    set_task_id(task_id)
    run = repo.create_agent_run(
        task_id=task_id,
        agent=agent,
        status="running",
        started_at=now_iso(),
        input=input_fields,
        attempts=1,
    )
    set_agent_run_id(run["id"])
    try:
        yield run
    except Exception as exc:
        repo.update_agent_run(
            run["id"], status="failed", error=str(exc), finished_at=now_iso()
        )
        raise
    else:
        repo.update_agent_run(run["id"], status="succeeded", finished_at=now_iso())
    finally:
        set_agent_run_id(None)
