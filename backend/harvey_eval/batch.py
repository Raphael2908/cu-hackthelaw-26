"""Batch driver: run our pipeline (variant A — the shipped, observation-only worker)
over a set of Harvey tasks, score each with Harvey's judge, and emit a Track A +
Track B summary.

    uv run python -m harvey_eval.batch --tasks-file ../harvey-labs/_batch_tasks.json --severity high

Writes harvey_eval/batch_results.jsonl (one row per task) and prints a summary.
"""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

from harvey_eval import run as runner
from harvey_eval import score as scorer

RESULTS_ROOT = runner.RESULTS_ROOT
HERE = Path(__file__).resolve().parent
OUT = HERE / "batch_results.jsonl"


def _load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def run_batch(task_ids: list[str], severity: str, tag: str, merge: bool = False,
              out_path: Path = OUT) -> list[dict]:
    # When merging, seed from existing rows and upsert by task id (preserving order), so a
    # re-run of a few tasks fills them in without clobbering the rest of the batch.
    by_task: dict[str, dict] = {}
    order: list[str] = []
    if merge and out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                by_task[r["task"]] = r
                order.append(r["task"])

    for i, task in enumerate(task_ids, 1):
        run_id = f"{task}/our-pipeline/{tag}"
        area = task.split("/")[0]
        print(f"\n===== [{i}/{len(task_ids)}] {task} =====")
        row: dict = {"task": task, "area": area, "severity": severity, "run_id": run_id}
        try:
            our = runner.run(task, severity, run_id)          # Track A produce + Track B signals
            rc = scorer.score_run(run_id, task)               # Harvey judge
            scores = _load_json(RESULTS_ROOT / run_id / "scores.json")
            if rc != 0 or scores is None:
                row["error"] = f"scoring failed (rc={rc})"
            else:
                row.update({
                    "all_pass": scores["all_pass"],
                    "n_passed": scores["n_passed"],
                    "n_criteria": scores["n_criteria"],
                    "pct": round(scores["n_passed"] / max(scores["n_criteria"], 1), 3),
                    "n_findings": our["n_findings"],
                    "uncertainty": our["uncertainty"],
                    "priority": our["priority"],
                    "lane": our["lane"],
                    "has_hard_flag": our["has_hard_flag"],
                    "citation_support_rate": our["citation_support_rate"],
                    "deviation_score": our["deviation_score"],
                    "disagreement_score": our["disagreement_score"],
                    "n_flags": our["n_flags"],
                })
        except Exception as e:  # keep the batch going; record the failure
            row["error"] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
        if task not in by_task:
            order.append(task)
        by_task[task] = row
        # checkpoint after every task so a mid-batch crash keeps prior results
        out_path.write_text(
            "\n".join(json.dumps(by_task[t]) for t in order) + "\n", encoding="utf-8"
        )
    return [by_task[t] for t in order]


def summarize(rows: list[dict], out_path: Path = OUT) -> None:
    ok = [r for r in rows if "error" not in r]
    print("\n" + "=" * 78)
    print(f"BATCH SUMMARY (variant A — shipped worker) — {len(ok)}/{len(rows)} scored")
    print("=" * 78)
    print(f"{'task':52} {'crit':>7} {'pass%':>6} {'all':>4} {'unc':>5} {'lane':>7}")
    for r in rows:
        if "error" in r:
            print(f"{r['task'][:52]:52} {'ERR':>7} {r['error'][:30]}")
            continue
        print(f"{r['task'][:52]:52} {r['n_passed']:>3}/{r['n_criteria']:<3} "
              f"{r['pct']*100:>5.0f}% {('Y' if r['all_pass'] else '.'):>4} "
              f"{r['uncertainty']:>5.2f} {r['lane']:>7}")
    if ok:
        tot_p = sum(r["n_passed"] for r in ok)
        tot_c = sum(r["n_criteria"] for r in ok)
        n_allpass = sum(1 for r in ok if r["all_pass"])
        print("-" * 78)
        print(f"Micro per-criterion pass rate: {tot_p}/{tot_c} = {tot_p/tot_c*100:.1f}%")
        print(f"Macro per-task pass rate:      {sum(r['pct'] for r in ok)/len(ok)*100:.1f}%")
        print(f"All-pass tasks:                {n_allpass}/{len(ok)}")
        print(f"Routed to review lane:         {sum(1 for r in ok if r['lane']=='review')}/{len(ok)}")
    print(f"\nRows written to {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--tasks-file", required=True)
    p.add_argument("--severity", default="high", choices=["low", "medium", "high", "extreme"])
    p.add_argument("--tag", default="batchA")
    p.add_argument("--merge", action="store_true",
                   help="Upsert into existing results file instead of overwriting.")
    p.add_argument("--out", default=None,
                   help="Results jsonl filename (relative to harvey_eval/) or absolute path. "
                        "Defaults to batch_results.jsonl. Use a distinct name to avoid clobbering.")
    args = p.parse_args()
    out_path = OUT if args.out is None else (
        Path(args.out) if Path(args.out).is_absolute() else HERE / args.out
    )
    task_ids = json.loads(Path(args.tasks_file).read_text(encoding="utf-8"))
    summarize(run_batch(task_ids, args.severity, args.tag, args.merge, out_path), out_path)
