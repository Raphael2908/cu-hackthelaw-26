from __future__ import annotations

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "provider_mode": settings.PROVIDER_MODE, "env": settings.ENV}
