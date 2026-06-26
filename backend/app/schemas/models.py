from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

TaskType = Literal["ma_first_draft"]
TaskStatus = Literal[
    "planning", "researching", "ranking", "evaluating", "synthesizing", "complete", "failed"
]


# --- requests ---


class TaskCreate(BaseModel):
    task_type: TaskType = "ma_first_draft"
    title: str = Field(min_length=1, max_length=300)
    brief: str = Field(min_length=1)
    eval_doc_count: int | None = Field(
        default=None, ge=1, le=50, description="N: top-ranked docs the evaluator scrutinises."
    )


class DocumentRegister(BaseModel):
    filename: str
    s3_key: str
    mime: str = "application/octet-stream"


class PresignRequest(BaseModel):
    filename: str
    content_type: str = "application/octet-stream"
    size_bytes: int = Field(ge=1, le=50 * 1024 * 1024)  # 50 MB cap


# --- responses ---


class TaskOut(BaseModel):
    id: str
    user_id: str
    task_type: str
    title: str
    brief: str
    eval_doc_count: int
    status: str
    plan_md: str | None = None
    created_at: str

    model_config = {"extra": "ignore"}


class CandidateOut(BaseModel):
    id: str
    task_id: str
    origin: str
    title: str | None = None
    url: str | None = None
    snippet: str | None = None
    rank: int | None = None
    relevance_score: float | None = None
    evaluated: bool = False
    eval_relevance: float | None = None
    eval_risk: float | None = None
    eval_uncertainty: float | None = None
    eval_notes: str | None = None
    use_in_synthesis: bool = False

    model_config = {"extra": "ignore"}


class OutputOut(BaseModel):
    id: str
    task_id: str
    version: int
    content_md: str
    created_at: str

    model_config = {"extra": "ignore"}


class PresignResponse(BaseModel):
    url: str
    s3_key: str
    fields: dict[str, Any] = {}
