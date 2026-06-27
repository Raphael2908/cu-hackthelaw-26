from __future__ import annotations

from app.core.audit import verify_chain
from app.db.repo import Repo
from app.db.tables import AUDIT_EVENTS, FLAGS, RISK_SCORES, SUBMISSIONS, TASKS


def latest_risk(repo: Repo, task_id: str) -> dict | None:
    scores = repo.list(RISK_SCORES, task_id=task_id)
    return scores[-1] if scores else None


def latest_submission(repo: Repo, task_id: str) -> dict | None:
    subs = repo.list(SUBMISSIONS, task_id=task_id)
    return subs[-1] if subs else None


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
    decided = [c for c in cards if c["task"]["status"] in ("signed_off", "escalated")]
    inbox = [c for c in cards if c["task"]["status"] in ("dispatched", "in_progress")]
    return {
        "queue": queue,
        "auto_clear_lane": auto_clear,
        "sampled_into_queue": [c for c in queue if c["risk"] and c["risk"].get("sampled")],
        "decided": decided,
        "awaiting_human": inbox,
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
