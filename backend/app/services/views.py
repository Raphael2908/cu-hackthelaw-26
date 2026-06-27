from __future__ import annotations

from app.core.audit import verify_chain
from app.db.repo import Repo
from app.db.tables import (
    AUDIT_EVENTS,
    CORPUS,
    FLAGS,
    RISK_SCORES,
    SUBMISSIONS,
    TASK_MESSAGES,
    TASKS,
)

# A task is "resolved" once it reaches one of these. Everything else is still in flight — it needs
# to run, come back from an associate, or get the partner's decision. Gates case close / debrief.
TERMINAL_STATUSES = frozenset({"signed_off", "escalated", "cleared"})


def pending_summary(tasks: list[dict]) -> dict:
    """Group not-yet-resolved tasks by what's holding them up — a debrief-readiness check. A debrief
    drawn from an incomplete record would misrepresent the matter, so closing is gated on total == 0
    (architecture.md §14: nothing is signed off until the human has actually supervised it)."""
    pending = [t for t in tasks if t["status"] not in TERMINAL_STATUSES]
    in_set = lambda *s: [t for t in pending if t["status"] in s]  # noqa: E731
    return {
        "total": len(pending),
        "awaiting_decision": len(in_set("submitted", "checked", "in_review")),
        "with_associate": len(
            in_set("dispatched", "in_progress", "returned", "awaiting_clarification")
        ),
        "not_run": len(in_set("proposed", "approved")),
    }


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


def task_attachments(repo: Repo, task_id: str) -> list[dict]:
    """Files the associate attached to this task — stored as case+task-tagged corpus docs, returned
    with their corpus id so the partner can open each in the source drawer."""
    docs = repo.list(CORPUS, kind="attachment", task_id=task_id)
    return [{"id": d["id"], "title": d["title"]} for d in docs]


# A task is "in flight" (pre-review) when it is between dispatch and the partner's review queue.
_PRE_REVIEW = frozenset({"dispatched", "in_progress", "submitted", "checked"})


def _holder(repo: Repo, card: dict) -> str | None:
    """Who is actually holding an in-flight task right now: ``'ai'`` (the supervision pipeline is
    running) or ``'human'`` (it sits in the associate's inbox). ``None`` if the task isn't in an
    in-flight/pre-review state. Lanes must look at ``assignee_type``, not status alone — a running
    AI task is ``in_progress`` but is NOT "with a person" (architecture.md §8)."""
    t = card["task"]
    status, at = t["status"], t["assignee_type"]
    if at == "human":
        return "human" if status in ("dispatched", "in_progress", "returned") else None
    if at == "ai":
        return "ai" if status in _PRE_REVIEW else None
    # hybrid: the AI first pass is "with AI"; once that pass exists and the task is parked for the
    # associate, or it was returned for rework, it is "with a person". The AI first-pass submission
    # is the discriminator, because a hybrid task is in_progress BOTH while the AI drafts AND after,
    # while awaiting the associate (coordinator._run_and_route).
    if status == "returned":
        return "human"
    if status in _PRE_REVIEW:
        if status == "in_progress" and ai_first_pass(repo, t["id"]):
            return "human"
        return "ai"
    return None


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
        "attachments": task_attachments(repo, task["id"]),
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
    # Partition in-flight work by who's actually holding it (assignee_type), not status alone: AI/
    # hybrid tasks running the pipeline get their own "With AI" lane instead of being mislabelled as
    # "with a person" or falling into no lane while submitted/checked (architecture.md §8).
    with_ai = [c for c in cards if _holder(repo, c) == "ai"]
    inbox = [c for c in cards if _holder(repo, c) == "human"]
    needs_reply = [c for c in cards if c["task"]["status"] == "awaiting_clarification"]
    for c in needs_reply:
        c["messages"] = messages(repo, c["task"]["id"])
    return {
        "queue": queue,
        "auto_clear_lane": auto_clear,
        "sampled_into_queue": [c for c in queue if c["risk"] and c["risk"].get("sampled")],
        "decided": decided,
        "escalated": escalated,
        "with_ai": with_ai,
        "awaiting_human": inbox,
        "needs_reply": needs_reply,
        # Complete pending count across ALL statuses (incl. proposed/approved/submitted/checked that
        # no lane shows) so the debrief page can gate "close" on a fully-resolved case.
        "pending": pending_summary(tasks),
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
