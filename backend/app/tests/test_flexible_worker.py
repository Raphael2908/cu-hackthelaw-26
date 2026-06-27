from __future__ import annotations

from app.config import settings
from app.db.tables import TASKS
from app.services import checker, ranker, worker
from app.services.task_spec import build_task_spec


def _review_task(repo, draft_id="draft-dpa-atlas", **over):
    """A default (review) task — no worker-spec fields set, so the back-compat defaults apply."""
    task = {
        "case_id": "case-x",
        "plan_id": "plan-x",
        "target_document_id": draft_id,
        "task_type": "review_binding_obligation",
        "assignee_type": "ai",
        "severity": "high",
        "input_process_section": "binding obligation",
        "status": "submitted",
        "title": draft_id,
    }
    task.update(over)
    return repo.insert(TASKS, task)


def _extract_task(repo, **over):
    """A flexible, non-review task: extraction with no firm standard, deviation excluded — exactly
    what the planner copies off the `extract_obligations` process-map section."""
    task = {
        "case_id": "case-x",
        "plan_id": "plan-x",
        "target_document_id": "draft-obligations-atlas",
        "task_type": "extract_obligations",
        "assignee_type": "ai",
        "severity": "low",
        "input_process_section": "Extract operative obligations",
        "output_kind": "extract",
        "worker_instruction": "Extract every operative obligation from the schedule.",
        "checklist": ["List each obligation", "Name the obligated party"],
        "applicable_checks": ["citation_support", "multi_run_disagreement"],
        "requires_standard": False,
        "status": "submitted",
        "title": "extract-obligations",
    }
    task.update(over)
    return repo.insert(TASKS, task)


def test_instruction_reaches_the_worker(in_memory_repo):
    """The section instruction AND the planner's per-task ai_instruction both reach the worker — the
    ai_instruction field used to be stored and never consumed."""
    repo = in_memory_repo
    task = _extract_task(
        repo,
        worker_instruction="EXTRACT THE OBLIGATIONS",
        ai_instruction="Pay special attention to audit rights.",
    )
    spec = build_task_spec(repo, task)
    assert spec.kind == "extract"
    assert "EXTRACT THE OBLIGATIONS" in spec.instruction
    assert "Pay special attention to audit rights." in spec.instruction


def test_no_standard_task_skips_precedent_deviation(in_memory_repo, provider):
    """A from-scratch task with no firm standard must skip precedent deviation cleanly: neutral
    score, NOT applied, and crucially no fabricated deviation flag even though a seeded firm
    standard exists in the corpus (architecture.md §14.4)."""
    repo = in_memory_repo
    task = _extract_task(repo)
    sub = worker.run_review(repo, task=task, provider=provider)
    signals = checker.run_checks(repo, task, sub, provider)

    assert signals["deviation_score"] == 0.0
    assert signals["applied_checks"]["precedent_deviation"] is False
    assert not any(f["signal_type"] == "precedent_deviation" for f in signals["flags"])
    # The reference was never resolved for this task.
    assert build_task_spec(repo, task).reference is None


def test_uncertainty_is_renormalised_over_applied_checks(in_memory_repo):
    """When a signal didn't apply it is excluded from BOTH numerator and denominator — a high
    deviation score that did not run must not leak into the composite."""
    signals = {
        "citation_support_rate": 0.5,
        "deviation_score": 1.0,  # would dominate if (wrongly) included
        "disagreement_score": 0.0,
        "applied_checks": {
            "citation_support": True,
            "precedent_deviation": False,
            "multi_run_disagreement": True,
        },
    }
    w_c, w_d, w_g = settings.W_CITATION, settings.W_DEVIATION, settings.W_DISAGREEMENT
    expected = (w_c * (1.0 - 0.5) + w_g * 0.0) / (w_c + w_g)
    got = ranker.compute_uncertainty(signals)
    assert abs(got - expected) < 1e-9
    # Renormalising must give a LOWER number than if the (non-applied) deviation term had leaked in.
    leaked = (w_c * (1.0 - 0.5) + w_d * 1.0 + w_g * 0.0) / (w_c + w_d + w_g)
    assert got < leaked


def test_disagreement_runs_without_a_firm_standard(in_memory_repo, provider):
    """The disagreement re-run now uses the shared task spec, so it works for a no-standard task —
    proving it no longer depends on review_document/firm_standard. The fixture scripts f-obl-2 into
    only one of three runs → Jaccard distance 0.5."""
    repo = in_memory_repo
    task = _extract_task(repo)
    sub = worker.run_review(repo, task=task, provider=provider)
    signals = checker.run_checks(repo, task, sub, provider)
    assert signals["applied_checks"]["multi_run_disagreement"] is True
    assert signals["disagreement_score"] == 0.5


def test_per_type_output_persists_on_submission(in_memory_repo, provider):
    """A flexible task type carries its own structured product in the submission payload, alongside
    the universal findings the checker reads."""
    repo = in_memory_repo
    task = _extract_task(repo)
    sub = worker.run_review(repo, task=task, provider=provider)
    assert sub["output_kind"] == "extract"
    obligations = sub["payload"]["obligations"]
    assert obligations and obligations[0]["party"] == "Supplier"
    # The universal checkable-claims seam is still populated for supervision.
    assert sub["findings"]


def test_default_task_applies_all_three_checks(in_memory_repo, provider):
    """Regression: a task with no worker-spec fields reproduces the original three-signal review."""
    repo = in_memory_repo
    task = _review_task(repo)
    sub = worker.run_review(repo, task=task, provider=provider)
    signals = checker.run_checks(repo, task, sub, provider)
    assert signals["applied_checks"] == {
        "citation_support": True,
        "precedent_deviation": True,
        "multi_run_disagreement": True,
    }
    assert sub["output_kind"] == "review"
