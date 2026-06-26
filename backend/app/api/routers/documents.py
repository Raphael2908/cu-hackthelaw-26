from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, get_current_user
from app.db.repo import get_repo
from app.schemas.models import DocumentRegister

router = APIRouter(prefix="/tasks", tags=["documents"])


@router.post("/{task_id}/documents")
def register_document(
    task_id: str, body: DocumentRegister, user: CurrentUser = Depends(get_current_user)
) -> dict:
    repo = get_repo()
    task = repo.get_task(task_id)
    if task is None or task["user_id"] != user.id:
        raise HTTPException(404, "Task not found.")
    return repo.create_document(
        task_id=task_id,
        user_id=user.id,
        filename=body.filename,
        s3_key=body.s3_key,
        mime=body.mime,
        status="uploaded",
    )


@router.get("/{task_id}/documents")
def list_documents(task_id: str, user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    repo = get_repo()
    task = repo.get_task(task_id)
    if task is None or task["user_id"] != user.id:
        raise HTTPException(404, "Task not found.")
    return repo.list_documents(task_id)
