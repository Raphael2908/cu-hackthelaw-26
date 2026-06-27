from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from app.config import settings

# Shared pool for the supervision pipeline. Dispatch submits each AI/hybrid task here so the approve
# request returns immediately; the slow model calls run off the request path and the cockpit shows
# progress as tasks finish (architecture.md §8 — the same service boundary a real queue would slot
# into). The store (SqliteRepo) serialises writes under its own lock, and the audit chain is written
# under a lock, so concurrent workers are safe.
_executor: ThreadPoolExecutor | None = None


def _pool() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=max(1, settings.DISPATCH_WORKERS), thread_name_prefix="dispatch"
        )
    return _executor


def submit(fn: Callable, *args) -> None:
    """Run `fn(*args)` on the background pool. Fire-and-forget: the caller does not await it."""
    _pool().submit(fn, *args)
