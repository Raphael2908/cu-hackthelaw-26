from __future__ import annotations

from app.db.repo import Repo
from app.db.tables import CORPUS, SUBMISSIONS
from app.fixtures import firm_standard
from app.providers.base import LLMProvider


def run_review(repo: Repo, *, task: dict, provider: LLMProvider, produced_by: str = "ai") -> dict:
    """The worker (depth): review the task's target document against the firm standard and emit a
    structured submission — findings, the clauses relied on, the citations made, and the audit trail
    of sources used. No verdict (architecture.md §14.1)."""
    draft = repo.get(CORPUS, task["target_document_id"])
    if not draft:
        raise ValueError(f"Target document {task['target_document_id']} not found.")
    std = repo.get(CORPUS, task.get("firm_standard_id") or firm_standard()["id"]) or firm_standard()

    result = provider.review_document(
        draft=draft,
        firm_standard=std,
        process_section=task.get("input_process_section", ""),
        run_index=0,
    )
    submission = {
        "task_id": task["id"],
        "produced_by": produced_by,
        "run_index": 0,
        "summary": result.summary,
        "findings": [
            {
                "id": f.id,
                "clause_ref": f.clause_ref,
                "statement": f.statement,
                "citation": f.citation,
            }
            for f in result.findings
        ],
        "citations": [f.citation for f in result.findings if f.citation],
        "clauses_relied_on": result.clauses_relied_on,
        "audit_sources": result.audit_sources,
    }
    return repo.insert(SUBMISSIONS, submission)
