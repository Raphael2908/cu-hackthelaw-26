from __future__ import annotations

import hashlib
import json

from app.db.repo import Repo
from app.db.tables import AUDIT_EVENTS

# Two kinds of audit, kept deliberately separate (architecture.md §11):
#   accountability — the defensible, signed record of who decided what, when, on what evidence.
#   supervision    — actionable signal (flags) that routes a human's attention.
ACCOUNTABILITY = "accountability"
SUPERVISION = "supervision"


def _hash(prev_hash: str, payload: dict) -> str:
    body = prev_hash + json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def record_event(
    repo: Repo,
    *,
    kind: str,
    type: str,
    actor: str,
    case_id: str | None = None,
    task_id: str | None = None,
    payload: dict | None = None,
) -> dict:
    """Append one hash-chained audit event. The chain is global and append-only: each event's
    `hash` covers its content plus the previous event's `hash`, so any tampering is detectable."""
    payload = payload or {}
    prev = repo.last(AUDIT_EVENTS)
    prev_hash = prev["hash"] if prev else "GENESIS"
    content = {
        "kind": kind,
        "type": type,
        "actor": actor,
        "case_id": case_id,
        "task_id": task_id,
        "payload": payload,
    }
    event = dict(content)
    event["prev_hash"] = prev_hash
    event["hash"] = _hash(prev_hash, content)
    return repo.insert(AUDIT_EVENTS, event)


def record_accountability(repo: Repo, *, type: str, actor: str, **kw) -> dict:
    return record_event(repo, kind=ACCOUNTABILITY, type=type, actor=actor, **kw)


def record_supervision(repo: Repo, *, type: str, actor: str, **kw) -> dict:
    return record_event(repo, kind=SUPERVISION, type=type, actor=actor, **kw)


def verify_chain(repo: Repo) -> bool:
    """Recompute the chain end to end. Used by the audit view / tests to prove integrity."""
    prev_hash = "GENESIS"
    for ev in repo.list(AUDIT_EVENTS):
        content = {k: ev.get(k) for k in ("kind", "type", "actor", "case_id", "task_id", "payload")}
        if ev.get("prev_hash") != prev_hash or ev.get("hash") != _hash(prev_hash, content):
            return False
        prev_hash = ev["hash"]
    return True
