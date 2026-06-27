from __future__ import annotations

from celery import Celery

from app.config import settings

# The Celery application — the durable, retryable, horizontally-scalable replacement for the old
# in-process thread pool (architecture.md §8). Kept free of any app-internal imports so the task
# module (which imports the coordinator) can import this without a cycle. JSON-only payloads force
# us to pass serializable args across the process boundary: dispatch sends a task_id, and the worker
# reconstructs the repo + provider from their factories (see app/core/tasks.py).
celery_app = Celery(
    "cockpit",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)
celery_app.autodiscover_tasks(["app.core"])  # registers app/core/tasks.py
