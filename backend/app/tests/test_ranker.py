from __future__ import annotations

import random

from app.config import settings
from app.db.tables import TASKS
from app.services import ranker


def _task(repo, severity):
    return repo.insert(
        TASKS, {"case_id": "c", "severity": severity, "title": "t", "status": "checked"}
    )


def test_hard_flag_forces_top_of_queue(in_memory_repo):
    task = _task(in_memory_repo, "low")  # even a LOW severity item with a hard flag must surface
    signals = {
        "citation_support_rate": 0.0,
        "deviation_score": 0.0,
        "disagreement_score": 0.0,
        "has_hard_flag": True,
    }
    risk = ranker.score_task(in_memory_repo, task, signals)
    assert risk["priority"] >= 0.95
    assert risk["lane"] == "review"


def test_low_clean_item_auto_clears(in_memory_repo):
    settings.SAMPLE_RATE = 0.0
    task = _task(in_memory_repo, "low")
    signals = {
        "citation_support_rate": 1.0,
        "deviation_score": 0.0,
        "disagreement_score": 0.0,
        "has_hard_flag": False,
    }
    risk = ranker.score_task(in_memory_repo, task, signals)
    assert risk["lane"] == "auto_clear"
    assert risk["sampled"] is False


def test_sampling_pulls_auto_cleared_into_review(in_memory_repo):
    settings.SAMPLE_RATE = 1.0  # sample everything → deterministic for the test
    task = _task(in_memory_repo, "low")
    signals = {
        "citation_support_rate": 1.0,
        "deviation_score": 0.0,
        "disagreement_score": 0.0,
        "has_hard_flag": False,
    }
    risk = ranker.score_task(in_memory_repo, task, signals, rng=random.Random(1))
    assert risk["lane"] == "auto_clear"
    assert risk["sampled"] is True


def test_high_severity_outranks_low(in_memory_repo):
    settings.SAMPLE_RATE = 0.0
    sig = {
        "citation_support_rate": 1.0,
        "deviation_score": 0.0,
        "disagreement_score": 0.0,
        "has_hard_flag": False,
    }
    hi = ranker.score_task(in_memory_repo, _task(in_memory_repo, "high"), sig)
    lo = ranker.score_task(in_memory_repo, _task(in_memory_repo, "low"), sig)
    assert hi["priority"] > lo["priority"]
