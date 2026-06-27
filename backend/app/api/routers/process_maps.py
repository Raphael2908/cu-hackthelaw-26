from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.audit import record_accountability
from app.core.auth import CurrentUser, get_current_user
from app.db.repo import get_repo
from app.db.tables import CORPUS
from app.schemas.models import ProcessMapCreate

router = APIRouter()


def _as_map(doc: dict) -> dict:
    return {"id": doc["id"], "title": doc["title"], "task_types": doc.get("task_types", {})}


@router.get("/process-maps")
def list_process_maps() -> list[dict]:
    """The process maps a partner can select for a case (architecture.md §6). Each is a
    `process_doc` corpus document carrying its sections (`task_types`)."""
    return [_as_map(d) for d in get_repo().list(CORPUS, kind="process_doc")]


@router.post("/process-maps", status_code=201)
def create_process_map(
    body: ProcessMapCreate, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """Lightweight structured create — a brand-new process map starts as a clean slate (no agentic
    track record), so the planner proposes delegation purely by task nature and the partner decides
    where to insert AI. Uploading a real process-map document is a follow-up (todo.md)."""
    repo = get_repo()
    doc = repo.insert(
        CORPUS,
        {
            "celex": None,
            "kind": "process_doc",
            "title": body.title,
            "source_url": "internal://process/custom",
            "text": "Partner-authored process map.",
            "clauses": {},
            "planted_defects": [],
            "ground_truth": {},
            "task_types": {k: v.model_dump() for k, v in body.task_types.items()},
        },
    )
    record_accountability(
        repo,
        type="process_map_created",
        actor=user.email,
        payload={"process_doc_id": doc["id"], "n_sections": len(body.task_types)},
    )
    return _as_map(doc)
