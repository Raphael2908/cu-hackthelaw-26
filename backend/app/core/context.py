from __future__ import annotations

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_task_id: ContextVar[str | None] = ContextVar("task_id", default=None)
_agent_run_id: ContextVar[str | None] = ContextVar("agent_run_id", default=None)


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()


def set_task_id(value: str | None) -> None:
    _task_id.set(value)


def get_task_id() -> str | None:
    return _task_id.get()


def set_agent_run_id(value: str | None) -> None:
    _agent_run_id.set(value)


def get_agent_run_id() -> str | None:
    return _agent_run_id.get()


def correlation_fields() -> dict[str, str]:
    """Current correlation ids, for log records."""
    out: dict[str, str] = {}
    if rid := _request_id.get():
        out["request_id"] = rid
    if tid := _task_id.get():
        out["task_id"] = tid
    if arid := _agent_run_id.get():
        out["agent_run_id"] = arid
    return out
