from __future__ import annotations

from app.core.audit import record_accountability
from app.db.repo import Repo
from app.db.tables import DEBRIEFS, DECISIONS, FLAGS, TASKS
from app.providers.base import LLMProvider

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "extreme": 3}


def _flag_view(f: dict) -> dict:
    """The checkable bits of a flag the debrief surfaces — incl. both source/work refs so the
    partner can still reach the source (and the quoting passage) in one click."""
    return {
        "signal_type": f["signal_type"],
        "hard": bool(f.get("hard")),
        "title": f["title"],
        "description": f.get("description", ""),
        "source_ref": f.get("source_ref"),
        "work_ref": f.get("work_ref"),
    }


def generate_debrief(repo: Repo, *, case: dict, provider: LLMProvider, actor: str) -> dict:
    """At case close, compose a structured, issue-centric debrief from the case record. Per task
    that needed attention we join its flags + the partner's decision into ONE issue (the reader
    never re-joins the tables); routine cleared work collapses to a count; carry-forward comes from
    the provider. Recomposition and ordering only — never a verdict (architecture.md §1, §14)."""
    tasks = repo.list(TASKS, case_id=case["id"])
    all_flags: list[dict] = []
    all_decisions: list[dict] = []
    issues: list[dict] = []
    cleared: list[dict] = []

    for t in tasks:
        flags = repo.list(FLAGS, task_id=t["id"])
        decisions = repo.list(DECISIONS, task_id=t["id"])
        all_flags += flags
        all_decisions += decisions
        decision = decisions[-1] if decisions else None
        if flags or decision:
            issues.append(
                {
                    "task_title": t["title"],
                    "severity": t["severity"],
                    "status": t["status"],
                    "assignee_type": t["assignee_type"],
                    "flags": [_flag_view(f) for f in flags],
                    "decision": (
                        {
                            "action": decision["action"],
                            "note": decision.get("note", ""),
                            "amendment": decision.get("amendment"),
                        }
                        if decision
                        else None
                    ),
                }
            )
        else:
            cleared.append(
                {"task_title": t["title"], "severity": t["severity"], "status": t["status"]}
            )

    # Worst-first: hard flags first, then higher severity, then more flags. A sort, not a judgment.
    issues.sort(
        key=lambda i: (
            any(f["hard"] for f in i["flags"]),
            _SEVERITY_RANK.get(i["severity"], 0),
            len(i["flags"]),
        ),
        reverse=True,
    )

    carry_forward = provider.debrief_carry_forward(
        case=case, tasks=tasks, flags=all_flags, decisions=all_decisions
    )

    report = {
        "case_title": case["title"],
        "goal": case.get("goal", ""),
        "summary": {
            "tasks": len(tasks),
            "needs_attention": len(issues),
            "cleared": len(cleared),
            "hard_flags": sum(1 for f in all_flags if f.get("hard")),
            "rejected": sum(1 for d in all_decisions if d.get("action") == "reject"),
            "carry_forward": len(carry_forward),
        },
        "issues": issues,
        "cleared": cleared,
        "carry_forward": carry_forward,
    }

    debrief = repo.insert(DEBRIEFS, {"case_id": case["id"], "content": report})
    record_accountability(
        repo,
        type="debrief_generated",
        actor=actor,
        case_id=case["id"],
        payload={"debrief_id": debrief["id"]},
    )
    return debrief
