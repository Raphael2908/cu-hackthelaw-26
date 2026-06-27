from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.audit import record_accountability
from app.core.auth import CurrentUser, get_current_user
from app.db.repo import get_repo
from app.db.tables import CASES, CORPUS, DEBRIEFS, PLANS, TASKS
from app.fixtures import firm_standard, process_doc
from app.providers.factory import get_llm_provider
from app.schemas.models import CaseCreate, PlanReviseRequest
from app.services import debrief as debrief_svc
from app.services import documents, planner, views

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
            "severity": body.severity,
            "instructions": body.instructions,
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


@router.post("/cases/{case_id}/documents", status_code=201)
async def upload_case_documents(
    case_id: str,
    files: list[UploadFile] = File(...),
    user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Attach bulk documents (PDF / text / DOCX) to a case so the planner can scope tasks over them.
    Each becomes a `draft` corpus document tagged with this `case_id` (architecture.md §9 — text
    attached to a case, no object store). Records an accountability event for the upload."""
    repo = get_repo()
    case = repo.get(CASES, case_id)
    if not case:
        raise HTTPException(404, "Case not found.")

    created: list[dict] = []
    for upload in files:
        raw = await upload.read()
        try:
            text = documents.extract_text(upload.filename or "document", raw)
        except ValueError as e:
            raise HTTPException(415, str(e)) from e
        doc = repo.insert(
            CORPUS,
            {
                "celex": None,
                "kind": "draft",
                "title": upload.filename or "Untitled document",
                "source_url": f"upload://{case_id}/{upload.filename}",
                "text": text,
                "case_id": case_id,
                "planted_defects": [],
                "ground_truth": {},
            },
        )
        created.append({"id": doc["id"], "title": doc["title"]})

    record_accountability(
        repo,
        type="documents_uploaded",
        actor=user.email,
        case_id=case_id,
        payload={"document_ids": [d["id"] for d in created], "n": len(created)},
    )
    return created


@router.get("/cases/{case_id}/documents")
def list_case_documents(case_id: str) -> list[dict]:
    docs = get_repo().list(CORPUS, kind="draft", case_id=case_id)
    return [{"id": d["id"], "title": d["title"], "source_url": d.get("source_url")} for d in docs]


@router.post("/cases/{case_id}/plan", status_code=201)
def create_plan(case_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Run the planner → a PROPOSED plan. Nothing dispatches yet (architecture.md §6)."""
    repo = get_repo()
    case = repo.get(CASES, case_id)
    if not case:
        raise HTTPException(404, "Case not found.")
    return planner.propose_plan(repo, case=case, provider=get_llm_provider(), actor=user.email)


@router.post("/cases/{case_id}/plan/tasks", status_code=201)
def add_plan_task(case_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Add a blank proposed task to the plan for the partner to fill in (architecture.md §6)."""
    repo = get_repo()
    case = repo.get(CASES, case_id)
    if not case:
        raise HTTPException(404, "Case not found.")
    try:
        return planner.add_task(repo, case=case, actor=user.email)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/cases/{case_id}/plan/revise", status_code=201)
def revise_case_plan(
    case_id: str, body: PlanReviseRequest, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """Re-propose the plan from the partner's free-text direction. Still a PROPOSAL — nothing
    dispatches until the partner approves (architecture.md §6)."""
    repo = get_repo()
    case = repo.get(CASES, case_id)
    if not case:
        raise HTTPException(404, "Case not found.")
    try:
        return planner.revise_plan(
            repo, case=case, provider=get_llm_provider(), feedback=body.feedback, actor=user.email
        )
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


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


def _pending_close_message(p: dict) -> str:
    parts = []
    if p["awaiting_decision"]:
        parts.append(f"{p['awaiting_decision']} awaiting your decision")
    if p["with_associate"]:
        parts.append(f"{p['with_associate']} with an associate")
    if p["not_run"]:
        parts.append(f"{p['not_run']} not yet started")
    n = p["total"]
    return (
        f"Cannot close the case: {n} task{'s' if n != 1 else ''} still pending "
        f"({', '.join(parts)}). Resolve every task before generating the debrief."
    )


@router.post("/cases/{case_id}/close")
def close_case(case_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    """Close the case and generate the debrief — but only once every task is resolved. A debrief
    drawn from an in-flight record would misrepresent the matter, so a case with any pending task is
    refused (409). This is the authoritative guard; the frontend also disables the button."""
    repo = get_repo()
    case = repo.get(CASES, case_id)
    if not case:
        raise HTTPException(404, "Case not found.")
    pending = views.pending_summary(repo.list(TASKS, case_id=case_id))
    if pending["total"] > 0:
        raise HTTPException(409, _pending_close_message(pending))
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
