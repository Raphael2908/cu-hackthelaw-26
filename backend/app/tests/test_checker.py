from __future__ import annotations

from app.db.tables import TASKS
from app.services import checker, worker


def _ai_task(repo, draft_id, *, severity="high", task_type="review_binding_obligation"):
    return repo.insert(
        TASKS,
        {
            "case_id": "case-x",
            "plan_id": "plan-x",
            "target_document_id": draft_id,
            "task_type": task_type,
            "assignee_type": "ai",
            "severity": severity,
            "input_process_section": "test",
            "status": "submitted",
            "title": draft_id,
        },
    )


def test_non_supporting_citation_is_a_hard_flag(in_memory_repo, provider):
    repo = in_memory_repo
    task = _ai_task(repo, "draft-dpa-atlas")
    sub = worker.run_review(repo, task=task, provider=provider)
    res = checker.citation_support(repo, task, sub, provider)
    assert res["rate"] < 1.0
    assert any(f["hard"] and f["signal_type"] == "citation_support" for f in res["flags"])
    # The flag points one click away to the actual (existing) source.
    flag = next(f for f in res["flags"] if f["signal_type"] == "citation_support")
    assert flag["source_ref"]["exists"] is True


def test_fabricated_citation_is_a_hard_flag(in_memory_repo, provider):
    repo = in_memory_repo
    task = _ai_task(repo, "draft-govlaw-atlas", severity="medium", task_type="review_governing_law")
    sub = worker.run_review(repo, task=task, provider=provider)
    res = checker.citation_support(repo, task, sub, provider)
    flag = next(f for f in res["flags"] if "Fabricated" in f["title"])
    assert flag["hard"] is True
    assert flag["source_ref"]["exists"] is False


def test_precedent_deviation_flags_both_clauses(in_memory_repo, provider):
    repo = in_memory_repo
    task = _ai_task(repo, "draft-dpa-atlas")
    sub = worker.run_review(repo, task=task, provider=provider)
    res = checker.precedent_deviation(repo, task, sub, provider)
    refs = {f["source_ref"]["standard_key"] for f in res["flags"]}
    assert {"liability", "governing_law"} <= refs
    assert res["score"] > 0.5


def test_multi_run_disagreement_detects_instability(in_memory_repo, provider):
    repo = in_memory_repo
    task = _ai_task(repo, "draft-govlaw-atlas", severity="medium")
    sub = worker.run_review(repo, task=task, provider=provider)
    res = checker.multi_run_disagreement(repo, task, sub, provider)
    assert res["score"] >= checker.DISAGREEMENT_FLAG_THRESHOLD
    assert res["flags"]


def test_clean_low_doc_produces_no_flags(in_memory_repo, provider):
    repo = in_memory_repo
    task = _ai_task(repo, "draft-recital-atlas", severity="low", task_type="review_recital_summary")
    sub = worker.run_review(repo, task=task, provider=provider)
    signals = checker.run_checks(repo, task, sub, provider)
    assert signals["flags"] == []
    assert signals["citation_support_rate"] == 1.0
    assert signals["has_hard_flag"] is False


def test_checker_never_emits_a_verdict(in_memory_repo, provider):
    repo = in_memory_repo
    task = _ai_task(repo, "draft-dpa-atlas")
    sub = worker.run_review(repo, task=task, provider=provider)
    signals = checker.run_checks(repo, task, sub, provider)
    for f in signals["flags"]:
        assert "verdict" not in f
        assert f.get("hard") in (True, False)  # a flag, not a pass/fail
