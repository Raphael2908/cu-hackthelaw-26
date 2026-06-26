from __future__ import annotations

import redis

from app.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Lazily-constructed Redis client singleton (transport + ephemeral state)."""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client
