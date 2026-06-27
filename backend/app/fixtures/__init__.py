from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@lru_cache
def _load(name: str):
    return json.loads((_DIR / name).read_text(encoding="utf-8"))


def corpus() -> list[dict]:
    return _load("corpus.json")


def associates() -> list[dict]:
    return _load("associates.json")


def mock_reviews() -> dict:
    return _load("mock_reviews.json")


def mock_plan_by_type() -> dict:
    """Per-section task scoping keyed by ``task_type``. The mock planner decomposes a case by
    walking the process doc's sections and emitting one task per section from this map, so the plan
    tracks the process doc rather than a fixed list (architecture.md §6)."""
    return _load("mock_plan.json")


def process_doc() -> dict:
    for d in corpus():
        if d["kind"] == "process_doc":
            return d
    raise RuntimeError("No process_doc in corpus fixtures.")


def firm_standard() -> dict:
    for d in corpus():
        if d["kind"] == "firm_standard":
            return d
    raise RuntimeError("No firm_standard in corpus fixtures.")
