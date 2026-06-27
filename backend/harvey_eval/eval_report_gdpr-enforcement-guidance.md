# Comprehensive evaluation — one EU task

**Task:** `data-privacy-cybersecurity/summarize-new-gdpr-enforcement-guidance`
*Summarize New GDPR Enforcement Guidance — Executive Regulatory Brief for a SaaS
workforce-analytics company (NovaBridge / PulseView).*

**Setup:** branch `feat/harvey-benchmark`, provider **real** (Anthropic `claude-opus-4-8`).
Our shipped worker → checker → ranker is run over the Harvey task with the 9-instrument EU
CELEX corpus seeded so `citation_support` can resolve real citations.

The benchmark has two tracks:
- **Track A — work quality.** Does the produced deliverable satisfy the task's rubric
  (46 criteria)? Normally scored by Harvey's LLM judge (`evaluation/run_eval.py`,
  `claude-sonnet-4-6`, one call per criterion).
- **Track B — supervision.** What do *our* checker signals + ranker say about that output?
  This is the layer the product is actually about.

> ### Note on the Track A number
> The **automated** Harvey judge could not be run for this report, for two reasons:
> 1. **Anthropic credits are exhausted** — a clean probe returns
>    `400 invalid_request_error: credit balance too low`. The judge uses the same key.
> 2. **`pandoc` is not installed** — `evaluation/scoring.py` extracts `.docx` deliverables
>    via pandoc; without it the judge receives an error string and fails every criterion.
>
> The Track A section below is therefore a **manual replication** of the judge: each
> criterion graded against the *actual rendered deliverable text* using its own
> `match_criteria`, exactly as the judge would (judge sees deliverable + criterion only).
> It is reproducible by the automated judge once credits + pandoc are available — see the
> last section for the exact command.

---

## Track B — supervision signals (real, measured)

| Signal | Value | What it means |
|---|---|---|
| `citation_support_rate` | **1.0** | every CELEX the worker cited resolved against the seeded corpus |
| `deviation_score` | 0.95 | high divergence from the synthetic firm standard (the task instructions) |
| `disagreement_score` | 0.4 | conclusions partly unstable across 3 worker re-runs |
| `uncertainty` (composite of the 3 signals) | 0.365 | |
| `priority` | 0.6325 | ranker's routing score |
| `lane` | **review** | routed to human review (not auto-anything — never is) |
| `sampled` | false | not additionally pulled for spot-check |
| `has_hard_flag` | **false** | no fabricated / unsupported-citation flag |
| `corpus_celex_seeded` | 9 | GDPR, Schrems II, SCCs, DPF, AI Act, … |
| `n_findings` | 15 | worker's checkable observations |
| `n_flags` | 12 | |

**Flags (all soft, `hard=false`):**
- **11 × `precedent_deviation`** — deviation from the firm standard, one per source doc
  (AP decision summary, EDPB guidelines summary, processing overview, compliance tracker,
  cover email) plus several on the overall DRAFT package.
- **1 × `multi_run_disagreement`** — "conclusions unstable across 3 runs".

**Reading it:** the supervision layer behaved exactly as designed. Corpus seeding made
`citation_support` *discriminate* (1.0 with no hard flag — every citation resolved; contrast
the unseeded baseline where real EU citations were falsely branded "fabricated"). The ranker
routed to **review** with 12 soft flags and **rendered no verdict** — consistent with the one
rule (agents surface checkable claims; the human decides).

### Cost / tokens (metering)

| | |
|---|---|
| LLM calls | 5 (worker review + deviation + citation + ≥2 disagreement re-runs) |
| input tokens | 279,289 |
| output tokens | 18,868 |
| cache read | 0 |
| **total** | **298,157** |
| **cost** | **$1.8681** (Opus 4.8 @ $5 / $25 per 1M in/out) |

High vs. a "few cents" estimate because the bundle is large (~279k input) and `cache_read=0`
— the shared prompt prefix isn't cached across the 5 calls. Prompt caching lives in
`app/providers/` (off-limits to this branch); enabling it would roughly halve this.

---

## Track A — work quality (manual judge replication)

> ⚠️ Manual grading, not the automated judge. Binary pass/fail per criterion against the
> rendered `executive-regulatory-brief.docx`. "low-conf" marks criteria a real judge could
> flip.

### Score

**Estimated ~15 / 46 criteria pass (~33%). Overall: TASK FAIL** (Harvey requires all-pass for
a "task pass"; the fractional score is ~0.33). 14 are clear passes, ~1 leans pass, ~6 are
borderline (graded fail), 25 are clear fails.

The distribution is the whole story: **passes cluster on factual / arithmetic criteria;
fails cluster on every "recommend X" and remediation-roadmap criterion.** That is structural,
not random — see "Why" below.

### The root cause: worker↔task impedance mismatch

The worker **did not write the executive brief**. It treated the five Harvey source documents
as "the DRAFT to review" and emitted *checkable observations about that source set* (figure /
citation / cross-document consistency, plus the deliverable-gap itself). Its own summary:
*"The submitted DRAFT does not contain a separately drafted executive brief; it reproduces the
underlying source documents themselves."*

This is by construction: our worker is a **supervision** worker (surface checkable claims about
a draft, never a verdict). The Harvey task is a **production** task (synthesize a brief that
spots 11 GDPR issues + recommendations + a prioritized roadmap). So the worker passes the
criteria it is built to verify (does the math reconcile? are citations internally consistent?)
and fails the criteria that require *authoring advice* (recommend a legal-basis transition,
build a remediation roadmap, assign owners and timelines).

### Per-criterion verdicts

| ID | Subtask | Verdict | Evidence (deliverable) |
|---|---|---|---|
| C-001 | LI inappropriate for productivity metrics (¶34) | ✗ FAIL | only notes ¶34 citation consistency (F7), not the gap |
| C-002 | Recommend transition to alt legal basis | ✗ FAIL | no recommendation authored |
| C-003 | Notes impact on 740+ enterprise DPAs | ✗ FAIL | F12 cites 740+ as a scale figure, not DPA-update impact |
| C-004 | TalentScope precedent linked to LI issue | ✗ FAIL | not linked |
| C-005 | Bundled consent defective | ✗ FAIL | not identified |
| C-006 | Declining consent blocks survey access | ✗ FAIL | not mentioned |
| C-007 | No consent-withdrawal mechanism | ✗ FAIL | not mentioned |
| C-008 | EDPB ¶47 voluntariness criteria | ✗ FAIL (low-conf) | F6/F7 cite ¶47 + red-flag threshold but don't describe the voluntariness test |
| C-009 | 97.3% acceptance as coercion evidence | ✓ PASS | F6: 97.3% exceeds the 90–95% red-flag threshold |
| C-010 | Recommend redesigned consent architecture | ✗ FAIL | no recommendation |
| C-011 | Per-employee scores trigger Article 22 (¶58) | ✓ PASS (low-conf) | F15: per-employee scores generated/retained, "Art 22 point-of-generation" |
| C-012 | Cohort aggregation does not avoid Art 22 | ✓ PASS | F15: scores retained "regardless of aggregated delivery (min cohort 5)" |
| C-013 | Recommend Art 22 safeguards / score elimination | ✗ FAIL | no recommendation |
| C-014 | Model training as separate processing purpose (¶71) | ✗ FAIL | F7 cites ¶71 only; not flagged as a separate-purpose gap |
| C-015 | Pseudonymization alone insufficient | ✗ FAIL | not addressed |
| C-016 | Recommend updated DPAs / notices for training | ✗ FAIL | no recommendation |
| C-017 | Purpose-specific TIA needed (¶83) | ✗ FAIL (low-conf) | F10 notes general-purpose TIA; F7 cites ¶83; deficiency not asserted |
| C-018 | DPIA stale, needs refresh | ✗ FAIL (low-conf) | F9 notes Sept-2023 staleness as a date check, no refresh recommendation |
| C-019 | DPIA refresh identifies ≥2 of 3 gaps | ✗ FAIL | no refresh content |
| C-020 | TalentScope DPIA failure as precedent | ✗ FAIL | not connected |
| C-021 | Excessive retention (36/24 mo vs 12) | ✓ PASS | F5: 36 mo exceeds TalentScope's sanctioned 30; 12 deemed sufficient |
| C-022 | Recommend retention review w/ 12-mo benchmark | ✗ FAIL (low-conf) | F5 states the benchmark but recommends nothing |
| C-023 | Comparable fine ~€8.1M | ✓ PASS | F4: €8.103M |
| C-024 | Max fine ~€11.6M | ✓ PASS | F4: €11.576M |
| C-025 | Insurance gap ~€3.1M | ✓ PASS | F4: €8.103M − €5M = €3.103M uninsured |
| C-026 | Recommend increasing insurance sub-limit | ✗ FAIL | no recommendation |
| C-027 | IPO / S-1 disclosure risk | ✗ FAIL | not mentioned |
| C-028 | Remediation timeline intersects IPO | ✗ FAIL | not mentioned |
| C-029 | Article 35(11) ongoing DPIA review | ✗ FAIL | not mentioned |
| C-030 | Art 28(3)(f) processor duty to assist | ✗ FAIL | not mentioned |
| C-031 | SCC module-selection error (Module 3 vs 4/1) | ✓ PASS | F8: extensive Module 3 vs Module 4/1 mismatch analysis |
| C-032 | DISTRACTOR: cohort min-5 does NOT resolve Art 22 | ✓ PASS | F15 treats score generation as the issue regardless of aggregation |
| C-033 | Summarize EDPB Guidelines, ≥2 provisions plain-language | ✗ FAIL (low-conf) | lists ¶34/47/58/71/83 topics but as consistency checks, not plain-language summary |
| C-034 | Summarize TalentScope incl €8.5M fine | ✓ PASS | F3: fine €8.5M |
| C-035 | Fine ≈ 2.8% of turnover | ✓ PASS | F3: ~2.8% of turnover |
| C-036 | Describe violations in TalentScope decision | ✓ PASS | F5: excessive retention (30 mo) — ≥1 specific violation |
| C-037 | TalentScope product similar to PulseView | ✗ FAIL (low-conf) | both named in Summary; similarity-as-precedent not stated |
| C-038 | Prioritized remediation roadmap | ✗ FAIL | no remediation section exists |
| C-039 | Assign responsible parties | ✗ FAIL | none |
| C-040 | Recommended timelines | ✗ FAIL | none |
| C-041 | Flag escalation to outside counsel / board | ✗ FAIL | none |
| C-042 | Dutch AP as lead supervisory authority | ✓ PASS | references the Dutch AP / AP-2025-0042 throughout |
| C-043 | NovaBridge EUR turnover €289–290M | ✓ PASS | F4: €289.4M |
| C-044 | Coordinate w/ securities counsel re IPO | ✗ FAIL | not mentioned |
| C-045 | EDPB Guidelines 03/2024 + Dec-2024 date | ✓ PASS | Summary "EDPB Guidelines 03/2024"; F13 "adopted December 12, 2024" |
| C-046 | AP-2025-0042 + Jan-2025 date | ✗ FAIL | number referenced; January-2025 publication date not stated |

**Clear passes (14):** C-009, C-012, C-021, C-023, C-024, C-025, C-031, C-032, C-034, C-035,
C-036, C-042, C-043, C-045. **+1 lean pass:** C-011.

---

## Synthesis

| | Track A (work quality) | Track B (supervision) |
|---|---|---|
| Result | ~15/46 (~33%), task FAIL | uncertainty 0.365 → **review** lane, 12 soft flags, no hard flag |
| Verdict rendered? | n/a (rubric grading) | **No** — checkable claims only |
| Driver | impedance mismatch: supervision worker on a production task | corpus seeding made `citation_support` discriminate |

1. **The two tracks measure different things, and that's the point.** Track A says the worker
   is a poor *drafter* of this brief (correct — it isn't a drafter). Track B says the
   *supervision* layer correctly characterised the output as deviating heavily from the brief
   spec (deviation 0.95) and routed it to a human, citing nothing fabricated. The product is
   Track B.
2. **The Track-A passes are exactly the worker's wheelhouse:** arithmetic reconciliation
   (€8.1M / €11.6M / €3.1M), retention vs. benchmark, SCC module mismatch, the Art-22
   distractor, citation/figure consistency. The fails are uniformly "author advice", which the
   supervision worker does not do.
3. **For a fair Track-A number on production tasks** we'd need a worker that *produces*, not
   one that *reviews*. Alternatively, accept that these EU production tasks exercise the
   supervision layer and report Track A as a known floor.

## To get the real automated Track A later

1. Top up Anthropic credits (console → Plans & Billing).
2. Install pandoc (`choco install pandoc -y` or `winget install JohnMacFarlane.Pandoc`).
3. From `harvey-labs/` (key available in env):
   ```
   uv run python -m evaluation.run_eval \
     --run-id 'eu_smoke5/summarize-new-gdpr-enforcement-guidance' \
     --task  'data-privacy-cybersecurity/summarize-new-gdpr-enforcement-guidance' \
     --judge-model claude-sonnet-4-6
   ```
   Writes `results/<run-id>/scores.json` (real per-criterion verdicts) + a report. Compare
   against the manual table above — discrepancies are most likely among the six "low-conf" rows.
