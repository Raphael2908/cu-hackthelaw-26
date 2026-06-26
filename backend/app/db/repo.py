from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings
from app.db.tables import ALL_TABLES


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


def _matches(record: dict, filters: dict) -> bool:
    return all(record.get(k) == v for k, v in filters.items())


class Repo(ABC):
    """Single data-access seam. All resources are stored uniformly as dict records; each row
    carries an `id`, a monotonically increasing `seq` (for deterministic ordering, e.g. the audit
    chain), and a `created_at`. Services never touch the storage SDK directly."""

    @abstractmethod
    def insert(self, table: str, record: dict) -> dict: ...

    @abstractmethod
    def get(self, table: str, id: str) -> dict | None: ...

    @abstractmethod
    def list(self, table: str, **filters) -> list[dict]:
        """Records matching equality `filters`, ordered by insertion (`seq` ascending)."""

    @abstractmethod
    def update(self, table: str, id: str, fields: dict) -> dict | None: ...

    @abstractmethod
    def last(self, table: str) -> dict | None:
        """The most recently inserted record in a table, or None. Used by the audit chain."""


class InMemoryRepo(Repo):
    """Dict-backed double for tests. No network, no disk."""

    def __init__(self) -> None:
        self._data: dict[str, list[dict]] = {t: [] for t in ALL_TABLES}
        self._seq = 0
        self._lock = threading.Lock()

    def _stamp(self, record: dict) -> dict:
        with self._lock:
            self._seq += 1
            seq = self._seq
        rec = dict(record)
        rec.setdefault("id", _new_id())
        rec.setdefault("created_at", _now())
        rec["seq"] = seq
        return rec

    def insert(self, table: str, record: dict) -> dict:
        rec = self._stamp(record)
        self._data.setdefault(table, []).append(rec)
        return dict(rec)

    def get(self, table: str, id: str) -> dict | None:
        for rec in self._data.get(table, []):
            if rec["id"] == id:
                return dict(rec)
        return None

    def list(self, table: str, **filters) -> list[dict]:
        rows = [r for r in self._data.get(table, []) if _matches(r, filters)]
        rows.sort(key=lambda r: r["seq"])
        return [dict(r) for r in rows]

    def update(self, table: str, id: str, fields: dict) -> dict | None:
        for rec in self._data.get(table, []):
            if rec["id"] == id:
                rec.update(fields)
                return dict(rec)
        return None

    def last(self, table: str) -> dict | None:
        rows = self._data.get(table, [])
        if not rows:
            return None
        return dict(max(rows, key=lambda r: r["seq"]))


class SqliteRepo(Repo):
    """SQLite-backed store. Each logical table is one physical table of (id, seq, created_at, data)
    where `data` is the JSON-serialized record. Small dataset → filtering happens in Python after
    load, which keeps the storage layer trivial and the resource set easy to extend."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or settings.SQLITE_PATH
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI may serve from a threadpool; we guard with a lock.
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            for table in ALL_TABLES:
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, seq INTEGER, created_at TEXT, data TEXT)"
                )
            self._conn.commit()

    def _next_seq(self) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT COALESCE(MAX(m), 0) FROM ("
            + " UNION ALL ".join(f"SELECT MAX(seq) AS m FROM {t}" for t in ALL_TABLES)
            + ")"
        )
        return int(cur.fetchone()[0] or 0) + 1

    def insert(self, table: str, record: dict) -> dict:
        with self._lock:
            rec = dict(record)
            rec.setdefault("id", _new_id())
            rec.setdefault("created_at", _now())
            rec["seq"] = self._next_seq()
            self._conn.execute(
                f"INSERT INTO {table} (id, seq, created_at, data) VALUES (?, ?, ?, ?)",
                (rec["id"], rec["seq"], rec["created_at"], json.dumps(rec)),
            )
            self._conn.commit()
            return dict(rec)

    def get(self, table: str, id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(f"SELECT data FROM {table} WHERE id = ?", (id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, table: str, **filters) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(f"SELECT data FROM {table} ORDER BY seq ASC").fetchall()
        out = [json.loads(r[0]) for r in rows]
        return [r for r in out if _matches(r, filters)]

    def update(self, table: str, id: str, fields: dict) -> dict | None:
        with self._lock:
            row = self._conn.execute(f"SELECT data FROM {table} WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            rec = json.loads(row[0])
            rec.update(fields)
            self._conn.execute(f"UPDATE {table} SET data = ? WHERE id = ?", (json.dumps(rec), id))
            self._conn.commit()
            return dict(rec)

    def last(self, table: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                f"SELECT data FROM {table} ORDER BY seq DESC LIMIT 1"
            ).fetchone()
        return json.loads(row[0]) if row else None


_repo: Repo | None = None


def set_repo(r: Repo | None) -> None:
    global _repo
    _repo = r


def get_repo() -> Repo:
    global _repo
    if _repo is None:
        _repo = SqliteRepo()
    return _repo
