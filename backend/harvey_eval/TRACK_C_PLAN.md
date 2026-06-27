# Track C — does our supervision layer predict work quality? (PLAN, not executed)

**One question:** is our composite `uncertainty` (Track B) correlated with a Harvey-backed quality
metric (Track A)? If higher uncertainty tracks lower Harvey quality, the supervision layer is doing
its job — it flags the work that is actually worse, so a partner's attention goes to the right place.

**Audience:** hackathon judges → one persuasive chart + one number.
**Scope:** `backend/harvey_eval/track_c/` only. Reads `checker.py`/`ranker.py`, no `app/` edits.

---

## Hypothesis

> `uncertainty` ↑  ⇒  Harvey quality ↓   (negative correlation)

`uncertainty` = `compute_uncertainty(signals)` from `ranker.py:15` (the weighted composite of the
three signals). We treat it as one number; we do **not** evaluate the three sub-signals individually.

## The Harvey-backed metric (the y-axis)

Per task, a quality score in [0,1]. Two options, cheapest first:

- **Q-light (recommended for $5/20 tasks):** one judge call per task — "rate this deliverable's
  overall quality 0–1 against the task instructions." ~1 cheap Sonnet call/task.
- **Q-full:** Harvey's real rubric judge (`evaluation/run_eval.py`) → `score = passed/total criteria`.
  More credible, but 46 calls/task **and** needs `pandoc` + credits.

Either works as "some Harvey-backed metric." Start with Q-light; upgrade to Q-full if budget allows.

## Method

For N EU tasks:
1. Run our pipeline (`harvey_eval/run.py`) → record `uncertainty` (already in `our_eval.json`).
2. Score the deliverable → Harvey quality (Q-light or Q-full).
3. Join into rows `{task, uncertainty, quality, cost}`.
4. Compute **Spearman ρ** (rank correlation; robust, few assumptions) + p-value.

## Outputs (for judges)

- **Scatter plot:** `uncertainty` (x) vs. Harvey quality (y), one dot per task, trend line.
- **Headline number:** "ρ = −0.X (n=N) — higher supervision uncertainty predicts lower Harvey
  quality."
- *(stretch, if N allows)* **detection-vs-budget curve:** review the top-X% by uncertainty → what % of
  the low-quality tasks you catch.

## Budget

Task 1 cost $1.87 (big bundle, worker re-run 3× for disagreement). 20 full runs ≈ $37 — so $5 ≠ 20
full runs. To fit ~$5 across ~20 tasks: set `DISAGREEMENT_RUNS=2`, cap bundle tokens, use Q-light.
Otherwise spend $5 on ~3–5 full tasks and present the correlation at small N (labelled illustrative).

| Option | N | Quality metric | Est. cost |
|---|---|---|---|
| A (recommended) | ~all 20, cost-stripped | Q-light | ~$5 |
| B | 3–5 full | Q-full (rubric) | ~$5 |
| C | offline/mock | n/a (wiring only) | ~$0 |

## Caveats to state plainly (keeps it honest)

- **Small N** → wide confidence interval; report ρ with n and p, don't over-claim.
- **Circularity** — quality judge and our signals are both LLM-based; a correlation is suggestive, not
  proof. (Fine for a demo; note it.)
- **Impedance mismatch** — the worker reviews rather than drafts, so absolute Harvey scores are low;
  the *correlation* is still meaningful and is what we're testing.

## Artifacts

- `track_c/quality.py` — Q-light (and/or wrapper around `run_eval` for Q-full).
- `track_c/correlate.py` — join + Spearman ρ + scatter (and optional budget curve).
- `track_c/report.md` — the chart + the one-line finding.

> Prereqs before real spend: top up credits (+ `pandoc` only if using Q-full).
