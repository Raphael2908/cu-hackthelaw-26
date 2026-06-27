# Harvey Benchmark — Track C results (first 5 EU tasks, planner-driven)

## What the Harvey benchmark is

[Harvey Labs](https://www.harvey.ai/) publishes a suite of **real legal work tasks** — each a realistic
matter with (a) a set of source documents (contracts, memos, emails, regulatory text), (b) an
instruction brief, and (c) a **rubric of pass/fail criteria** (`match_criteria`) a senior lawyer would
use to grade the deliverable. Tasks span practice areas (data privacy, M&A, capital markets,
arbitration, …) and work types (`review`, `analyze`, `draft`, `research`). It is the closest public
proxy for "is this AI legal output actually any good," because quality is judged against an explicit,
lawyer-authored rubric rather than vibes.

## How we used it

Our product is a **supervision cockpit**: it doesn't just produce legal work, it triages completed AI
output by a measured **uncertainty** signal and surfaces checkable flags for a human. So the question
we care about isn't only "how good is the work" — it's **"does our uncertainty signal predict where
the work is bad?"** We run each Harvey task through three tracks:

- **Track A — work quality.** Run our shipped `worker → checker → ranker` over the task, render the
  worker's output as the expected `.docx`, and grade it against the Harvey rubric with an independent
  strict judge: `Q = criteria passed / total`.
- **Track B — supervision signals.** Record what our checker says about that same output: the three
  independent signals (citation support, precedent deviation, multi-run disagreement) and their
  composite **`uncertainty`**, plus the ranker's lane.
- **Track C — the real question.** Correlate Track B's `uncertainty` with Track A's quality
  (Spearman ρ). A strong **negative** ρ means higher uncertainty reliably flags lower-quality work —
  i.e. the supervision layer sends a partner's attention to the right place.

**EU/GDPR tasks only:** our citation model is CELEX/EUR-Lex-shaped, so EU tasks are the slice where the
checker's citation/deviation signals can fire faithfully against the seeded EU corpus.

**Planner as the entry point (this run).** Earlier runs hand-built the worker task with a fixed
"review the draft against the firm standard" instruction for *every* task — the single biggest drag on
quality. Here each task is first routed through the **planner** (`provider.plan_case`), which authors a
task-specific worker brief; the shipped pipeline then executes it. Worker model **claude-sonnet-4-6**;
the strict grader is an independent Sonnet call. The table below is the result on the first 5 EU tasks.

## Results

Ordered by uncertainty. Track B `uncertainty` vs. Track A strict per-criterion grader
(`score = passes / criteria`).

| Task | uncertainty | Harvey Q (passed/total) |
|---|---|---|
| review-master-services | 0.750 | 0.658 (27/41) |
| map-eu-ai-act | 0.786 | 0.638 (30/47) |
| summarize-new-gdpr | 0.882 | 0.630 (29/46) |
| compare-privacy-notice | 0.991 | 0.378 (14/37) |
| identify-issues-DPA | 1.000 | 0.167 (7/42) |

**Spearman ρ = −1.000 (perfect), n=5** — up from the prior non-planner version's **−0.60** on the same 5 tasks.
Every task's uncertainty rank is the exact inverse of its quality rank: higher supervision
uncertainty perfectly tracks lower work quality. The worst task (`identify-issues-DPA`, Q=0.167)
pegs uncertainty at its ceiling (1.000), so the cockpit floats it straight to the top of the review queue — supervision working as intended.

> **n=5 caveat.** A perfect rank match at n=5 is strong but small-sample (two-sided p≈0.017). Across 9
> graded EU tasks the planner-driven correlation is **ρ = −0.703** (vs the prior non-planner −0.32 at
> n=10) — still clearly stronger. Full batch 2 + combined detail in
> `backend/harvey_eval/track_c/planner_sonnet5_results.md`.
