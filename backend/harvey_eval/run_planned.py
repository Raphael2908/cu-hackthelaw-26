"""Planner-driven Track A + Track B runner.

Same pipeline as ``harvey_eval/run.py`` (worker -> checker -> ranker over a Harvey task),
with ONE difference: instead of hand-building the worker task with no instruction — which makes
``build_task_spec`` fall back to the fixed "review the DRAFT against the FIRM STANDARD"
default for *every* task — we route the task through the **planner** first.

``evaluation.md`` headline #1: the harness bypassing the planner is the single biggest
determinant of our Track-A number. Here we call ``provider.plan_case`` (the lightweight planner
entry point chosen for this run) to author a task-specific ``ai_instruction``; the shipped
worker then executes with that tailored brief layered onto the section instruction
(``app/services/task_spec.py``). Everything downstream (checker, ranker, deliverable render,
metering) is identical to ``run.py``, so this is a clean A/B against the prior non-planner run.

The worker ``kind`` is mapped from the task's Harvey ``work_type`` (a documented harness
modelling choice — see ``KIND_BY_WORK_TYPE``). For the review/analyze EU tasks in this run that
resolves to ``kind=review`` with all three checks, deliberately the same signal set as the prior
run so ``uncertainty`` stays comparable and the only changed variable is the planner brief.

Usage (from backend/, env injected from the repo-root .env):
    uv run python -m harvey_eval.run_planned --task <area>/<slug> --severity high \
        --run-id planner_sonnet5/<slug>
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

# Importing run triggers its module-level _load_root_env(), so the repo-root .env
# (PROVIDER_MODE=real, ANTHROPIC_API_KEY, ANTHROPIC_MODEL) is injected before app.config loads.
from harvey_eval import run as base
from harvey_eval.metering import UsageTracker, install_metering

base._load_root_env()  # idempotent; the statement break keeps app.* imports after env injection

# app.* is safe to import now (env already injected above).
from app.db.repo import InMemoryRepo  # noqa: E402
from app.db.tables import CORPUS, FLAGS, RISK_SCORES  # noqa: E402
from app.providers.factory import get_llm_provider  # noqa: E402
from app.schemas.models import DEFAULT_CHECKS  # noqa: E402
from app.services.checker import run_checks  # noqa: E402
from app.services.ranker import score_task  # noqa: E402
from app.services.worker import run_review  # noqa: E402

# Harvey work_type -> our worker kind. Documented modelling choice: an observation-only review
# fits review/analyze; draft/research map to the generative/extractive kinds for future cohorts.
KIND_BY_WORK_TYPE = {
    "review": "review",
    "analyze": "review",
    "": "review",
    "draft": "draft",
    "research": "extract",
}
# Per-kind worker spec. review checks against a standard (all three signals); the generative /
# extractive kinds have no firm standard to deviate from, so precedent_deviation is dropped and
# the uncertainty composite renormalises over the applied signals (architecture.md §7.2).
_NO_STD_CHECKS = ["citation_support", "multi_run_disagreement"]
SPEC_BY_KIND = {
    "review": {"requires_standard": True, "checks": list(DEFAULT_CHECKS)},
    "summarize": {"requires_standard": False, "checks": list(_NO_STD_CHECKS)},
    "extract": {"requires_standard": False, "checks": list(_NO_STD_CHECKS)},
    "draft": {"requires_standard": False, "checks": list(_NO_STD_CHECKS)},
}

# The EU catalogue carries the authoritative work_type per task id.
_EU_TASKS = Path(__file__).resolve().parent / "eu_tasks.json"


def _work_type(task_id: str, config: dict) -> str:
    """Resolve the task's Harvey work_type: prefer task.json, fall back to the EU catalogue."""
    wt = (config.get("work_type") or "").strip()
    if wt:
        return wt
    if _EU_TASKS.exists():
        for row in json.loads(_EU_TASKS.read_text(encoding="utf-8")):
            if row.get("id") == task_id:
                return (row.get("work_type") or "").strip()
    return ""


def plan_instruction(provider, *, task: dict, bundle: dict, kind: str, spec: dict) -> str | None:
    """Call the planner LLM to author a task-specific worker brief (ai_instruction).

    We model the Harvey task as a single-section process map so plan_case has the section's kind
    in scope when it writes the brief. Returns the first task's ai_instruction, or None (the
    worker then uses the default review framing — same as the non-planner harness)."""
    work_type = kind  # section key; the planner reads the kind from TASK TYPES
    process_doc = {
        "id": "harvey-planner-map",
        "kind": "process_doc",
        "task_types": {
            work_type: {
                "label": task["config"].get("title", task["id"]),
                "kind": kind,
                "requires_standard": spec["requires_standard"],
                "checks": spec["checks"],
            }
        },
    }
    proposed = provider.plan_case(
        goal=task["config"].get("title", task["id"]),
        brief=task["instructions"],
        process_doc=process_doc,
        drafts=[{"id": bundle["id"], "title": bundle["title"]}],
        associates=[],
    )
    if not proposed:
        return None
    return proposed[0].get("ai_instruction") or None


def run(task_id: str, severity: str, run_id: str | None) -> dict:
    task = base.load_task(task_id)
    run_id = run_id or f"{task_id}/planner/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_dir = base.RESULTS_ROOT / run_id
    out_dir = run_dir / "output"

    work_type = _work_type(task_id, task["config"])
    kind = KIND_BY_WORK_TYPE.get(work_type, "review")
    spec = SPEC_BY_KIND[kind]

    bundle_text, doc_names = base.build_bundle(task)
    provider = get_llm_provider()
    usage = UsageTracker()
    install_metering(provider, usage)
    repo = InMemoryRepo()

    case_id = "harvey-case"
    bundle = repo.insert(CORPUS, {
        "kind": "draft", "case_id": case_id,
        "title": task["config"].get("title", task_id),
        "text": bundle_text, "celex": None,
    })
    # Synthetic firm standard = the task instructions (Harvey has no firm standard). Only consumed
    # by review-kind tasks (requires_standard); harmless otherwise.
    std = repo.insert(CORPUS, {
        "kind": "firm_standard", "case_id": case_id,
        "title": "Task instructions (as standard)",
        "text": task["instructions"], "clauses": {}, "celex": None,
    })

    # The planner authors the task-specific worker brief (the one variable vs the non-planner run).
    ai_instruction = plan_instruction(provider, task=task, bundle=bundle, kind=kind, spec=spec)

    wtask = {
        "id": "harvey-task", "case_id": case_id,
        "target_document_id": bundle["id"], "firm_standard_id": std["id"],
        "input_process_section": task["instructions"], "severity": severity,
        # Flexible-worker spec resolved by build_task_spec: the planner's brief layers on top.
        "output_kind": kind,
        "worker_instruction": None,
        "ai_instruction": ai_instruction,
        "checklist": [],
        "applicable_checks": spec["checks"],
        "requires_standard": spec["requires_standard"],
    }

    # Track A: worker produces the deliverable, now driven by the planner's tailored instruction.
    submission = run_review(repo, task=wtask, provider=provider, produced_by="ai")
    deliv = base.deliverable_name(task["config"])
    base.render_docx(submission, task, out_dir / deliv)

    # Track B: checker + ranker over the same output. Seed EU instruments so citation_support can
    # resolve real CELEX citations against the corpus.
    n_seeded = base.seed_eu_corpus(repo)
    signals = run_checks(repo, wtask, submission, provider)
    risk = score_task(repo, wtask, signals)

    (run_dir / "metrics.json").write_text(json.dumps({
        "task": task_id, "run_id": run_id, "model": os.environ.get("ANTHROPIC_MODEL", ""),
        "documents_included": doc_names, "deliverable": deliv,
        "entry_point": "planner", "work_type": work_type, "worker_kind": kind,
    }, indent=2))

    our = {
        "task": task_id, "run_id": run_id, "severity": severity,
        "entry_point": "planner", "work_type": work_type, "worker_kind": kind,
        "ai_instruction": ai_instruction,
        "deliverable": deliv, "documents_included": doc_names,
        "n_findings": len(submission.get("findings", [])),
        "corpus_celex_seeded": n_seeded,
        "citation_support_rate": signals["citation_support_rate"],
        "deviation_score": signals["deviation_score"],
        "disagreement_score": signals["disagreement_score"],
        "uncertainty": risk["uncertainty"],
        "priority": risk["priority"],
        "lane": risk["lane"],
        "sampled": risk["sampled"],
        "has_hard_flag": signals["has_hard_flag"],
        "applied_checks": risk.get("applied_checks"),
        "usage": usage.summary(),
        "n_flags": len(repo.list(FLAGS)),
        "flags": [
            {"signal_type": f["signal_type"], "hard": f.get("hard", False), "title": f["title"]}
            for f in repo.list(FLAGS)
        ],
        "_risk_scores_rows": len(repo.list(RISK_SCORES)),
    }
    (run_dir / "our_eval.json").write_text(json.dumps(our, indent=2))
    print(json.dumps({k: v for k, v in our.items() if k != "flags"}, indent=2))
    u = our["usage"]
    print(f"\nTokens: {u['total_tokens']:,} ({u['llm_calls']} LLM calls) | "
          f"in={u['input_tokens']:,} out={u['output_tokens']:,} "
          f"cache_read={u['cache_read_tokens']:,} | cost=${u['cost_usd']:.4f} ({u['model']})")
    print(f"\nPlanner ai_instruction present: {bool(ai_instruction)}")
    print(f"Deliverable: {out_dir / deliv}")
    print(f"Run dir:     {run_dir}")
    return our


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True)
    p.add_argument("--severity", default="high", choices=["low", "medium", "high", "extreme"])
    p.add_argument("--run-id", default=None)
    args = p.parse_args()
    run(args.task, args.severity, args.run_id)
