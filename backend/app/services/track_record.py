from __future__ import annotations

from app.config import settings
from app.db.repo import Repo
from app.db.tables import CASES, DECISIONS, FLAGS, TASKS

# A completed agentic task is in one of these terminal states (architecture.md §5).
_TERMINAL = {"signed_off", "cleared", "escalated"}
# Only AI/hybrid work builds an AI track record — we never grade purely human work (§14).
_AGENTIC = {"ai", "hybrid"}
# The three independent checker signals (architecture.md §7.2), in display order.
_SIGNALS = ("citation_support", "precedent_deviation", "multi_run_disagreement")


def _outcome(task: dict, last_decision: dict | None) -> str:
    """Reduce a completed agentic task to a single outcome the log can show and the planner can
    count. `clean` = the AI work stood (auto-cleared, or signed off without amendment); `adverse` =
    a human had to amend it or it was rejected/escalated. Never a verdict — just what happened."""
    status = task.get("status")
    if status == "escalated":
        return "adverse"
    if status == "cleared":
        return "clean"
    if status == "signed_off":
        action = last_decision.get("action") if last_decision else None
        return "adverse" if action == "amend" else "clean"
    return "clean"


def aggregate(repo: Repo, *, process_doc_id: str) -> dict:
    """The agentic track record for ONE process map (architecture.md §6).

    Walks every completed AI/hybrid task whose case used `process_doc_id`, bucketed by section
    (`task_type`). The record is scoped to the map — a fresh map is a clean slate; a reused map
    carries history the planner consults to graduate a section to AI (clean record) or pull it back
    to a human owner (adverse record). Returns per-section counts plus a flat completed-task log.

    Each section also carries the *feedback detail* a partner reads to understand a record: the
    flags that were raised broken down by the three checker signals (hard/soft), the lessons to
    carry forward (the partner's own amendment/rejection words), and the matters the section ran in.
    These stay counts + the partner's recorded words + flags — never a verdict (§1, §14)."""
    cases = {c["id"]: c for c in repo.list(CASES)}

    by_section: dict[str, dict] = {}
    section_cases: dict[str, dict] = {}  # section -> case_id -> drill-down row
    log: list[dict] = []
    for task in repo.list(TASKS):
        if task.get("assignee_type") not in _AGENTIC or task.get("status") not in _TERMINAL:
            continue
        case = cases.get(task.get("case_id"), {})
        if case.get("process_doc_id") != process_doc_id:
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
                "flags_by_signal": {s: {"count": 0, "hard": 0} for s in _SIGNALS},
                "hard_flags": 0,
                "lessons": [],
            },
        )
        decisions = repo.list(DECISIONS, task_id=task["id"])
        last_decision = decisions[-1] if decisions else None
        outcome = _outcome(task, last_decision)
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

        # Flags raised on this AI work, by signal (hard/soft visible separately).
        for f in repo.list(FLAGS, task_id=task["id"]):
            bucket = rec["flags_by_signal"].setdefault(
                f["signal_type"], {"count": 0, "hard": 0}
            )
            bucket["count"] += 1
            if f.get("hard"):
                bucket["hard"] += 1
                rec["hard_flags"] += 1

        # The lesson to carry forward — the partner's own words on what had to change.
        if last_decision and last_decision.get("action") in ("amend", "reject"):
            text = (last_decision.get("amendment") or last_decision.get("note") or "").strip()
            if text:
                rec["lessons"].append(
                    {
                        "case_id": task.get("case_id"),
                        "case_title": case.get("title", task.get("case_id")),
                        "action": last_decision["action"],
                        "text": text,
                    }
                )

        # Drill-down: the matters this section ran in.
        crow = section_cases.setdefault(section, {}).setdefault(
            task.get("case_id"),
            {
                "case_id": task.get("case_id"),
                "title": case.get("title", task.get("case_id")),
                "status": case.get("status", "open"),
                "completed": 0,
                "adverse": 0,
            },
        )
        crow["completed"] += 1
        if outcome == "adverse":
            crow["adverse"] += 1

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

    for section, rec in by_section.items():
        rec["clean"] = rec["completed"] >= settings.AI_TRACK_RECORD_MIN and rec["adverse"] == 0
        rec["cases"] = sorted(
            section_cases.get(section, {}).values(),
            key=lambda r: r["adverse"],
            reverse=True,
        )

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
