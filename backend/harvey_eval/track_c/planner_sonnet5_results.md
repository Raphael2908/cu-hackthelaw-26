# Track C — planner-driven worker, first 5 EU tasks

Worker model **claude-sonnet-4-6**, routed through the **planner** as the entry point
(`harvey_eval/run_planned.py`): for every task the planner (`provider.plan_case`) authors a
task-specific `ai_instruction`, which the shipped worker executes instead of the fixed
"review the DRAFT against the FIRM STANDARD" default. This is the fix `evaluation.md` headline #1
prescribes. Track B `uncertainty` vs. Track A per-criterion grader (`grade.py` /
`grader_prompt.md`, one Sonnet call each, `score = passes / criteria`). Run-ids
`planner_sonnet5/<slug>`. All 5 ran in parallel.

## Uncertainty vs Harvey score (this run), ordered by uncertainty

| Task | uncertainty | Harvey Q (passed/total) | worker cost |
|---|---|---|---|
| review-master-services-agreement-for-regulatory-compliance | 0.750 | 0.658 (27/41) | $1.57 |
| map-eu-ai-act-transparency-obligations-to-existing-product-documentation | 0.786 | 0.638 (30/47) | $2.04 |
| summarize-new-gdpr-enforcement-guidance | 0.882 | 0.630 (29/46) | $1.22 |
| compare-privacy-notice-against-statutory-disclosure-requirements | 0.991 | 0.378 (14/37) | $1.73 |
| identify-issues-in-counterparty-data-processing-addendum | 1.000 | 0.167 (7/42) | $1.44 |

**Spearman ρ (uncertainty vs Q-score), n=5: −1.000.** Every task's uncertainty rank is the exact
inverse of its quality rank — higher supervision uncertainty perfectly tracks lower work quality.
Total worker cost **$7.99** (5 parallel runs); grader ≈ $0.13–0.18/task.

## A/B vs the prior non-planner run (same 5 tasks)

The only changed variable is the planner-authored `ai_instruction` (worker `kind` stayed `review`,
same three signals), so this is a clean A/B against `sonnet5_results.md`.

| Task | unc (no planner → planner) | Q (no planner → planner) |
|---|---|---|
| summarize-new-gdpr | 0.965 → 0.882 | 0.543 → 0.630 |
| compare-privacy-notice | 0.991 → 0.991 | 0.568 → 0.378 |
| identify-issues-DPA | 0.812 → 1.000 | 0.698 → 0.167 |
| map-eu-ai-act | 0.751 → 0.786 | 0.583 → 0.638 |
| review-master-services | 0.794 → 0.750 | 0.805 → 0.658 |
| **Spearman ρ** | — | **−0.600 → −1.000** |

## Notes

- **The supervision signal got *sharper*, not just the work.** Track C ρ improved from −0.60 to a
  perfect −1.00. Work quality did **not** uniformly rise (two tasks improved, three dropped) — what
  improved is the *alignment* between our `uncertainty` and Harvey quality. The signal now ranks the
  five tasks' quality perfectly from its own three checkable signals.
- **The worst task is the one the signal screamed about.** `identify-issues-DPA` fell to Q=0.167 under
  the planner brief, and `uncertainty` hit its ceiling (1.000) — the cockpit would have floated it
  straight to the top of the review queue. That is the product working as intended: surface the bad
  output for the human, never auto-clear it.
- **n=5 caveat.** ρ=−1.00 at n=5 is a perfect rank match but still small-N (two-sided p≈0.017 for a
  perfect Spearman at n=5). Directionally very strong; the 10-task combined run extends it.
- All five deliverables carried a non-null planner `ai_instruction` (verified in each `our_eval.json`),
  confirming the planner — not the default review instruction — drove the worker.

---

# Batch 2 — next 5 EU tasks (planner-driven), and the combined picture

Same planner-driven pipeline, run-ids `planner_sonnet5b/<slug>`. **Two tasks were swapped out of the
prior `eu_sonnet5b` set**: `review-saas` (the $6.23 cost outlier) and `analyze-counterparty` (which
**structurally** overruns the worker's 32k `max_tokens` in the disagreement re-runs every run — its
"47 modifications across 28 clauses" produce a findings list too long to return as valid JSON, and
the streamed path doesn't catch the cut-off). They were replaced by `identify-privacy-…-transfer-
agreement` and `assess-impact-of-eu-ai-act-…` — so batch 2 is a fresh EU-5, not a strict A/B.

| Task | kind | uncertainty | Harvey Q (passed/total) | worker cost |
|---|---|---|---|---|
| review-master-services *(batch 1)* | review | 0.750 | 0.658 (27/41) | $1.57 |
| map-eu-ai-act *(batch 1)* | review | 0.786 | 0.638 (30/47) | $2.04 |
| triage-vendor-contracts-for-gdpr-cross | review | 0.869 | 0.511 (24/47) | $2.32 |
| draft-standard-contractual-clauses-addendum | **draft** | 0.835 | 0.159 (10/63) | $1.90 |
| summarize-new-gdpr *(batch 1)* | review | 0.882 | 0.630 (29/46) | $1.22 |
| identify-privacy-issues-transfer-agreement | review | 0.967 | 0.378 (17/45) | $1.78 |
| compare-privacy-notice *(batch 1)* | review | 0.991 | 0.378 (14/37) | $1.73 |
| identify-issues-DPA *(batch 1)* | review | 1.000 | 0.167 (7/42) | $1.44 |
| draft-data-processing-agreement | **draft** | 1.000 | 0.129 (8/62) | $2.47 |
| assess-impact-of-eu-ai-act-… | review | 0.952 | **ungraded** (credits) | $2.10 |

**Combined Spearman ρ (uncertainty vs Q), n=9: −0.703.** (assess-impact's worker run completed —
`uncertainty=0.952` — but its grader call was lost first to a malformed-JSON judge response and then
to API credit exhaustion; re-run `planner_batch` after topping up to make it n=10.) Total worker
cost: batch 1 **$7.99** + batch 2 **$10.56** = **$18.55**.

## What batch 2 shows

- **Track C holds across a broader EU set.** ρ = −0.703 at n=9 is stronger than the prior
  *non-planner* numbers (−0.60 at n=5, −0.32 at n=10) — the planner-driven worker's `uncertainty`
  is a better quality predictor, not just on the cleanest 5.
- **The draft tasks are NOT a fair test yet — a harness rendering gap.** The planner correctly routes
  `work_type=draft` to `kind=draft` (verified: both draft tasks ran with 2 applicable checks,
  precedent-deviation dropped, composite renormalised). **But `harvey_eval/run.py::render_docx`
  only renders the submission's `summary` + `findings` — it never renders the per-kind `payload`**
  (`draft_text` for draft, `key_points` for summarize, `obligations` for extract). So the actually-
  drafted document never reaches the graded `.docx`; the judge sees findings only. That is why the
  draft scores stayed low (0.129, 0.159) despite the routing fix. **To fairly test the draft-task fix,
  `render_docx` must emit `payload.draft_text` (and the other payloads) and the draft tasks must be
  re-run.** Until then the draft rows understate quality and should be read as "routing works,
  rendering+regrade pending," not "the planner didn't help drafts."
- The two highest-uncertainty tasks (both 1.000: `identify-issues-DPA`, `draft-dpa`) are the two
  lowest-quality — the triage signal again points the partner at the worst output.
