from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from app.core.auth import CurrentUser, get_current_user
from app.db.repo import get_repo
from app.schemas.models import (
    CandidateOut,
    OutputOut,
    TaskCreate,
    TaskOut,
)
from app.services.pipeline import enqueue_pipeline

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _owned_task(task_id: str, user: CurrentUser) -> dict:
    task = get_repo().get_task(task_id)
    if task is None or task["user_id"] != user.id:
        raise HTTPException(404, "Task not found.")
    return task


@router.post("", response_model=TaskOut)
def create_task(body: TaskCreate, user: CurrentUser = Depends(get_current_user)) -> dict:
    repo = get_repo()
    task = repo.create_task(
        user_id=user.id,
        task_type=body.task_type,
        title=body.title,
        brief=body.brief,
        eval_doc_count=body.eval_doc_count or settings.DEFAULT_EVAL_DOC_COUNT,
        status="planning",
        plan_md=None,
    )
    enqueue_pipeline(task["id"])
    return task


@router.get("", response_model=list[TaskOut])
def list_tasks(user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    return get_repo().list_tasks(user.id)


@router.get("/{task_id}", response_model=TaskOut)
def get_task(task_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    return _owned_task(task_id, user)


@router.get("/{task_id}/candidates", response_model=list[CandidateOut])
def list_candidates(task_id: str, user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    _owned_task(task_id, user)
    return get_repo().list_candidates(task_id)


@router.get("/{task_id}/output", response_model=OutputOut)
def get_output(task_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    _owned_task(task_id, user)
    output = get_repo().latest_output(task_id)
    if output is None:
        raise HTTPException(404, "No output yet.")
    return output
