from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, get_current_user
from app.db.repo import get_repo
from app.db.tables import CASES, DEBRIEFS, PLANS
from app.fixtures import firm_standard, process_doc
from app.providers.factory import get_llm_provider
from app.schemas.models import CaseCreate
from app.services import debrief as debrief_svc
from app.services import planner, views

router = APIRouter()


@router.post("/cases", status_code=201)
def create_case(body: CaseCreate, user: CurrentUser = Depends(get_current_user)) -> dict:
    repo = get_repo()
    case = repo.insert(
        CASES,
        {
            "title": body.title,
            "brief_text": body.brief_text,
            "goal": body.goal,
            "process_doc_id": body.process_doc_id or process_doc()["id"],
            "firm_standard_id": body.firm_standard_id or firm_standard()["id"],
            "status": "open",
            "created_by": user.email,
        },
    )
    return case


@router.get("/cases")
def list_cases() -> list[dict]:
    return get_repo().list(CASES)


@router.get("/cases/{case_id}")
def get_case(case_id: str) -> dict:
    case = get_repo().get(CASES, case_id)
    if not case:
        raise HTTPException(404, "Case not found.")
    return case


@router.post("/cases/{case_id}/plan", status_code=201)
def create_plan(case_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Run the planner → a PROPOSED plan. Nothing dispatches yet (architecture.md §6)."""
    repo = get_repo()
    case = repo.get(CASES, case_id)
    if not case:
        raise HTTPException(404, "Case not found.")
    return planner.propose_plan(repo, case=case, provider=get_llm_provider(), actor=user.email)


@router.get("/cases/{case_id}/plan")
def get_case_plan(case_id: str) -> dict:
    repo = get_repo()
    plans = repo.list(PLANS, case_id=case_id)
    if not plans:
        raise HTTPException(404, "No plan for this case.")
    plan = plans[-1]
    from app.db.tables import TASKS

    return {"plan": plan, "tasks": repo.list(TASKS, plan_id=plan["id"])}


@router.get("/cases/{case_id}/cockpit")
def get_cockpit(case_id: str) -> dict:
    return views.cockpit(get_repo(), case_id)


@router.get("/cases/{case_id}/audit")
def get_audit(case_id: str) -> dict:
    return views.audit_view(get_repo(), case_id)


@router.post("/cases/{case_id}/close")
def close_case(case_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    repo = get_repo()
    case = repo.get(CASES, case_id)
    if not case:
        raise HTTPException(404, "Case not found.")
    repo.update(CASES, case_id, {"status": "closed", "closed_at": datetime.now(UTC).isoformat()})
    return debrief_svc.generate_debrief(
        repo, case=case, provider=get_llm_provider(), actor=user.email
    )


@router.get("/cases/{case_id}/debrief")
def get_debrief(case_id: str) -> dict:
    debriefs = get_repo().list(DEBRIEFS, case_id=case_id)
    if not debriefs:
        raise HTTPException(404, "No debrief yet — close the case to generate one.")
    return debriefs[-1]
