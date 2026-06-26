from __future__ import annotations

from app.core.audit import record_accountability
from app.db.repo import Repo
from app.db.tables import ASSOCIATES, CORPUS, PLANS, TASKS
from app.fixtures import firm_standard, process_doc
from app.providers.base import LLMProvider


def propose_plan(repo: Repo, *, case: dict, provider: LLMProvider, actor: str) -> dict:
    """Scope the case goal into a proposed task list with assignee type, severity and inputs. The
    plan is a PROPOSAL — nothing dispatches until the partner approves it (architecture.md §6)."""
    drafts = [d for d in repo.list(CORPUS) if d["kind"] == "draft"]
    associates = repo.list(ASSOCIATES)
    proc = repo.get(CORPUS, case.get("process_doc_id") or process_doc()["id"]) or process_doc()

    proposed = provider.plan_case(
        goal=case["goal"],
        brief=case["brief_text"],
        process_doc=proc,
        drafts=drafts,
        associates=associates,
    )

    plan = repo.insert(
        PLANS,
        {"case_id": case["id"], "status": "proposed", "approved_by": None, "approved_at": None},
    )
    std_id = case.get("firm_standard_id") or firm_standard()["id"]
    tasks = []
    for t in proposed:
        tasks.append(
            repo.insert(
                TASKS,
                {
                    "case_id": case["id"],
                    "plan_id": plan["id"],
                    "title": t["title"],
                    "description": t.get("description", ""),
                    "task_type": t["task_type"],
                    "assignee_type": t["assignee_type"],
                    "assignee_id": t.get("assignee_id"),
                    "severity": t["severity"],
                    "target_document_id": t["target_document_id"],
                    "firm_standard_id": std_id,
                    "input_brief_slice": t.get("input_brief_slice", ""),
                    "input_process_section": t.get("input_process_section", ""),
                    "ai_instruction": t.get("ai_instruction"),
                    "status": "proposed",
                    "order_index": t.get("order_index", 0),
                },
            )
        )

    record_accountability(
        repo,
        type="plan_proposed",
        actor=actor,
        case_id=case["id"],
        payload={"plan_id": plan["id"], "n_tasks": len(tasks)},
    )
    return {"plan": plan, "tasks": tasks}
