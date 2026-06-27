from __future__ import annotations

from app.core.audit import record_accountability
from app.db.repo import Repo
from app.db.tables import ASSOCIATES, CORPUS, PLANS, TASKS
from app.fixtures import firm_standard, process_doc
from app.providers.base import LLMProvider
from app.services import track_record


def propose_plan(repo: Repo, *, case: dict, provider: LLMProvider, actor: str) -> dict:
    """Scope the case goal into a proposed task list with assignee type, severity and inputs. The
    plan is a PROPOSAL — nothing dispatches until the partner approves it (architecture.md §6).

    Severity is the partner's up-front choice on the case (architecture.md §7.1) and is applied here
    as the default for every task — never inferred by the model. Task enrichment (severity, process
    section, default assignee, ordering, target validation) lives in this service so the mock and
    real providers stay symmetric and only need to return raw task scoping.

    Delegation (human/ai/hybrid) is the planner agent's judgment of the task's *nature* — not a
    function of severity (architecture.md §6). On top of that, this service overlays the selected
    process map's agentic track record: a section AI has a clean record on graduates to AI;
    one with an adverse record is pulled back to a human owner. A fresh (or unselected) map is a
    clean slate, so the nature suggestion stands and the partner decides where to insert AI."""
    # Prefer documents the partner uploaded to THIS case; fall back to the seeded demo drafts so the
    # offline demo still produces a plan when nothing was uploaded.
    all_drafts = [d for d in repo.list(CORPUS) if d["kind"] == "draft"]
    uploaded = [d for d in all_drafts if d.get("case_id") == case["id"]]
    drafts = uploaded or [d for d in all_drafts if not d.get("case_id")]

    associates = repo.list(ASSOCIATES)
    proc = repo.get(CORPUS, case.get("process_doc_id") or process_doc()["id"]) or process_doc()
    task_types = proc.get("task_types", {})
    # The process map scopes the agentic track record: this map's history alone decides whether a
    # section has earned AI by default (architecture.md §6).
    record = track_record.aggregate(repo, process_doc_id=proc["id"])["by_section"]

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
    case_severity = case.get("severity", "medium")
    draft_ids = {d["id"] for d in drafts}
    fallback_doc_id = drafts[0]["id"] if drafts else None
    humans = [a["id"] for a in associates] or [None]

    tasks = []
    graduated: list[str] = []  # sections the track record pushed to AI (for the audit record)
    pulled_back: list[str] = []  # sections it pulled back to a human owner
    for i, t in enumerate(proposed):
        task_type = t["task_type"]
        # Never trust the model's target blindly: snap an unknown id back to a real candidate doc.
        target = t.get("target_document_id")
        if target not in draft_ids:
            target = fallback_doc_id
        # Delegation = the agent's nature-based suggestion, adjusted by this map's track record.
        assignee_type, assignee_rationale = track_record.apply_record(
            suggested_type=t["assignee_type"], section_record=record.get(task_type)
        )
        if assignee_type != t["assignee_type"]:
            (graduated if assignee_type == "ai" else pulled_back).append(task_type)
        # Default assignee for human/hybrid work; the partner can reassign before approval.
        assignee_id = t.get("assignee_id")
        if assignee_id is None and assignee_type in ("human", "hybrid"):
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
                    "assignee_type": assignee_type,
                    "assignee_id": assignee_id,
                    "assignee_rationale": assignee_rationale,
                    # Severity is the partner's choice on the case, not a model inference.
                    "severity": case_severity,
                    "target_document_id": target,
                    "firm_standard_id": std_id,
                    "input_brief_slice": t.get("input_brief_slice", ""),
                    "input_process_section": t.get("input_process_section")
                    or task_types.get(task_type, {}).get("label", task_type),
                    "ai_instruction": t.get("ai_instruction"),
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
            "process_doc_id": proc["id"],
            "track_record_consulted": True,
            "graduated_to_ai": graduated,
            "pulled_back_to_human": pulled_back,
        },
    )
    return {"plan": plan, "tasks": tasks}
