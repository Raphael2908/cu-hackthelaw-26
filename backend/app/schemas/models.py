from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "extreme"]
AssigneeType = Literal["human", "ai", "hybrid"]

# The kind of work a task delegates to the (now flexible) worker. Each kind drives a different
# instruction + output shape (architecture.md §6). `review` reproduces the original behaviour, so it
# is the default everywhere and every existing seed/test keeps working unchanged.
TaskKind = Literal["review", "summarize", "extract", "draft"]
# The supervision signals the checker can run on a submission. A task declares which apply; a
# non-applicable signal is excluded from the uncertainty composite, never fabricated (§7.2, §14.4).
CheckName = Literal["citation_support", "precedent_deviation", "multi_run_disagreement"]
DEFAULT_CHECKS: tuple[CheckName, ...] = (
    "citation_support",
    "precedent_deviation",
    "multi_run_disagreement",
)


class AssociateCreate(BaseModel):
    name: str
    practice_area: str
    current_load: int = 0
    capacity: int = 5


class CaseCreate(BaseModel):
    title: str
    brief_text: str
    goal: str
    # Severity is the partner's up-front choice (architecture.md §7.1), never model-inferred. It
    # becomes the default for every task in the plan; the partner can still override per task.
    severity: Severity = "medium"
    # Default to the seeded corpus' process doc + firm standard if not supplied.
    process_doc_id: str | None = None
    firm_standard_id: str | None = None


class ProcessMapSection(BaseModel):
    """One section of a process map = a task type. `severity` is the firm's declared risk band for
    the section (metadata only); delegation is decided by task nature, not this band.

    The remaining fields are the partner-authored *worker spec* (architecture.md §6): how the
    flexible worker should execute this task type. They are optional with back-compatible defaults —
    a section that omits them behaves exactly like the original "review a draft against the firm
    standard" task (`kind=review`, all three checks, a firm standard required)."""

    label: str
    severity: Severity = "medium"
    # The kind of work (and therefore the output shape) the worker produces for this section.
    kind: TaskKind = "review"
    # The partner's instruction to the worker. None → the worker falls back to the default review
    # instruction. The planner may append a per-task `ai_instruction` on top of this.
    instruction: str | None = None
    # A checklist of points the worker must address — the partner-authored "process map" spec.
    checklist: list[str] = Field(default_factory=list)
    # Which supervision signals apply to this task type. Defaults to all three.
    checks: list[CheckName] = Field(default_factory=lambda: list(DEFAULT_CHECKS))
    # Whether precedent-deviation applies (i.e. the task is checked against a firm standard). A
    # from-scratch draft or a summary has no standard to deviate from.
    requires_standard: bool = True


# --- Per-task-type worker output payloads (architecture.md §6) -----------------------------------
# Each non-review kind carries its own structured product in the submission's `payload`, validated
# in real mode against the model below. The universal `findings` list stays the checkable-claims
# seam the checker reads, so per-type payloads never reshape what supervision consumes.


class SummarizePayload(BaseModel):
    key_points: list[str] = Field(default_factory=list)


class ExtractObligation(BaseModel):
    text: str
    party: str = ""
    locator: str = ""


class ExtractPayload(BaseModel):
    obligations: list[ExtractObligation] = Field(default_factory=list)


class DraftPayload(BaseModel):
    draft_text: str = ""
    clause_ref: str = ""


# `review` has no payload model — its product is the `findings` list itself, so it maps to nothing.
PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "summarize": SummarizePayload,
    "extract": ExtractPayload,
    "draft": DraftPayload,
}


class ProcessMapCreate(BaseModel):
    """Lightweight structured create for a process map (architecture.md §6). No document parsing —
    the partner names the map and its sections; uploading a real process-map document is a follow-up
    (see todo.md). Stored as a `process_doc` corpus document."""

    title: str
    task_types: dict[str, ProcessMapSection]


class TaskPatch(BaseModel):
    """Edit a *proposed* task before plan approval (architecture.md §6)."""

    title: str | None = None
    description: str | None = None
    assignee_type: AssigneeType | None = None
    assignee_id: str | None = None
    severity: Severity | None = None
    ai_instruction: str | None = None


class SubmissionCreate(BaseModel):
    """A human associate submitting work back into the flow."""

    summary: str
    findings: list[dict] = Field(default_factory=list)


class DecisionCreate(BaseModel):
    action: Literal["approve", "amend", "reject"]
    note: str = ""
    amendment: str | None = None


class ReassignRequest(BaseModel):
    """Partner-approved redo. Never automatic (architecture.md §14.6)."""

    assignee_type: AssigneeType
    assignee_id: str | None = None
    note: str = ""
