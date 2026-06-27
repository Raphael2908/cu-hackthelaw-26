"""Track C — join our supervision `uncertainty` (Track B) with a Harvey-backed quality score
and report the correlation.

Per task it records one row {uncertainty, quality}. With a single task there is no correlation
(n=1) — it just prints the data point. Run over many tasks to get a Spearman rho. Rows accumulate
in track_c/results.jsonl (deduped by run_id). See TRACK_C_PLAN.md.

Usage (from backend/):
    uv run python -m harvey_eval.track_c.correlate --task <t> --run-id <run-id>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harvey_eval.track_c.quality import RESULTS_ROOT, score_quality_light

RESULTS_FILE = Path(__file__).resolve().parent / "results.jsonl"


def uncertainty_for(run_id: str) -> float:
    our = json.loads((RESULTS_ROOT / run_id / "our_eval.json").read_text(encoding="utf-8"))
    return float(our["uncertainty"])


def _rank(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0  # average rank (1-based) for ties
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float:
    rx, ry = _rank(xs), _rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0


def _load_rows() -> list[dict]:
    if not RESULTS_FILE.exists():
        return []
    return [json.loads(line) for line in RESULTS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]


def _save_rows(rows: list[dict]) -> None:
    RESULTS_FILE.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True)
    p.add_argument("--run-id", required=True)
    args = p.parse_args()

    unc = uncertainty_for(args.run_id)
    q = score_quality_light(args.task, args.run_id)
    row = {
        "task": args.task,
        "run_id": args.run_id,
        "uncertainty": unc,
        "quality": q["quality"],
        "quality_reasoning": q["reasoning"],
        "judge_model": q["judge_model"],
        "judge_usage": q["usage"],
    }

    rows = [r for r in _load_rows() if r.get("run_id") != args.run_id]  # dedupe by run_id
    rows.append(row)
    _save_rows(rows)

    print(json.dumps(row, indent=2))
    print(f"\nData points: {len(rows)}  ->  {RESULTS_FILE}")
    if len(rows) < 2:
        print("Need >=2 tasks for a correlation (Spearman rho). This is the only point so far.")
        print("Hypothesis (to test as N grows): higher uncertainty -> lower Harvey quality.")
    else:
        rho = spearman([r["uncertainty"] for r in rows], [r["quality"] for r in rows])
        print(f"Spearman rho (uncertainty vs quality), n={len(rows)}: {rho:+.3f}")
        print("Negative rho supports: higher supervision uncertainty predicts lower Harvey quality.")


if __name__ == "__main__":
    main()
