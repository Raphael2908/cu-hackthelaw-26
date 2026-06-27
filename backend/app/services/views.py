from __future__ import annotations

from app.core.audit import verify_chain
from app.db.repo import Repo
from app.db.tables import AUDIT_EVENTS, FLAGS, RISK_SCORES, SUBMISSIONS, TASK_MESSAGES, TASKS


def latest_risk(repo: Repo, task_id: str) -> dict | None:
    scores = repo.list(RISK_SCORES, task_id=task_id)
    return scores[-1] if scores else None


def latest_submission(repo: Repo, task_id: str) -> dict | None:
    subs = repo.list(SUBMISSIONS, task_id=task_id)
    return subs[-1] if subs else None


def ai_first_pass(repo: Repo, task_id: str) -> dict | None:
    """The AI's pass on a hybrid task (distinct from the associate's own later submission). The
    pipeline tags it with the task's assignee_type, so a hybrid AI pass is produced_by 'hybrid'."""
    subs = [s for s in repo.list(SUBMISSIONS, task_id=task_id) if s["produced_by"] != "human"]
    return subs[0] if subs else None


def messages(repo: Repo, task_id: str) -> list[dict]:
    """The partner↔associate thread for a task, oldest first."""
    return repo.list(TASK_MESSAGES, task_id=task_id)


def task_card(repo: Repo, task: dict) -> dict:
    """A queue row: the task + its risk breakdown + the single most salient flag."""
    flags = repo.list(FLAGS, task_id=task["id"])
    risk = latest_risk(repo, task["id"])
    top_flag = None
    if flags:
        # Hard flags first, then by signal type. The partner sees the worst thing immediately.
        top_flag = sorted(flags, key=lambda f: (not f.get("hard"), f["signal_type"]))[0]
    return {
        "task": task,
        "risk": risk,
        "top_flag": top_flag,
        "flag_count": len(flags),
    }


def task_detail(repo: Repo, task: dict) -> dict:
    """Full item view: submission, every flag (with its checkable source_ref), risk breakdown."""
    return {
        "task": task,
        "submission": latest_submission(repo, task["id"]),
        "flags": repo.list(FLAGS, task_id=task["id"]),
        "risk": latest_risk(repo, task["id"]),
        "messages": messages(repo, task["id"]),
    }


def cockpit(repo: Repo, case_id: str) -> dict:
    """The triaged queue (highest risk first), the auto-clear lane (logged, with sampled items
    surfaced), and items already decided. No pass/fail anywhere — only triage."""
    tasks = repo.list(TASKS, case_id=case_id)
    cards = [task_card(repo, t) for t in tasks]

    def priority(card: dict) -> float:
        return card["risk"]["priority"] if card["risk"] else 0.0

    queue = sorted(
        [c for c in cards if c["task"]["status"] == "in_review"],
        key=priority,
        reverse=True,
    )
    auto_clear = [c for c in cards if c["task"]["status"] == "cleared"]
    decided = [c for c in cards if c["task"]["status"] == "signed_off"]
    # Escalations get their own lane: work that fell back to a human (a partner reject or a
    # fail-safe pipeline failure) is the partner's most urgent attention, not a footnote next to
    # signed-off work (architecture.md §8, §14.6).
    escalated = [c for c in cards if c["task"]["status"] == "escalated"]
    inbox = [c for c in cards if c["task"]["status"] in ("dispatched", "in_progress", "returned")]
    needs_reply = [c for c in cards if c["task"]["status"] == "awaiting_clarification"]
    for c in needs_reply:
        c["messages"] = messages(repo, c["task"]["id"])
    return {
        "queue": queue,
        "auto_clear_lane": auto_clear,
        "sampled_into_queue": [c for c in queue if c["risk"] and c["risk"].get("sampled")],
        "decided": decided,
        "escalated": escalated,
        "awaiting_human": inbox,
        "needs_reply": needs_reply,
    }


def audit_view(repo: Repo, case_id: str) -> dict:
    """Read-only audit. Accountability (decisions/approvals) and supervision (flags) are rendered as
    separate streams (architecture.md §11), with the hash chain verified."""
    events = [e for e in repo.list(AUDIT_EVENTS) if e.get("case_id") == case_id]
    return {
        "accountability": [e for e in events if e["kind"] == "accountability"],
        "supervision": [e for e in events if e["kind"] == "supervision"],
        "chain_valid": verify_chain(repo),
    }
