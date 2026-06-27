from __future__ import annotations

from app import fixtures
from app.config import settings
from app.db.repo import Repo
from app.db.tables import ASSOCIATES, CASES, CORPUS, DECISIONS, TASKS

# A prior, closed matter that ran on the seeded process map ("process-doc-review", aka Map A). It
# gives that map a clean agentic track record on its binding-obligation section, so the planner
# graduates that section to AI by default and the track-record view has real history to show. The
# second seeded map ("process-map-nda-fresh", in corpus.json) deliberately has NO history, so it
# demonstrates the clean-slate split. Delegation is still decided by task nature (§6); the record
# only graduates / pulls back on top of that.
_HISTORY_CASE_ID = "case-seed-prior-dpa"
_HISTORY_PROCESS_DOC_ID = "process-doc-review"
_HISTORY_SECTION = "review_binding_obligation"


def _seed_track_record(repo: Repo) -> None:
    """Idempotently seed a closed prior matter with AI_TRACK_RECORD_MIN clean, signed-off AI tasks
    on the seeded process map's binding-obligation section."""
    if repo.get(CASES, _HISTORY_CASE_ID):
        return
    repo.insert(
        CASES,
        {
            "id": _HISTORY_CASE_ID,
            "title": "Prior matter — DPA reviews (seed)",
            "brief_text": "Earlier supplier-agreement reviews completed on this process map.",
            "goal": "Historical record establishing the AI track record for this process map.",
            "severity": "high",
            "process_doc_id": _HISTORY_PROCESS_DOC_ID,
            "firm_standard_id": fixtures.firm_standard()["id"],
            "status": "closed",
            "created_by": "seed",
        },
    )
    for i in range(max(1, settings.AI_TRACK_RECORD_MIN)):
        task = repo.insert(
            TASKS,
            {
                "case_id": _HISTORY_CASE_ID,
                "plan_id": None,
                "title": f"Review DPA binding obligations — prior matter {i + 1}",
                "description": "Completed AI review of liability / data-transfer clauses.",
                "task_type": _HISTORY_SECTION,
                "assignee_type": "ai",
                "assignee_id": None,
                "assignee_rationale": "Seeded prior matter.",
                "severity": "high",
                "target_document_id": None,
                "firm_standard_id": fixtures.firm_standard()["id"],
                "input_brief_slice": "",
                "input_process_section": "Review of a binding obligation (liability/transfer)",
                "ai_instruction": None,
                "status": "signed_off",
                "order_index": i,
            },
        )
        # Signed off WITHOUT amendment → a clean outcome (architecture.md §6 / track_record).
        repo.insert(
            DECISIONS,
            {
                "task_id": task["id"],
                "action": "approve",
                "note": "AI review accepted as drafted.",
                "amendment": None,
                "decided_by": "seed",
                "decided_at": task["created_at"],
            },
        )


def seed(repo: Repo) -> None:
    """Idempotently load the corpus (EU Cellar-modelled docs, firm standard, process maps, drafts)
    and the human-maintained associate registry, plus a prior matter establishing one process map's
    agentic track record. Safe to call on every boot."""
    if not repo.list(CORPUS):
        for doc in fixtures.corpus():
            repo.insert(CORPUS, dict(doc))
    if not repo.list(ASSOCIATES):
        for a in fixtures.associates():
            repo.insert(ASSOCIATES, dict(a))
    _seed_track_record(repo)
