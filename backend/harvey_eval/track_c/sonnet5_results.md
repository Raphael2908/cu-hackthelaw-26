# Track C — Sonnet worker, first 5 EU tasks

Worker model **claude-sonnet-4-6** (merged-backend `run_task` pipeline). Track B `uncertainty`
vs. Track A per-criterion grader (`grade.py` / `grader_prompt.md`, one Sonnet call each,
`score = passes / criteria`). Run-ids `eu_sonnet5/<slug>`. All 5 ran in parallel.

| Task | uncertainty | Q-score (criteria passed) | worker cost |
|---|---|---|---|
| summarize-new-gdpr-enforcement-guidance | 0.965 | 25/46 (0.543) | $1.13 |
| compare-privacy-notice-against-statutory-disclosure-requirements | 0.991 | 21/37 (0.568) | $1.37 |
| identify-issues-in-counterparty-data-processing-addendum | 0.812 | 30/43 (0.698) | $1.11 |
| map-eu-ai-act-transparency-obligations-to-existing-product-documentation | 0.751 | 28/48 (0.583) | $1.80 |
| review-master-services-agreement-for-regulatory-compliance | 0.794 | 33/41 (0.805) | $1.44 |

**Spearman ρ (uncertainty vs Q-score), n=5: −0.600.** Higher supervision uncertainty tracks lower
work quality — the intended direction. Total worker cost **$6.84** (5 parallel runs).

## Notes
- Cleanest Track C set so far: 5 complete points, **one worker model** (no Opus/Haiku confound),
  all uncertainties bounded in [0.75, 0.99], graded identically.
- The merged backend's lenient JSON parsing (`_strip_fences` / `_loads_lenient`) fixed the
  fenced/truncated-JSON crashes: `review-master-services` (failed outright on Haiku and on the first
  Sonnet attempts) now completes, and the out-of-range `uncertainty=3.70` deviation artifact did not
  recur.
- **ρ = −0.60 is moderate, not significant at n=5** (|ρ|≈0.9 needed for p≈0.05; p ≈ 0.28).
  Directionally consistent, not proof — more tasks needed. The two highest-uncertainty tasks (0.99,
  0.97) are the two lowest-quality; the lowest-uncertainty task (0.75 map-eu-ai-act) is mid-pack,
  which is the main wobble pulling ρ off −1.
