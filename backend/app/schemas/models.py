from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "extreme"]
AssigneeType = Literal["human", "ai", "hybrid"]


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
    the section (metadata only); delegation is decided by task nature, not this band."""

    label: str
    severity: Severity = "medium"


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
