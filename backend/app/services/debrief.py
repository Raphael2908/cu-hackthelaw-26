from __future__ import annotations

from app.core.audit import record_accountability
from app.db.repo import Repo
from app.db.tables import DEBRIEFS, DECISIONS, FLAGS, TASKS
from app.providers.base import LLMProvider


def generate_debrief(repo: Repo, *, case: dict, provider: LLMProvider, actor: str) -> dict:
    """At case close, generate a templated debrief from the case record: tasks done, flags raised,
    partner decisions, and carry-forward notes (architecture.md §1, breadth)."""
    tasks = repo.list(TASKS, case_id=case["id"])
    flags: list[dict] = []
    decisions: list[dict] = []
    for t in tasks:
        flags += repo.list(FLAGS, task_id=t["id"])
        decisions += repo.list(DECISIONS, task_id=t["id"])

    content = provider.generate_debrief(case=case, tasks=tasks, flags=flags, decisions=decisions)
    debrief = repo.insert(DEBRIEFS, {"case_id": case["id"], "content": content})
    record_accountability(
        repo,
        type="debrief_generated",
        actor=actor,
        case_id=case["id"],
        payload={"debrief_id": debrief["id"]},
    )
    return debrief
