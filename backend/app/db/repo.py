from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
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
    def delete(self, table: str, id: str) -> bool:
        """Remove a record by id. Returns True if a row was deleted."""

    @abstractmethod
    def last(self, table: str) -> dict | None:
        """The most recently inserted record in a table, or None. Used by the audit chain."""

    @abstractmethod
    def insert_chained(self, table: str, build: Callable[[dict | None], dict]) -> dict:
        """Atomically read the last row of `table`, build the new record from it, and insert it.

        The read and the write happen as one unit — atomic *across processes* (SqliteRepo holds the
        write lock via BEGIN IMMEDIATE for the whole sequence). This is what keeps the hash-chained
        audit log unforkable now that the pipeline runs on a separate Celery worker process, where
        an in-process lock no longer coordinates with the API process (architecture.md §11)."""


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

    def delete(self, table: str, id: str) -> bool:
        rows = self._data.get(table, [])
        for i, rec in enumerate(rows):
            if rec["id"] == id:
                del rows[i]
                return True
        return False

    def last(self, table: str) -> dict | None:
        rows = self._data.get(table, [])
        if not rows:
            return None
        return dict(max(rows, key=lambda r: r["seq"]))

    def insert_chained(self, table: str, build: Callable[[dict | None], dict]) -> dict:
        with self._lock:
            rows = self._data.get(table, [])
            prev = dict(max(rows, key=lambda r: r["seq"])) if rows else None
            self._seq += 1
            rec = dict(build(prev))
            rec.setdefault("id", _new_id())
            rec.setdefault("created_at", _now())
            rec["seq"] = self._seq
            self._data.setdefault(table, []).append(rec)
            return dict(rec)


class SqliteRepo(Repo):
    """SQLite-backed store. Each logical table is one physical table of (id, seq, created_at, data)
    where `data` is the JSON-serialized record. Small dataset → filtering happens in Python after
    load, which keeps the storage layer trivial and the resource set easy to extend."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or settings.SQLITE_PATH
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: FastAPI may serve from a threadpool; we guard with a lock.
        # isolation_level=None: manual transaction control, so writes can use an explicit
        # BEGIN IMMEDIATE (see _write) that holds the write lock across read-then-write — the
        # cross-process atomicity the Celery worker needs (the in-process lock alone no longer
        # coordinates two processes against the shared file).
        self._conn = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        # WAL lets readers and a writer coexist; busy_timeout makes a second writer wait for the
        # lock instead of erroring with "database is locked".
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            for table in ALL_TABLES:
                self._conn.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, seq INTEGER, created_at TEXT, data TEXT)"
                )

    def _write(self, fn: Callable[[], dict | None]) -> dict | None:
        """Run a read-then-write `fn` inside one BEGIN IMMEDIATE transaction. The write lock is
        acquired up front, so the SELECT and the INSERT/UPDATE are atomic across processes; the
        in-process `self._lock` serialises threads sharing this one connection."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                result = fn()
                self._conn.execute("COMMIT")
                return result
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def _next_seq(self) -> int:
        cur = self._conn.execute(
            "SELECT COALESCE(MAX(m), 0) FROM ("
            + " UNION ALL ".join(f"SELECT MAX(seq) AS m FROM {t}" for t in ALL_TABLES)
            + ")"
        )
        return int(cur.fetchone()[0] or 0) + 1

    def _insert_row(self, table: str, rec: dict) -> dict:
        rec = dict(rec)
        rec.setdefault("id", _new_id())
        rec.setdefault("created_at", _now())
        rec["seq"] = self._next_seq()
        self._conn.execute(
            f"INSERT INTO {table} (id, seq, created_at, data) VALUES (?, ?, ?, ?)",
            (rec["id"], rec["seq"], rec["created_at"], json.dumps(rec)),
        )
        return dict(rec)

    def _last_row(self, table: str) -> dict | None:
        row = self._conn.execute(
            f"SELECT data FROM {table} ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return json.loads(row[0]) if row else None

    def insert(self, table: str, record: dict) -> dict:
        return self._write(lambda: self._insert_row(table, record))

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
        def _do() -> dict | None:
            row = self._conn.execute(f"SELECT data FROM {table} WHERE id = ?", (id,)).fetchone()
            if not row:
                return None
            rec = json.loads(row[0])
            rec.update(fields)
            self._conn.execute(f"UPDATE {table} SET data = ? WHERE id = ?", (json.dumps(rec), id))
            return dict(rec)

        return self._write(_do)

    def delete(self, table: str, id: str) -> bool:
        def _do() -> bool:
            cur = self._conn.execute(f"DELETE FROM {table} WHERE id = ?", (id,))
            return cur.rowcount > 0

        return self._write(_do)

    def last(self, table: str) -> dict | None:
        with self._lock:
            return self._last_row(table)

    def insert_chained(self, table: str, build: Callable[[dict | None], dict]) -> dict:
        return self._write(lambda: self._insert_row(table, build(self._last_row(table))))


_repo: Repo | None = None


def set_repo(r: Repo | None) -> None:
    global _repo
    _repo = r


def get_repo() -> Repo:
    global _repo
    if _repo is None:
        _repo = SqliteRepo()
    return _repo
