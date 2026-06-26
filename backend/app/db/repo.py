from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


class Repo(ABC):
    """All data access goes through this resource-typed interface. `get_*` return None on a miss;
    handlers map that to 404. Handlers/tasks call `get_repo()` — never the Supabase SDK directly."""

    # --- tasks ---
    @abstractmethod
    def create_task(self, *, user_id: str, **fields: Any) -> dict: ...
    @abstractmethod
    def get_task(self, task_id: str) -> dict | None: ...
    @abstractmethod
    def list_tasks(self, user_id: str) -> list[dict]: ...
    @abstractmethod
    def update_task(self, task_id: str, **fields: Any) -> dict | None: ...

    # --- documents ---
    @abstractmethod
    def create_document(self, *, task_id: str, user_id: str, **fields: Any) -> dict: ...
    @abstractmethod
    def list_documents(self, task_id: str) -> list[dict]: ...

    # --- candidates (the evidence pool) ---
    @abstractmethod
    def create_candidate(self, *, task_id: str, **fields: Any) -> dict: ...
    @abstractmethod
    def list_candidates(self, task_id: str) -> list[dict]: ...
    @abstractmethod
    def update_candidate(self, candidate_id: str, **fields: Any) -> dict | None: ...

    # --- agent_runs ---
    @abstractmethod
    def create_agent_run(self, *, task_id: str, agent: str, **fields: Any) -> dict: ...
    @abstractmethod
    def update_agent_run(self, run_id: str, **fields: Any) -> dict | None: ...
    @abstractmethod
    def list_agent_runs(self, task_id: str) -> list[dict]: ...
    @abstractmethod
    def list_runs_stuck_running(self, older_than_iso: str) -> list[dict]: ...

    # --- outputs ---
    @abstractmethod
    def create_output(self, *, task_id: str, **fields: Any) -> dict: ...
    @abstractmethod
    def latest_output(self, task_id: str) -> dict | None: ...


class SupabaseRepo(Repo):
    def __init__(self) -> None:
        from app.db.supabase import get_supabase

        self._sb = get_supabase()

    def _insert(self, table: str, row: dict) -> dict:
        return self._sb.table(table).insert(row).execute().data[0]

    def _update(self, table: str, row_id: str, fields: dict) -> dict | None:
        data = self._sb.table(table).update(fields).eq("id", row_id).execute().data
        return data[0] if data else None

    def _one(self, table: str, row_id: str) -> dict | None:
        data = self._sb.table(table).select("*").eq("id", row_id).limit(1).execute().data
        return data[0] if data else None

    # tasks
    def create_task(self, *, user_id: str, **fields: Any) -> dict:
        return self._insert("tasks", {"user_id": user_id, **fields})

    def get_task(self, task_id: str) -> dict | None:
        return self._one("tasks", task_id)

    def list_tasks(self, user_id: str) -> list[dict]:
        return (
            self._sb.table("tasks")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
            .data
        )

    def update_task(self, task_id: str, **fields: Any) -> dict | None:
        return self._update("tasks", task_id, fields)

    # documents
    def create_document(self, *, task_id: str, user_id: str, **fields: Any) -> dict:
        return self._insert("documents", {"task_id": task_id, "user_id": user_id, **fields})

    def list_documents(self, task_id: str) -> list[dict]:
        return self._sb.table("documents").select("*").eq("task_id", task_id).execute().data

    # candidates
    def create_candidate(self, *, task_id: str, **fields: Any) -> dict:
        return self._insert("candidates", {"task_id": task_id, **fields})

    def list_candidates(self, task_id: str) -> list[dict]:
        return (
            self._sb.table("candidates")
            .select("*")
            .eq("task_id", task_id)
            .order("rank", desc=False)
            .execute()
            .data
        )

    def update_candidate(self, candidate_id: str, **fields: Any) -> dict | None:
        return self._update("candidates", candidate_id, fields)

    # agent_runs
    def create_agent_run(self, *, task_id: str, agent: str, **fields: Any) -> dict:
        return self._insert("agent_runs", {"task_id": task_id, "agent": agent, **fields})

    def update_agent_run(self, run_id: str, **fields: Any) -> dict | None:
        return self._update("agent_runs", run_id, fields)

    def list_agent_runs(self, task_id: str) -> list[dict]:
        return self._sb.table("agent_runs").select("*").eq("task_id", task_id).execute().data

    def list_runs_stuck_running(self, older_than_iso: str) -> list[dict]:
        return (
            self._sb.table("agent_runs")
            .select("*")
            .eq("status", "running")
            .lt("started_at", older_than_iso)
            .execute()
            .data
        )

    # outputs
    def create_output(self, *, task_id: str, **fields: Any) -> dict:
        return self._insert("outputs", {"task_id": task_id, **fields})

    def latest_output(self, task_id: str) -> dict | None:
        data = (
            self._sb.table("outputs")
            .select("*")
            .eq("task_id", task_id)
            .order("version", desc=True)
            .limit(1)
            .execute()
            .data
        )
        return data[0] if data else None


class InMemoryRepo(Repo):
    """Dict-backed double for tests and keyless local runs. No network."""

    def __init__(self) -> None:
        self._tasks: dict[str, dict] = {}
        self._documents: dict[str, dict] = {}
        self._candidates: dict[str, dict] = {}
        self._agent_runs: dict[str, dict] = {}
        self._outputs: dict[str, dict] = {}

    def _new(self, store: dict[str, dict], row: dict) -> dict:
        row = {"id": _uuid(), "created_at": _now(), **row}
        store[row["id"]] = row
        return row

    # tasks
    def create_task(self, *, user_id: str, **fields: Any) -> dict:
        return self._new(self._tasks, {"user_id": user_id, **fields})

    def get_task(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    def list_tasks(self, user_id: str) -> list[dict]:
        rows = [t for t in self._tasks.values() if t["user_id"] == user_id]
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)

    def update_task(self, task_id: str, **fields: Any) -> dict | None:
        row = self._tasks.get(task_id)
        if row is None:
            return None
        row.update(fields)
        return row

    # documents
    def create_document(self, *, task_id: str, user_id: str, **fields: Any) -> dict:
        return self._new(self._documents, {"task_id": task_id, "user_id": user_id, **fields})

    def list_documents(self, task_id: str) -> list[dict]:
        return [d for d in self._documents.values() if d["task_id"] == task_id]

    # candidates
    def create_candidate(self, *, task_id: str, **fields: Any) -> dict:
        return self._new(self._candidates, {"task_id": task_id, **fields})

    def list_candidates(self, task_id: str) -> list[dict]:
        rows = [c for c in self._candidates.values() if c["task_id"] == task_id]
        return sorted(rows, key=lambda r: (r.get("rank") is None, r.get("rank") or 0))

    def update_candidate(self, candidate_id: str, **fields: Any) -> dict | None:
        row = self._candidates.get(candidate_id)
        if row is None:
            return None
        row.update(fields)
        return row

    # agent_runs
    def create_agent_run(self, *, task_id: str, agent: str, **fields: Any) -> dict:
        return self._new(self._agent_runs, {"task_id": task_id, "agent": agent, **fields})

    def update_agent_run(self, run_id: str, **fields: Any) -> dict | None:
        row = self._agent_runs.get(run_id)
        if row is None:
            return None
        row.update(fields)
        return row

    def list_agent_runs(self, task_id: str) -> list[dict]:
        return [r for r in self._agent_runs.values() if r["task_id"] == task_id]

    def list_runs_stuck_running(self, older_than_iso: str) -> list[dict]:
        return [
            r
            for r in self._agent_runs.values()
            if r.get("status") == "running" and (r.get("started_at") or "") < older_than_iso
        ]

    # outputs
    def create_output(self, *, task_id: str, **fields: Any) -> dict:
        return self._new(self._outputs, {"task_id": task_id, **fields})

    def latest_output(self, task_id: str) -> dict | None:
        rows = [o for o in self._outputs.values() if o["task_id"] == task_id]
        if not rows:
            return None
        return max(rows, key=lambda r: r.get("version", 0))


_repo: Repo | None = None


def set_repo(r: Repo | None) -> None:
    global _repo
    _repo = r


def get_repo() -> Repo:
    global _repo
    if _repo is None:
        _repo = SupabaseRepo()  # lazy in prod; raises if DB unconfigured
    return _repo
