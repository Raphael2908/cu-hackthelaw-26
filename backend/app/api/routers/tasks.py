from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.audit import record_accountability
from app.core.auth import CurrentUser, get_current_user
from app.db.repo import get_repo
from app.db.tables import CORPUS, TASKS
from app.providers.factory import get_llm_provider
from app.schemas.models import (
    DecisionCreate,
    MessageCreate,
    ReassignRequest,
    SubmissionCreate,
    TaskPatch,
)
from app.services import coordinator, views

router = APIRouter()


def _task_or_404(task_id: str) -> dict:
    task = get_repo().get(TASKS, task_id)
    if not task:
        raise HTTPException(404, "Task not found.")
    return task


@router.get("/inbox")
def inbox(user: CurrentUser = Depends(get_current_user)) -> list[dict]:
    """Associate inbox: tasks assigned to a human/hybrid worker that are awaiting submission. Hybrid
    tasks carry the AI instruction and the AI first-pass review."""
    repo = get_repo()
    out = []
    for t in repo.list(TASKS):
        if t["assignee_type"] in ("human", "hybrid") and t["status"] in (
            "dispatched",
            "in_progress",
            "returned",  # sent back by the partner for rework
            "awaiting_clarification",  # waiting on the partner's reply (read-only here)
        ):
            out.append(
                {
                    "task": t,
                    "target_document": repo.get(CORPUS, t["target_document_id"]),
                    "ai_first_pass": views.ai_first_pass(repo, t["id"]),  # hybrid only
                    "last_submission": views.latest_submission(repo, t["id"]),
                    "messages": views.messages(repo, t["id"]),
                }
            )
    return out


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    """Full item detail: submission, flags (each with a one-click source_ref), risk breakdown."""
    return views.task_detail(get_repo(), _task_or_404(task_id))


@router.patch("/tasks/{task_id}")
def patch_task(task_id: str, body: TaskPatch) -> dict:
    """Edit a PROPOSED task before approval (reassign, change severity, retitle)."""
    repo = get_repo()
    task = _task_or_404(task_id)
    if task["status"] != "proposed":
        raise HTTPException(409, "Only proposed tasks can be edited; the plan is already approved.")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    return repo.update(TASKS, task_id, fields)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, user: CurrentUser = Depends(get_current_user)) -> None:
    """Remove a PROPOSED task from the plan before approval. Recorded for traceability."""
    repo = get_repo()
    task = _task_or_404(task_id)
    if task["status"] != "proposed":
        raise HTTPException(409, "Only proposed tasks can be removed; the plan is approved.")
    repo.delete(TASKS, task_id)
    record_accountability(
        repo,
        type="task_removed",
        actor=user.email,
        case_id=task["case_id"],
        task_id=task_id,
        payload={"title": task["title"]},
    )


@router.post("/tasks/{task_id}/submit")
def submit_task(
    task_id: str, body: SubmissionCreate, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """A human associate submits work back into the flow."""
    repo = get_repo()
    task = _task_or_404(task_id)
    if task["assignee_type"] == "ai":
        raise HTTPException(409, "AI tasks are not submitted by a human.")
    return coordinator.submit_human_work(
        repo, task=task, summary=body.summary, findings=body.findings, actor=user.email
    )


@router.post("/tasks/{task_id}/decision")
def decide_task(
    task_id: str, body: DecisionCreate, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """approve / amend / reject → an immutable, signed record. The human is always the decider."""
    repo = get_repo()
    task = _task_or_404(task_id)
    if user.role != "partner":
        raise HTTPException(403, "Only the supervising partner can sign off on work.")
    return coordinator.record_decision(
        repo,
        task=task,
        action=body.action,
        note=body.note,
        amendment=body.amendment,
        actor=user.email,
    )


@router.post("/tasks/{task_id}/reassign")
def reassign_task(
    task_id: str, body: ReassignRequest, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """Partner-approved redo/reassignment. Never automatic."""
    repo = get_repo()
    task = _task_or_404(task_id)
    if user.role != "partner":
        raise HTTPException(403, "Only the supervising partner can reassign work.")
    return coordinator.reassign(
        repo,
        task=task,
        assignee_type=body.assignee_type,
        assignee_id=body.assignee_id,
        note=body.note,
        actor=user.email,
        provider=get_llm_provider(),
    )


@router.post("/tasks/{task_id}/message")
def post_message(
    task_id: str, body: MessageCreate, user: CurrentUser = Depends(get_current_user)
) -> dict:
    """The partner↔associate back-and-forth on one task. An associate raises a question (it goes to
    the partner's cockpit); the partner answers (it returns to the associate). Both hops are
    recorded in the audit trail."""
    repo = get_repo()
    task = _task_or_404(task_id)
    text = body.body.strip()
    if not text:
        raise HTTPException(422, "Message cannot be empty.")

    if user.role == "partner":
        if task["status"] != "awaiting_clarification":
            raise HTTPException(409, "There is no open question on this task to answer.")
        return coordinator.answer_clarification(repo, task=task, body=text, actor=user.email)

    # associate
    if task["assignee_type"] == "ai":
        raise HTTPException(409, "AI tasks have no associate to raise a question.")
    if task["status"] not in ("dispatched", "in_progress", "returned"):
        raise HTTPException(409, "You can only raise a question on a task in your inbox.")
    return coordinator.request_clarification(repo, task=task, body=text, actor=user.email)
