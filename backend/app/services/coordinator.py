from __future__ import annotations

from datetime import UTC, datetime

from app.core.audit import record_accountability
from app.db.repo import Repo
from app.db.tables import DECISIONS, PLANS, SUBMISSIONS, TASKS
from app.providers.base import LLMProvider
from app.services import checker, ranker, worker

# Neutral signals for human-only submissions: we do NOT run the checker on purely human work
# (no AI grading of a qualified lawyer's product — architecture.md §14). Placement is by the
# up-front severity alone.
_NEUTRAL_SIGNALS = {
    "citation_support_rate": 1.0,
    "deviation_score": 0.0,
    "disagreement_score": 0.0,
    "flags": [],
    "has_hard_flag": False,
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _route_by_risk(repo: Repo, task: dict, risk: dict) -> str:
    """Auto-cleared (and not sampled) → logged to the audit lane. Everything else → the partner's
    cockpit queue. Nothing is auto-approved (architecture.md §7.3)."""
    if risk["lane"] == "auto_clear" and not risk["sampled"]:
        repo.update(TASKS, task["id"], {"status": "cleared"})
        record_accountability(
            repo,
            type="auto_cleared",
            actor="coordinator",
            case_id=task["case_id"],
            task_id=task["id"],
            payload={"severity": task["severity"], "uncertainty": risk["uncertainty"]},
        )
        return "cleared"
    repo.update(TASKS, task["id"], {"status": "in_review"})
    return "in_review"


def _run_ai_pipeline(repo: Repo, task: dict, provider: LLMProvider) -> dict:
    """worker → checker → ranker, synchronously (instant in mock mode). Each transition is a state
    change on the task; the checker writes flags, the ranker writes a risk score."""
    produced_by = task["assignee_type"]  # "ai" or "hybrid"
    repo.update(TASKS, task["id"], {"status": "in_progress"})
    submission = worker.run_review(repo, task=task, provider=provider, produced_by=produced_by)
    record_accountability(
        repo,
        type="submission_received",
        actor=f"worker:{produced_by}",
        case_id=task["case_id"],
        task_id=task["id"],
        payload={"submission_id": submission["id"]},
    )
    repo.update(TASKS, task["id"], {"status": "submitted"})
    signals = checker.run_checks(repo, task, submission, provider)
    risk = ranker.score_task(repo, task, signals)
    repo.update(TASKS, task["id"], {"status": "checked"})
    return {"submission": submission, "risk": risk, "signals": signals}


def dispatch_task(repo: Repo, task: dict, provider: LLMProvider) -> dict:
    """Dispatch one approved task to the right worker. AI tasks run the supervision pipeline now;
    human tasks land in the associate inbox; hybrid tasks do both (AI pass + human ownership)."""
    record_accountability(
        repo,
        type="task_dispatched",
        actor="coordinator",
        case_id=task["case_id"],
        task_id=task["id"],
        payload={"assignee_type": task["assignee_type"]},
    )
    if task["assignee_type"] == "ai":
        out = _run_ai_pipeline(repo, task, provider)
        _route_by_risk(repo, task, out["risk"])
        return out
    if task["assignee_type"] == "hybrid":
        out = _run_ai_pipeline(repo, task, provider)
        # The human associate owns the result: it returns to the inbox until they submit.
        repo.update(TASKS, task["id"], {"status": "in_progress"})
        return out
    # human: sits in the inbox awaiting submission.
    repo.update(TASKS, task["id"], {"status": "dispatched"})
    return {"status": "dispatched"}


def approve_plan(repo: Repo, *, plan: dict, provider: LLMProvider, actor: str) -> dict:
    """The approval gate. No task is dispatched without this explicit, recorded partner action
    (architecture.md §14.7)."""
    if plan["status"] == "approved":
        raise ValueError("Plan already approved.")
    updated = repo.update(
        PLANS, plan["id"], {"status": "approved", "approved_by": actor, "approved_at": _now()}
    )
    record_accountability(
        repo,
        type="plan_approved",
        actor=actor,
        case_id=plan["case_id"],
        payload={"plan_id": plan["id"]},
    )
    tasks = repo.list(TASKS, plan_id=plan["id"])
    for task in tasks:
        repo.update(TASKS, task["id"], {"status": "approved"})
        dispatch_task(repo, repo.get(TASKS, task["id"]), provider)
    return {"plan": updated, "dispatched": len(tasks)}


def submit_human_work(
    repo: Repo, *, task: dict, summary: str, findings: list[dict], actor: str
) -> dict:
    """A human associate submits work back into the flow. Placed by up-front severity only — the
    checker never grades human work product."""
    submission = repo.insert(
        SUBMISSIONS,
        {
            "task_id": task["id"],
            "produced_by": "human",
            "run_index": 0,
            "summary": summary,
            "findings": findings,
            "citations": [],
            "clauses_relied_on": [],
            "audit_sources": [],
        },
    )
    record_accountability(
        repo,
        type="submission_received",
        actor=f"associate:{actor}",
        case_id=task["case_id"],
        task_id=task["id"],
        payload={"submission_id": submission["id"]},
    )
    repo.update(TASKS, task["id"], {"status": "submitted"})
    risk = ranker.score_task(repo, task, _NEUTRAL_SIGNALS)
    repo.update(TASKS, task["id"], {"status": "checked"})
    _route_by_risk(repo, task, risk)
    return {"submission": submission, "risk": risk}


def record_decision(
    repo: Repo, *, task: dict, action: str, note: str, amendment: str | None, actor: str
) -> dict:
    """approve / amend / reject. Writes an immutable, signed (hash-chained) accountability record.
    The agent never decides — only the human does (architecture.md §14.1)."""
    decision = repo.insert(
        DECISIONS,
        {
            "task_id": task["id"],
            "action": action,
            "note": note,
            "amendment": amendment,
            "decided_by": actor,
            "decided_at": _now(),
        },
    )
    record_accountability(
        repo,
        type="decision_recorded",
        actor=actor,
        case_id=task["case_id"],
        task_id=task["id"],
        payload={
            "action": action,
            "note": note,
            "amendment": amendment,
            "decision_id": decision["id"],
        },
    )
    status = "signed_off" if action in ("approve", "amend") else "escalated"
    repo.update(TASKS, task["id"], {"status": status})
    return decision


def reassign(
    repo: Repo,
    *,
    task: dict,
    assignee_type: str,
    assignee_id: str | None,
    note: str,
    actor: str,
    provider: LLMProvider,
) -> dict:
    """Partner-approved redo. Auto-reassignment of flagged work back into the machine is never
    permitted; this only runs on an explicit partner action (architecture.md §14.6)."""
    record_accountability(
        repo,
        type="task_reassigned",
        actor=actor,
        case_id=task["case_id"],
        task_id=task["id"],
        payload={"assignee_type": assignee_type, "assignee_id": assignee_id, "note": note},
    )
    repo.update(
        TASKS,
        task["id"],
        {"assignee_type": assignee_type, "assignee_id": assignee_id, "status": "approved"},
    )
    return dispatch_task(repo, repo.get(TASKS, task["id"]), provider)
