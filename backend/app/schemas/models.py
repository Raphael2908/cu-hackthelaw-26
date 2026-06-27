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


class TaskPatch(BaseModel):
    """Edit a *proposed* task before plan approval (architecture.md §6)."""

    title: str | None = None
    description: str | None = None
    assignee_type: AssigneeType | None = None
    assignee_id: str | None = None
    severity: Severity | None = None
    ai_instruction: str | None = None
    # The associate's half of a hybrid task — editable by the partner before approval, same as
    # ai_instruction (the planner proposes both).
    human_instruction: str | None = None


class PlanReviseRequest(BaseModel):
    """The partner's free-text direction for revising a proposed plan (architecture.md §6)."""

    feedback: str


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


class MessageCreate(BaseModel):
    """A note on a task. From an associate it raises a question to the partner; from the partner it
    answers an open question and hands the task back to the associate."""

    body: str
