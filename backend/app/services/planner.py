from __future__ import annotations

from app.core.audit import record_accountability
from app.db.repo import Repo
from app.db.tables import ASSOCIATES, CORPUS, PLANS, TASKS
from app.fixtures import firm_standard, process_doc
from app.providers.base import LLMProvider


def propose_plan(repo: Repo, *, case: dict, provider: LLMProvider, actor: str) -> dict:
    """Scope the case goal into a proposed task list with assignee type, severity and inputs. The
    plan is a PROPOSAL — nothing dispatches until the partner approves it (architecture.md §6).

    Severity is the partner's up-front choice on the case (architecture.md §7.1) and is applied here
    as the default for every task — never inferred by the model. Task enrichment (severity, process
    section, default assignee, ordering, target validation) lives in this service so the mock and
    real providers stay symmetric and only need to return raw task scoping."""
    # Prefer documents the partner uploaded to THIS case; fall back to the seeded demo drafts so the
    # offline demo still produces a plan when nothing was uploaded.
    all_drafts = [d for d in repo.list(CORPUS) if d["kind"] == "draft"]
    uploaded = [d for d in all_drafts if d.get("case_id") == case["id"]]
    drafts = uploaded or [d for d in all_drafts if not d.get("case_id")]

    associates = repo.list(ASSOCIATES)
    proc = repo.get(CORPUS, case.get("process_doc_id") or process_doc()["id"]) or process_doc()
    task_types = proc.get("task_types", {})

    proposed = provider.plan_case(
        goal=case["goal"],
        brief=case["brief_text"],
        process_doc=proc,
        drafts=drafts,
        associates=associates,
        instructions=case.get("instructions", ""),
    )

    plan = repo.insert(
        PLANS,
        {"case_id": case["id"], "status": "proposed", "approved_by": None, "approved_at": None},
    )
    std_id = case.get("firm_standard_id") or firm_standard()["id"]
    case_severity = case.get("severity", "medium")
    draft_ids = {d["id"] for d in drafts}
    fallback_doc_id = drafts[0]["id"] if drafts else None
    humans = [a["id"] for a in associates] or [None]

    tasks = []
    for i, t in enumerate(proposed):
        task_type = t["task_type"]
        # Never trust the model's target blindly: snap an unknown id back to a real candidate doc.
        target = t.get("target_document_id")
        if target not in draft_ids:
            target = fallback_doc_id
        # Default assignee for human/hybrid work; the partner can reassign before approval.
        assignee_id = t.get("assignee_id")
        if assignee_id is None and t["assignee_type"] in ("human", "hybrid"):
            assignee_id = humans[i % len(humans)]
        tasks.append(
            repo.insert(
                TASKS,
                {
                    "case_id": case["id"],
                    "plan_id": plan["id"],
                    "title": t["title"],
                    "description": t.get("description", ""),
                    "task_type": task_type,
                    "assignee_type": t["assignee_type"],
                    "assignee_id": assignee_id,
                    # Severity is the partner's choice on the case, not a model inference.
                    "severity": case_severity,
                    "target_document_id": target,
                    "firm_standard_id": std_id,
                    "input_brief_slice": t.get("input_brief_slice", ""),
                    "input_process_section": t.get("input_process_section")
                    or task_types.get(task_type, {}).get("label", task_type),
                    "ai_instruction": t.get("ai_instruction"),
                    # The associate's half of a hybrid task, and a one-line rationale the partner
                    # can sanity-check. Both are proposals the partner can edit before approval.
                    "human_instruction": t.get("human_instruction"),
                    "rationale": t.get("rationale"),
                    "status": "proposed",
                    "order_index": t.get("order_index", i),
                },
            )
        )

    record_accountability(
        repo,
        type="plan_proposed",
        actor=actor,
        case_id=case["id"],
        payload={
            "plan_id": plan["id"],
            "n_tasks": len(tasks),
            # The partner's up-front direction is part of the delegation record.
            "instructions": case.get("instructions", ""),
        },
    )
    return {"plan": plan, "tasks": tasks}


def add_task(repo: Repo, *, case: dict, actor: str) -> dict:
    """Add a blank PROPOSED task to the latest proposed plan, for the partner to fill in. Defaults
    to an AI review of the first available draft; the partner edits it inline before approving."""
    plans = repo.list(PLANS, case_id=case["id"])
    current = plans[-1] if plans else None
    if not current:
        raise ValueError("No plan to add to — generate one first.")
    if current["status"] != "proposed":
        raise ValueError("Only a proposed plan can be edited; this plan is already approved.")

    existing = repo.list(TASKS, plan_id=current["id"])
    order = max((t.get("order_index", 0) for t in existing), default=-1) + 1

    all_drafts = [d for d in repo.list(CORPUS) if d["kind"] == "draft"]
    uploaded = [d for d in all_drafts if d.get("case_id") == case["id"]]
    drafts = uploaded or [d for d in all_drafts if not d.get("case_id")]
    target = (
        drafts[0]["id"]
        if drafts
        else (existing[0]["target_document_id"] if existing else None)
    )
    proc = repo.get(CORPUS, case.get("process_doc_id") or process_doc()["id"]) or process_doc()
    task_types = proc.get("task_types", {})
    default_type = next(iter(task_types), "review_binding_obligation")

    task = repo.insert(
        TASKS,
        {
            "case_id": case["id"],
            "plan_id": current["id"],
            "title": "New task",
            "description": "",
            "task_type": default_type,
            "assignee_type": "ai",
            "assignee_id": None,
            "severity": case.get("severity", "medium"),
            "target_document_id": target,
            "firm_standard_id": case.get("firm_standard_id") or firm_standard()["id"],
            "input_brief_slice": "",
            "input_process_section": task_types.get(default_type, {}).get("label", default_type),
            "ai_instruction": None,
            "human_instruction": None,
            "rationale": "Added by the partner.",
            "status": "proposed",
            "order_index": order,
        },
    )
    record_accountability(
        repo,
        type="task_added",
        actor=actor,
        case_id=case["id"],
        task_id=task["id"],
        payload={"plan_id": current["id"]},
    )
    return task


def revise_plan(
    repo: Repo, *, case: dict, provider: LLMProvider, feedback: str, actor: str
) -> dict:
    """Re-propose the plan from the partner's free-text direction. The provider revises the CURRENT
    tasks (preserving the partner's edits); we re-stamp the result onto a fresh PROPOSED plan, so —
    like 'regenerate' — the latest plan wins and nothing dispatches until the partner approves. The
    feedback is recorded as part of the delegation record (architecture.md §14.7)."""
    plans = repo.list(PLANS, case_id=case["id"])
    current = plans[-1] if plans else None
    if not current:
        raise ValueError("No plan to revise — generate one first.")
    if current["status"] != "proposed":
        raise ValueError("Only a proposed plan can be revised; this plan is already approved.")

    current_tasks = sorted(
        repo.list(TASKS, plan_id=current["id"]), key=lambda t: t.get("order_index", 0)
    )
    revised = provider.revise_plan(case=case, current_tasks=current_tasks, feedback=feedback)

    plan = repo.insert(
        PLANS,
        {"case_id": case["id"], "status": "proposed", "approved_by": None, "approved_at": None},
    )
    std_id = case.get("firm_standard_id") or firm_standard()["id"]
    case_severity = case.get("severity", "medium")
    draft_ids = {d["id"] for d in repo.list(CORPUS) if d["kind"] == "draft"}
    fallback_doc_id = current_tasks[0]["target_document_id"] if current_tasks else None

    tasks = []
    for i, t in enumerate(revised):
        target = t.get("target_document_id")
        if target not in draft_ids:
            target = fallback_doc_id
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
                    # Keep the partner's per-task severity edit if present; else the case default.
                    "severity": t.get("severity", case_severity),
                    "target_document_id": target,
                    "firm_standard_id": std_id,
                    "input_brief_slice": t.get("input_brief_slice", ""),
                    "input_process_section": t.get("input_process_section"),
                    "ai_instruction": t.get("ai_instruction"),
                    "human_instruction": t.get("human_instruction"),
                    "rationale": t.get("rationale"),
                    "status": "proposed",
                    "order_index": i,
                },
            )
        )

    record_accountability(
        repo,
        type="plan_revised",
        actor=actor,
        case_id=case["id"],
        payload={
            "plan_id": plan["id"],
            "from_plan_id": current["id"],
            "feedback": feedback,
            "n_tasks": len(tasks),
        },
    )
    return {"plan": plan, "tasks": tasks}
