"""Track C grader + correlator for the planner-driven run.

Grades the five planner-driven EU deliverables with the strict Q-full per-criterion judge
(``grade.grade_deliverable``, ``claude-sonnet-4-6``, independent of the worker) and reports
Spearman rho of our supervision ``uncertainty`` vs the grader's quality score.

Self-contained on purpose: it writes its OWN ``planner_sonnet5_grades.jsonl`` rather than the
shared ``grader_results.jsonl`` (which feeds evaluation.md), and grades sequentially, so it
neither clobbers the prior 10-task data nor hits the parallel-write race noted in evaluation.md.

Usage (from backend/, after run_planned has produced the five run dirs):
    uv run python -m harvey_eval.track_c.planner_batch
    uv run python -m harvey_eval.track_c.planner_batch --recorrelate   # report over saved rows only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harvey_eval.track_c.correlate import spearman
from harvey_eval.track_c.grade import _uncertainty, grade_deliverable

# The 10 planner-driven EU tasks as (task_id, run_id) pairs.
# Batch 1 = the prior eu_sonnet5 set (clean A/B). Batch 2 = the next 5, with two swaps from the
# prior eu_sonnet5b set: review-saas (cost outlier) and analyze-counterparty (structural max_tokens
# truncation in the disagreement re-runs) were replaced by transfer-agreement + assess-impact.
_BATCH1 = [
    "data-privacy-cybersecurity/summarize-new-gdpr-enforcement-guidance",
    "data-privacy-cybersecurity/compare-privacy-notice-against-statutory-disclosure-requirements",
    "intellectual-property/identify-issues-in-counterparty-data-processing-addendum",
    "corporate-governance/map-eu-ai-act-transparency-obligations-to-existing-product-documentation",
    "intellectual-property/review-master-services-agreement-for-regulatory-compliance",
]
_BATCH2 = [
    "data-privacy-cybersecurity/triage-vendor-contracts-for-gdpr-cross",
    "data-privacy-cybersecurity/draft-data-processing-agreement",
    "data-privacy-cybersecurity/draft-standard-contractual-clauses-addendum",
    "data-privacy-cybersecurity/identify-privacy-and-data-protection-issues-in-counterparty-transfer-agreement",
    "corporate-governance/assess-impact-of-eu-ai-act-on-company-ai-product-portfolio",
]
# (task_id, run_id) for every task; run-ids namespaced per batch.
TASK_RUNS = (
    [(t, f"planner_sonnet5/{t.split('/')[-1]}") for t in _BATCH1]
    + [(t, f"planner_sonnet5b/{t.split('/')[-1]}") for t in _BATCH2]
)
TASKS = [t for t, _ in TASK_RUNS]
GRADES_FILE = Path(__file__).resolve().parent / "planner_sonnet5_grades.jsonl"


def _run_id(task_id: str) -> str:
    for t, rid in TASK_RUNS:
        if t == task_id:
            return rid
    return f"planner_sonnet5/{task_id.split('/')[-1]}"


def _load_rows() -> list[dict]:
    if not GRADES_FILE.exists():
        return []
    rows = []
    for line in GRADES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _save_rows(rows: list[dict]) -> None:
    GRADES_FILE.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )


def _report(rows: list[dict]) -> None:
    print(f"\nPlanner Track C data points: {len(rows)}  ->  {GRADES_FILE}")
    for r in rows:
        print(f"  unc={r['uncertainty']:.4f}  Q={r['score']:.3f} "
              f"({r['n_pass']}/{r['n_criteria']}, {r['n_low_confidence']} low-conf)  {r['task']}")
    if len(rows) >= 2:
        rho = spearman([r["uncertainty"] for r in rows], [r["score"] for r in rows])
        print(f"\nSpearman rho (uncertainty vs grader Q), n={len(rows)}: {rho:+.3f}")
        print("Prior non-planner run (eu_sonnet5, same 5 tasks): rho = -0.600")
    else:
        print("Need >=2 points for a correlation.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--recorrelate", action="store_true", help="report over saved rows, no grading")
    p.add_argument("--regrade", action="store_true", help="re-grade tasks already saved")
    args = p.parse_args()

    if args.recorrelate:
        _report(_load_rows())
        return

    rows_by_run: dict[str, dict] = {r["run_id"]: r for r in _load_rows()}
    for task_id, run_id in TASK_RUNS:
        if run_id in rows_by_run and not args.regrade:
            print(f"\n===== skip {task_id} ({run_id}) — already graded =====")
            continue
        print(f"\n===== grading {task_id} ({run_id}) =====")
        try:
            res = grade_deliverable(task_id, run_id)
        except Exception as e:  # keep going; a missing/failed deliverable shouldn't block the rest
            print(f"  ERROR: {type(e).__name__}: {e}")
            continue
        row = {
            "task": task_id,
            "run_id": run_id,
            "uncertainty": _uncertainty(run_id),
            "score": res["score"],
            "n_criteria": res["n_criteria"],
            "n_pass": res["n_pass"],
            "n_low_confidence": res["n_low_confidence"],
            "judge_model": res["judge_model"],
            "judge_usage": res["judge_usage"],
            "verdicts": res["verdicts"],
        }
        rows_by_run[run_id] = row
        print(json.dumps({k: v for k, v in row.items() if k != "verdicts"}, indent=2))
        _save_rows(list(rows_by_run.values()))  # checkpoint after each grade

    # Report in TASKS order over the rows we have.
    ordered = [rows_by_run[_run_id(t)] for t in TASKS if _run_id(t) in rows_by_run]
    _report(ordered)


if __name__ == "__main__":
    main()
