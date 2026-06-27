# Track C — grader-based correlation (Haiku worker)

Does our supervision `uncertainty` (Track B) predict a Harvey-backed quality score (Track A)?
Worker model: **claude-haiku-4-5**. Quality is the **Q-full** per-criterion grader (one Sonnet
call per task, using `grader_prompt.md`), `score = passes / criteria`. Raw per-criterion verdicts
are in `grader_results.jsonl`.

> Partial run: graded the **2 tasks completed so far** in the live `eu_haiku5/` sweep. The
> remaining 3 will be added once the sweep finishes. This file is separate from the sweep's
> `results.jsonl` and was produced without modifying the sweep.

## Data points

| Task | `uncertainty` | Q-full score | passes | low-conf |
|---|---|---|---|---|
| summarize-new-gdpr-enforcement-guidance | 0.9213 | **0.783** | 36/46 | 0 |
| compare-privacy-notice-against-statutory-disclosure-requirements | 0.9940 | **0.486** | 18/37 | 1 (C-030) |

**Spearman ρ (uncertainty vs Q-full score), n=2: −1.000** — higher supervision uncertainty tracks
lower work quality, the direction the supervision layer is supposed to deliver.

## Why this differs from Q-light

The cheap holistic judge (Q-light, one "rate 0–1" call) scored the **same two deliverables**
0.42 and 0.91 → ρ = **+1.000** (wrong sign): it over-credited the second deliverable's confident,
well-structured prose. Grading each `match_criteria` independently corrects that — the second
deliverable misses 19/37 specific requirements despite reading well.

| | task 1 | task 2 | ρ (n=2) |
|---|---|---|---|
| Q-light (holistic) | 0.42 | 0.91 | +1.000 ❌ |
| Q-full (per-criterion) | 0.783 | 0.486 | −1.000 ✅ |

## Cost / method

- One Sonnet call per task: ~$0.17 each (~$0.34 total). No per-criterion calls.
- Worker (Haiku) per task ≈ $0.41–0.49, vs ~$1.87 on Opus.

## Caveat — do not over-read

**n = 2 forces ρ to be exactly ±1.** Two points can only be perfectly monotonic; the magnitude is
meaningless. What's meaningful is that the *sign* is now correct and that the per-criterion scores
discriminate (0.78 vs 0.49). Real evidence needs the full 5-task set (target ρ ≈ −0.7 or stronger).
Both signals are LLM-derived, so a correlation is suggestive, not ground truth.
