"""Q-full grader — careful per-criterion evaluation of a deliverable against a Harvey task's
rubric, using the system prompt in grader_prompt.md.

This is the rigorous y-axis for Track C: instead of one holistic quality score (Q-light, which
gave a wrong-signed correlation), it grades every `match_criteria` independently and returns
score = passes / criteria. Writes to track_c/grader_results.jsonl — a SEPARATE file from the
sweep's results.jsonl, so it never collides with a running batch.

Usage (from backend/):
    uv run python -m harvey_eval.track_c.grade --task <t> --run-id <run-id>      # grade + record one
    uv run python -m harvey_eval.track_c.grade --recorrelate                      # just print rho over recorded rows
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import anthropic

from harvey_eval.track_c.correlate import spearman
from harvey_eval.track_c.quality import (
    JUDGE_MODEL,
    RESULTS_ROOT,
    TASKS_ROOT,
    _deliverable_text,
    _load_key,
    _task_brief,
)

PROMPT_FILE = Path(__file__).resolve().parent / "grader_prompt.md"
GRADER_RESULTS = Path(__file__).resolve().parent / "grader_results.jsonl"
_PRICE_IN, _PRICE_OUT = 3.0, 15.0  # Sonnet 4.6, USD per 1M


def _system_prompt() -> str:
    """Extract the fenced system-prompt block from grader_prompt.md and un-escape the doubled
    braces it carries for .format-compatibility (we send it verbatim, not via .format)."""
    md = PROMPT_FILE.read_text(encoding="utf-8")
    after = md.split("## System prompt", 1)[1]
    block = re.search(r"```(.*?)```", after, re.DOTALL).group(1).strip()
    return block.replace("{{", "{").replace("}}", "}")


def _criteria(task_id: str) -> list[dict]:
    cfg = json.loads(
        (TASKS_ROOT / Path(*task_id.split("/")) / "task.json").read_text(encoding="utf-8")
    )
    out = []
    for c in cfg.get("criteria", []):
        out.append(
            {"id": c.get("id"), "title": c.get("title", ""), "match_criteria": c.get("match_criteria", "")}
        )
    return out


def grade_deliverable(task_id: str, run_id: str) -> dict:
    _load_key()
    title, instructions = _task_brief(task_id)
    deliverable = _deliverable_text(run_id)
    criteria = _criteria(task_id)

    user = (
        f"TASK\n{title}\n{instructions[:15000]}\n\n"
        f"DELIVERABLE\n{deliverable[:80000]}\n\n"
        f"CRITERIA\n{json.dumps(criteria, ensure_ascii=False)}"
    )
    client = anthropic.Anthropic(max_retries=1)
    resp = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=16000,
        temperature=0.0,
        system=_system_prompt(),
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "max_tokens":
        raise ValueError("grader output truncated (max_tokens) — reduce criteria per call or raise cap")
    text = resp.content[0].text
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        raise ValueError(f"grader returned no JSON array: {text[:200]}")
    verdicts = json.loads(m.group(0))

    n = len(verdicts)
    n_pass = sum(1 for v in verdicts if str(v.get("verdict")).lower() == "pass")
    n_low = sum(1 for v in verdicts if str(v.get("confidence")).lower() == "low")
    u = resp.usage
    cost = (u.input_tokens * _PRICE_IN + u.output_tokens * _PRICE_OUT) / 1_000_000
    return {
        "score": round(n_pass / n, 4) if n else 0.0,
        "n_criteria": n,
        "n_pass": n_pass,
        "n_low_confidence": n_low,
        "verdicts": verdicts,
        "judge_model": JUDGE_MODEL,
        "judge_usage": {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens, "cost_usd": round(cost, 5)},
    }


def _uncertainty(run_id: str) -> float:
    return float(json.loads((RESULTS_ROOT / run_id / "our_eval.json").read_text(encoding="utf-8"))["uncertainty"])


def _load_rows() -> list[dict]:
    if not GRADER_RESULTS.exists():
        return []
    return [json.loads(line) for line in GRADER_RESULTS.read_text(encoding="utf-8").splitlines() if line.strip()]


def _save_rows(rows: list[dict]) -> None:
    GRADER_RESULTS.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def _report(rows: list[dict]) -> None:
    print(f"\nGrader data points: {len(rows)}  ->  {GRADER_RESULTS}")
    for r in rows:
        print(f"  unc={r['uncertainty']:.4f}  grader_score={r['score']:.3f} "
              f"({r['n_pass']}/{r['n_criteria']}, {r['n_low_confidence']} low-conf)  {r['run_id']}")
    if len(rows) >= 2:
        rho = spearman([r["uncertainty"] for r in rows], [r["score"] for r in rows])
        print(f"\nSpearman rho (uncertainty vs grader score), n={len(rows)}: {rho:+.3f}")
        print("Negative rho supports the hypothesis: higher supervision uncertainty -> lower work quality.")
    else:
        print("Need >=2 points for a correlation.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--task")
    p.add_argument("--run-id")
    p.add_argument("--recorrelate", action="store_true", help="just print rho over recorded rows")
    args = p.parse_args()

    if args.recorrelate:
        _report(_load_rows())
        return

    res = grade_deliverable(args.task, args.run_id)
    row = {
        "task": args.task,
        "run_id": args.run_id,
        "uncertainty": _uncertainty(args.run_id),
        "score": res["score"],
        "n_criteria": res["n_criteria"],
        "n_pass": res["n_pass"],
        "n_low_confidence": res["n_low_confidence"],
        "judge_model": res["judge_model"],
        "judge_usage": res["judge_usage"],
        "verdicts": res["verdicts"],
    }
    rows = [r for r in _load_rows() if r.get("run_id") != args.run_id]  # dedupe by run_id
    rows.append(row)
    _save_rows(rows)
    print(json.dumps({k: v for k, v in row.items() if k != "verdicts"}, indent=2))
    _report(rows)


if __name__ == "__main__":
    main()
