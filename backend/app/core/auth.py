from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException

from app.config import settings

_ALGORITHMS = ["ES256", "RS256"]


@dataclass
class CurrentUser:
    id: str
    email: str | None = None


def _issuer() -> str:
    return f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"


@lru_cache
def _jwk_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{_issuer()}/.well-known/jwks.json")


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> CurrentUser:
    if not settings.SUPABASE_URL:
        raise HTTPException(503, "Auth not configured (SUPABASE_URL unset).")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token.")

    token = authorization.split(" ", 1)[1]
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token).key
    except jwt.PyJWKClientError as exc:
        raise HTTPException(503, "Auth provider unreachable.") from exc

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=_ALGORITHMS,
            audience="authenticated",
            issuer=_issuer(),
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Invalid token.") from exc

    return CurrentUser(id=claims["sub"], email=claims.get("email"))
