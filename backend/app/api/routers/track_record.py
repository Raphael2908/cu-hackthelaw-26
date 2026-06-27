from __future__ import annotations

from fastapi import APIRouter

from app.db.repo import get_repo
from app.fixtures import process_doc
from app.services import track_record as track_record_svc

router = APIRouter()


@router.get("/track-record")
def get_track_record(process_doc_id: str | None = None) -> dict:
    """The agentic track record for one process map (architecture.md §6): per-section outcome counts
    (completed / clean / amended / escalated / graduated) plus the log of every completed AI/hybrid
    task on that map. Read-only; outcomes, never a verdict. Defaults to the seeded process map."""
    pid = process_doc_id or process_doc()["id"]
    return track_record_svc.aggregate(get_repo(), process_doc_id=pid)
