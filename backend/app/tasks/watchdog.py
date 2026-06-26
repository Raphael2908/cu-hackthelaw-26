from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.celery_app import celery_app
from app.config import settings
from app.db.repo import get_repo
from app.tasks.common import now_iso


@celery_app.task(name="tasks.watchdog_sweep")
def watchdog_sweep() -> int:
    """Fail agent_runs stuck in `running` past their SLA (a crashed/lost worker). Returns the
    number swept."""
    cutoff = (
        datetime.now(UTC) - timedelta(seconds=settings.AGENT_TIMEOUT_S + 120)
    ).isoformat()
    repo = get_repo()
    stuck = repo.list_runs_stuck_running(cutoff)
    for run in stuck:
        repo.update_agent_run(
            run["id"], status="failed", error="watchdog: stuck past SLA", finished_at=now_iso()
        )
    return len(stuck)
