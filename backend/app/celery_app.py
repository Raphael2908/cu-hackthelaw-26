from __future__ import annotations

from celery import Celery

from app.config import settings
from app.core.logging import configure_logging

configure_logging()

celery_app = Celery(
    "legal_drafting_copilot",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.agents", "app.tasks.watchdog", "app.tasks.signals"],
)

# One queue per agent stage so each scales / rate-limits independently.
celery_app.conf.task_routes = {
    "tasks.plan": {"queue": "q.plan"},
    "tasks.coordinate": {"queue": "q.plan"},
    "tasks.web_research": {"queue": "q.research"},
    "tasks.doc_read": {"queue": "q.doc"},
    "tasks.rerank": {"queue": "q.rerank"},
    "tasks.evaluate": {"queue": "q.eval"},
    "tasks.synthesize": {"queue": "q.synth"},
    "tasks.watchdog_sweep": {"queue": "q.plan"},
}

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
    timezone="UTC",
)

_t = settings.AGENT_TIMEOUT_S
celery_app.conf.task_annotations = {
    name: {"soft_time_limit": _t, "time_limit": _t + 60}
    for name in (
        "tasks.plan",
        "tasks.coordinate",
        "tasks.web_research",
        "tasks.doc_read",
        "tasks.rerank",
        "tasks.evaluate",
        "tasks.synthesize",
    )
}

celery_app.conf.beat_schedule = {
    "watchdog-sweep": {"task": "tasks.watchdog_sweep", "schedule": 60.0},
}
