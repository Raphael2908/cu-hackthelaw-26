from __future__ import annotations

from app.config import settings
from app.db.repo import Repo
from app.db.tables import CASES, DECISIONS, TASKS

# A completed agentic task is in one of these terminal states (architecture.md §5).
_TERMINAL = {"signed_off", "cleared", "escalated"}
# Only AI/hybrid work builds an AI track record — we never grade purely human work (§14).
_AGENTIC = {"ai", "hybrid"}


def _outcome(repo: Repo, task: dict) -> str:
    """Reduce a completed agentic task to a single outcome the log can show and the planner can
    count. `clean` = the AI work stood (auto-cleared, or signed off without amendment); `adverse` =
    a human had to amend it or it was rejected/escalated. Never a verdict — just what happened."""
    status = task.get("status")
    if status == "escalated":
        return "adverse"
    if status == "cleared":
        return "clean"
    if status == "signed_off":
        decisions = repo.list(DECISIONS, task_id=task["id"])
        action = decisions[-1].get("action") if decisions else None
        return "adverse" if action == "amend" else "clean"
    return "clean"


def aggregate(repo: Repo, *, process_doc_id: str) -> dict:
    """The agentic track record for ONE process map (architecture.md §6).

    Walks every completed AI/hybrid task whose case used `process_doc_id`, bucketed by section
    (`task_type`). The record is scoped to the map — a fresh map is a clean slate; a reused map
    carries history the planner consults to graduate a section to AI (clean record) or pull it back
    to a human owner (adverse record). Returns per-section counts plus a flat completed-task log."""
    case_map = {c["id"]: c.get("process_doc_id") for c in repo.list(CASES)}

    by_section: dict[str, dict] = {}
    log: list[dict] = []
    for task in repo.list(TASKS):
        if task.get("assignee_type") not in _AGENTIC or task.get("status") not in _TERMINAL:
            continue
        if case_map.get(task.get("case_id")) != process_doc_id:
            continue
        section = task.get("task_type", "")
        rec = by_section.setdefault(
            section,
            {
                "label": task.get("input_process_section") or section,
                "completed": 0,
                "ai": 0,
                "hybrid": 0,
                "clean_successes": 0,
                "amended": 0,
                "escalated": 0,
                "adverse": 0,
            },
        )
        outcome = _outcome(repo, task)
        rec["completed"] += 1
        rec[task["assignee_type"]] += 1
        if outcome == "adverse":
            rec["adverse"] += 1
            if task.get("status") == "escalated":
                rec["escalated"] += 1
            else:
                rec["amended"] += 1
        else:
            rec["clean_successes"] += 1
        log.append(
            {
                "task_id": task["id"],
                "case_id": task.get("case_id"),
                "task_type": section,
                "title": task.get("title"),
                "assignee_type": task["assignee_type"],
                "status": task.get("status"),
                "outcome": outcome,
                "seq": task.get("seq", 0),
            }
        )

    for rec in by_section.values():
        rec["clean"] = rec["completed"] >= settings.AI_TRACK_RECORD_MIN and rec["adverse"] == 0

    log.sort(key=lambda r: r["seq"], reverse=True)
    return {"process_doc_id": process_doc_id, "by_section": by_section, "log": log}


def apply_record(
    *, suggested_type: str, section_record: dict | None, instructed: bool = False
) -> tuple[str, str]:
    """Overlay a section's track record on the planner agent's nature-based suggestion.

    The planner agent decides delegation from the *nature* of the task (mechanical -> AI;
    high-judgment -> human/hybrid) — never from severity. This only adjusts that suggestion using
    what AI has actually done on this section of this map: graduate to AI on a clean record, pull
    back to a human owner on an adverse one. Returns ``(assignee_type, rationale)``; the plan stays
    a proposal the partner edits (architecture.md §6, §14.7).

    When ``instructed`` is set, the partner gave up-front instructions for this matter, and the
    planner's suggestion already reflects them — so a clean record does NOT graduate the task to AI
    over the partner's explicit steer. Pull-back on an adverse record still applies (it is a safety
    mechanism, not an optimisation)."""
    rec = section_record
    if rec and rec.get("clean"):
        if instructed:
            return (
                suggested_type,
                "AI has a clean record on this section, but the partner's up-front instructions "
                "steer this delegation — keeping the proposed assignee.",
            )
        return (
            "ai",
            f"AI has a clean record on this section of this process map "
            f"({rec['completed']} completed, 0 amended/rejected) — proposed AI.",
        )
    if rec and rec.get("adverse", 0) > 0:
        pulled_back = "human" if suggested_type == "human" else "hybrid"
        return (
            pulled_back,
            f"AI work on this section was amended/rejected before on this map "
            f"({rec['adverse']} of {rec['completed']}) — proposing a human owner.",
        )
    return (
        suggested_type,
        "Fresh process map — proposed by task nature; partner decides where to insert AI.",
    )
