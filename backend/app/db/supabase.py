from __future__ import annotations

from supabase import Client, create_client

from app.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    """Lazily-constructed service-role Supabase client singleton (RLS bypassed; ownership is
    enforced in handlers). Raises if the project is not configured."""
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SECRET_KEY:
            raise RuntimeError("Supabase not configured (SUPABASE_URL / SUPABASE_SECRET_KEY).")
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)
    return _client
