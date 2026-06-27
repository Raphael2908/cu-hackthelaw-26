from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, get_current_user
from app.db.repo import get_repo
from app.db.tables import PLANS, TASKS
from app.providers.factory import get_llm_provider
from app.services import coordinator

router = APIRouter()


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str) -> dict:
    repo = get_repo()
    plan = repo.get(PLANS, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found.")
    return {"plan": plan, "tasks": repo.list(TASKS, plan_id=plan_id)}


@router.post("/plans/{plan_id}/approve")
def approve_plan(plan_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    """The approval gate. Records the partner's explicit approval, then dispatches the tasks."""
    repo = get_repo()
    plan = repo.get(PLANS, plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found.")
    if user.role != "partner":
        raise HTTPException(403, "Only the supervising partner can approve a plan.")
    try:
        return coordinator.approve_plan(
            repo, plan=plan, provider=get_llm_provider(), actor=user.email
        )
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
