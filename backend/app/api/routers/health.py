from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/healthz")
@router.get("/api/healthz")
def healthz() -> dict:
    return {"status": "ok"}
