from __future__ import annotations

from dataclasses import dataclass

from app.db.repo import Repo
from app.db.tables import CORPUS
from app.fixtures import firm_standard
from app.schemas.models import DEFAULT_CHECKS

# The instruction the worker falls back to when a process-map section declares no custom one — i.e.
# the original "review a draft against the firm standard" behaviour. The STRICT-JSON / no-verdict
# envelope lives in the provider (architecture.md §14.1); this is only the task framing.
_DEFAULT_REVIEW_INSTRUCTION = (
    "You are a legal document reviewer. Review the DRAFT against the FIRM STANDARD and surface "
    "checkable observations about where it deviates from the standard or relies on authority that "
    "does not support it. Do not render a pass/fail verdict. "
    "Process section in focus: {process_section}."
)


def normalize_section(raw: dict | None) -> dict:
    """Default the worker-spec keys at READ time. Seeded process maps in ``corpus.json`` are raw
    dicts that never pass through ``ProcessMapSection`` validation, so the defaults must be applied
    here too — not only in the Pydantic model (architecture.md §6)."""
    raw = raw or {}
    return {
        "label": raw.get("label", ""),
        "severity": raw.get("severity", "medium"),
        "kind": raw.get("kind", "review"),
        "instruction": raw.get("instruction"),
        "checklist": raw.get("checklist") or [],
        "checks": list(raw.get("checks") or DEFAULT_CHECKS),
        "requires_standard": raw.get("requires_standard", True),
    }


@dataclass
class TaskSpec:
    """Everything the worker needs to execute one delegated task, resolved once. Built by BOTH the
    worker's first pass and the checker's multi-run re-runs, so the runs compared by the
    disagreement signal are provably the same call (architecture.md §7.2)."""

    kind: str
    instruction: str
    documents: list[dict]
    reference: dict | None
    checklist: list[str]
    applicable_checks: list[str]

    def run_kwargs(self, *, run_index: int = 0, source_lookup=None) -> dict:
        """Keyword args for ``provider.run_task``. Centralised so first pass and re-runs match."""
        return {
            "kind": self.kind,
            "instruction": self.instruction,
            "documents": self.documents,
            "reference": self.reference,
            "checklist": self.checklist,
            "run_index": run_index,
            "source_lookup": source_lookup,
        }


def build_task_spec(repo: Repo, task: dict) -> TaskSpec:
    """Resolve a task row into a concrete worker spec. The firm standard is resolved ONLY when the
    task requires one — a no-standard task (e.g. a from-scratch draft or a summary) gets
    ``reference=None`` rather than a silently invented fallback, so precedent-deviation can skip it
    cleanly (architecture.md §14.4)."""
    target = (
        repo.get(CORPUS, task["target_document_id"]) if task.get("target_document_id") else None
    )
    documents = [target] if target else []

    reference = None
    if task.get("requires_standard", True):
        reference = (
            repo.get(CORPUS, task.get("firm_standard_id") or firm_standard()["id"])
            or firm_standard()
        )

    instruction = task.get("worker_instruction") or _DEFAULT_REVIEW_INSTRUCTION.format(
        process_section=task.get("input_process_section", "")
    )
    ai_instruction = task.get("ai_instruction")
    if ai_instruction:
        # The planner's per-task instruction layers on top of the section instruction.
        instruction = f"{instruction}\n\nTASK-SPECIFIC INSTRUCTION:\n{ai_instruction}"

    return TaskSpec(
        kind=task.get("output_kind") or "review",
        instruction=instruction,
        documents=documents,
        reference=reference,
        checklist=task.get("checklist") or [],
        applicable_checks=task.get("applicable_checks") or list(DEFAULT_CHECKS),
    )
