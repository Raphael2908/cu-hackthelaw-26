from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from functools import lru_cache

from app.config import settings

# The worker model's live "thinking" relayed to the cockpit's "With AI" lane (architecture.md §8).
#
# Transport: a capped, TTL'd Redis LIST keyed by task, NOT bare pub/sub — so a partner who expands a
# row mid-run still replays what already streamed (pub/sub drops history for late subscribers). The
# publisher is sync (runs inside the Celery worker); the reader is async (it backs the SSE route).
#
# GUARDRAIL (architecture.md §14): this buffer is TRANSIENT UX ONLY. It is never read into the repo
# or the hash-chained audit record (which stays decisions + checkable evidence). Everything here is
# best-effort: a missing/unreachable broker means "no live stream", never a pipeline failure.

_MAX_DELTAS = 400  # cap the buffer so a long run can't grow it without bound
_POLL_SECONDS = 0.25  # how often the SSE reader tails the list for new deltas
_READ_DEADLINE_SECONDS = 180  # hard cap on one SSE connection's lifetime


def _key(task_id: str) -> str:
    return f"stream:task:{task_id}"


@lru_cache(maxsize=1)
def _sync_client():  # noqa: ANN202 - redis client type is import-time only
    """A pooled sync Redis client for the publisher, built once per worker process."""
    import redis

    return redis.from_url(settings.CELERY_BROKER_URL)


def publish_delta(task_id: str, event: dict) -> None:
    """Append one stream event (``{"type": "delta", "text": ...}`` or ``{"type": "done"}``) to the
    task's transient buffer. Best-effort: any Redis error is swallowed so dispatch never breaks when
    the broker is absent (inline/offline mode, tests)."""
    try:
        client = _sync_client()
        key = _key(task_id)
        pipe = client.pipeline()
        pipe.rpush(key, json.dumps(event))
        pipe.ltrim(key, -_MAX_DELTAS, -1)
        pipe.expire(key, settings.STREAM_TTL_SECONDS)
        pipe.execute()
    except Exception:  # noqa: BLE001 - the live stream is non-essential; never break the pipeline
        pass


async def iter_deltas(task_id: str) -> AsyncIterator[dict]:
    """Yield a task's stream events in order, tailing the buffer until a ``done`` event arrives, the
    deadline is hit, or the broker is unreachable. Replays any deltas already buffered, so a late
    subscriber (the partner expanding the row mid-run) still sees the run so far."""
    try:
        import redis.asyncio as aioredis
    except Exception:  # noqa: BLE001 - no redis client available → nothing to stream
        return

    client = aioredis.from_url(settings.CELERY_BROKER_URL)
    key = _key(task_id)
    cursor = 0
    deadline = time.monotonic() + _READ_DEADLINE_SECONDS
    try:
        while time.monotonic() < deadline:
            try:
                raw = await client.lrange(key, cursor, -1)
            except Exception:  # noqa: BLE001 - broker dropped mid-stream → end the stream cleanly
                return
            for item in raw:
                cursor += 1
                try:
                    event = json.loads(item)
                except (ValueError, TypeError):
                    continue
                yield event
                if event.get("type") == "done":
                    return
            await asyncio.sleep(_POLL_SECONDS)
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
