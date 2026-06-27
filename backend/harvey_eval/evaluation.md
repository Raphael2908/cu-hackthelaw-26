# Harvey evaluation — findings & how we got them

How well does our Supervision Cockpit do on real legal work (the Harvey Labs benchmark), and —
the question the product actually cares about — **does our supervision layer's risk signal predict
where the work is bad?** This doc records what we found and the road we took to find it.

EU/GDPR tasks only: our citation model is CELEX/EUR-Lex-shaped, so EU tasks are the slice where the
worker's citations and the `citation_support` / `precedent_deviation` signals can fire faithfully.

---

## The three tracks

- **Track A — work quality.** Does the produced deliverable satisfy the task's rubric (each Harvey
  criterion is a PASS/FAIL `match_criteria`)? `score = criteria passed / total`.
- **Track B — supervision signals.** What do *our* checker signals say about that output:
  `citation_support_rate`, `deviation_score`, `disagreement_score`, composite `uncertainty`, the
  ranker's lane. This is the layer the product is about.
- **Track C — the real question.** Does Track B's `uncertainty` correlate with Track A quality?
  (Spearman ρ, uncertainty vs. Q-score across tasks.)

How a task is run: `harvey_eval/run.py` ingests a Harvey task, runs our shipped worker → checker →
ranker, renders the worker's findings to the expected `.docx`, seeds the 9-instrument EU CELEX
corpus so `citation_support` can resolve real citations, and records the signals + per-task
token/cost metering.

---

## Headline findings

1. **The impedance mismatch dominates everything.** Our worker is a *supervision* worker — it is
   hard-wired to "review a draft and surface checkable observations," never to *produce* a document.
   Every Harvey task is run through that one instruction (see "Planner" below). So work quality is
   determined mostly by **how close the task's nature is to "review"**, not by the model:

   | Harvey `work_type` | n | avg Q-score |
   |---|---|---|
   | review | 3 | **0.78** |
   | analyze | 5 | **0.58** |
   | draft | 2 | **0.13** |

   `draft` tasks ask for a produced legal document; the worker reviews instead, so it scores ~0.
   This is the single biggest determinant of our Track-A number.

2. **The most capable model scored the worst** on the same task (`summarize-gdpr`), graded
   identically by the per-criterion grader:

   | worker | uncertainty | Q-score | worker cost |
   |---|---|---|---|
   | Opus 4.8 | **0.365** | **1/46 (0.02)** | $1.87 |
   | Sonnet 4.6 | 0.89–0.97 | 25–30/46 (0.54–0.65) | ~$1.0 |
   | Haiku 4.5 | 0.921 | 36–38/46 (0.78–0.83) | $0.41 |

   Opus interpreted "review this draft" most literally — it *consistency-checked the source
   documents* (verifying the fine math, citation parallels) instead of writing the brief, so the
   strict grader failed nearly every "identify issue / make recommendation" criterion. The cheaper
   models just wrote an issue-spotting brief and scored far higher. Capability ≠ rubric-fit when the
   task framing is wrong.

3. **`uncertainty` is a weak predictor of work quality**, and inversely related at the model level.
   Track C, Sonnet worker, 10 EU tasks:

   | set | n | Spearman ρ |
   |---|---|---|
   | first batch | 5 | −0.60 |
   | all tasks | 10 | **−0.32** |
   | non-draft (review+analyze) | 8 | −0.29 |

   Directionally correct (higher uncertainty → lower quality) but weak and **not significant**
   (p ≈ 0.3). Two reasons: (a) `uncertainty` **saturates** — 9 of 10 Sonnet runs sit in
   [0.75, 0.99], so it barely spreads while quality ranges 0.0–0.83; (b) the clean signal was
   carried by the *draft* tasks (high uncertainty + ~0 quality) — **removing them weakens ρ**
   (−0.32 → −0.29), i.e. uncertainty catches *wholesale task-type failure* better than it
   discriminates *better vs. worse* among comparable work. That's consistent with what it actually
   measures: output **stability + citation-resolvability**, not task-fit.

4. **At the model level the signal does separate good from bad** the *wrong* way for Track C but the
   *right* way for triage: Opus (low uncertainty 0.365) produced rubric-worthless work (0.02);
   Haiku/Sonnet (high uncertainty ~0.9) produced the better work. So `uncertainty` flagged the
   model whose *stable, well-cited* output was nonetheless off-task — it measures "is this output
   internally trustworthy," which is exactly orthogonal to "did it do the assigned job."

---

## Track C data (Sonnet worker, 10 EU tasks, by uncertainty)

| uncertainty | Q-score | task | work_type |
|---|---|---|---|
| 0.690 | 0.828 (48/58) | review-saas-template | review |
| 0.751 | 0.583 (28/48) | map-eu-ai-act | analyze |
| 0.783 | 0.468 (22/47) | triage-vendor-contracts | analyze |
| 0.794 | 0.805 (33/41) | review-master-services | review |
| 0.812 | 0.698 (30/43) | identify-issues-DPA | review |
| 0.908 | 0.000 (0/62) | draft-scc-addendum | draft |
| 0.938 | 0.258 (16/62) | draft-dpa | draft |
| 0.965 | 0.543 (25/46) | summarize-gdpr | analyze |
| 0.969 | 0.714 (45/63) | analyze-counterparty | analyze |
| 0.991 | 0.568 (21/37) | compare-privacy | analyze |

Total worker cost ≈ $17 (10 Sonnet runs). Grader ≈ $0.15–0.23/task (one call each).

Old manual Track A (before the automated grader existed): Opus `summarize-gdpr` hand-graded at
**15/46** — the strict automated grader later put the same deliverable at **1/46**, because the
manual pass gave credit to figures that appear only as consistency checks; the strict grader
applies "mentioned ≠ satisfies."

---

## Why the planner matters (the fix for #1)

The Harvey harness **does not use the planner**. `run.py` builds the worker task by hand with no
`ai_instruction` and no `worker_instruction`, so `build_task_spec` falls back to the fixed
`_DEFAULT_REVIEW_INSTRUCTION` ("review the DRAFT against the FIRM STANDARD…") for *every* task —
draft, summarize, review alike. The planner (`plan_case`) is what assigns a task-appropriate
`kind` + `ai_instruction` (draft vs. review vs. extract) in the full cockpit flow. Routing Harvey
tasks through the planner — or mapping each task's nature to a `worker_instruction`/`kind` in
`run.py` — is the path to fixing the draft-task failures and getting a fair Track-A number.

> Note: a merge (`feat/process-map-track-record`) brings in `run_task` (per-`kind` instruction) and
> `plan_case` (the planner). That makes the planner *machinery* available, but the eval harness
> still bypasses it — resolving the merge is necessary, not sufficient, for planner involvement.

---

## How we built the grader (and a methodology trap)

- **Q-light** (first attempt): one holistic "rate this 0–1" judge call. It gave a **+1.0** Spearman
  on the first 2 tasks — the *wrong sign*. It over-credited a confident, well-structured deliverable
  that actually missed most requirements.
- **Q-full** (`grader_prompt.md` + `track_c/grade.py`): grade every `match_criteria` independently,
  strict ("mentioned ≠ satisfies", evidence-or-fail, numbers/dates checked exactly, distractor and
  threshold criteria handled), **one LLM call per task** (all criteria in a single message),
  `score = passes/total`. Reproducible to ±2 criteria (Haiku regrade: 36/46 → 38/46).
- Judge model is **independent of the worker** (Sonnet judges, even when Sonnet is the worker, the
  call is a separate strict-grading pass) — but note both Track A grader and Track B signals are
  LLM-derived, so a Track-C correlation is *suggestive, not ground truth*. We never ran Harvey's
  official `run_eval` judge (needs `pandoc` + credits).

---

## Operational issues we hit (so the next run doesn't)

- **`run.py` .env override:** originally `os.environ[k]=v` overwrote an explicit `PROVIDER_MODE=mock`
  with the repo `.env`'s `real` → silent real-mode API spend. Fixed to `setdefault`.
- **Anthropic credit exhaustion** mid-run (400 `credit balance too low`); no API to query balance —
  check the console.
- **Provider JSON robustness:** Haiku wrapped worker JSON in a ` ```json ` fence; Sonnet emitted an
  over-long/truncated citation-check JSON — both crashed the old strict parser. The merge's
  `_strip_fences` / `_loads_lenient` fixed this (task 5 `review-master`, which failed outright on
  Haiku and the first Sonnet tries, then completed).
- **Out-of-range signal:** Haiku returned `deviation_score = 10.0` (ignored the 0–1 scale), pushing
  `uncertainty` to **3.70** — `uncertainty` isn't clamped to [0,1] when the worker misbehaves
  (an `app/` clamping gap).
- **Windows file locks:** grading failed when a deliverable `.docx` was open in Word (a `~$…docx`
  lock file got globbed). Fixed `track_c/quality.py` to skip `~$` files.
- **Results-file races + manual edits:** parallel grades writing the shared `grader_results.jsonl`
  raced; hand-added `//HAIKU` / `//OPUS` section markers broke JSON parsing. Mitigated with
  `--no-save` for parallel grading and a tolerant loader (skips `//` / blank / bad lines).
- **Git branch trap:** a stray checkout to `master` (where `harvey_eval` doesn't exist) silently
  removed the harness files from the working tree; switching back to `feat/harvey-benchmark`
  restored them. Watch the branch before running.
- **Cost outlier:** `review-saas` cost **$6.23** (vs ~$1.5 typical) — large context × many
  disagreement re-runs/citation checks. Per-task cost is not bounded.

---

## Bottom line

- Track A (work quality) is **task-type-bound**: review ≈ 0.78, analyze ≈ 0.58, draft ≈ 0.13. The
  draft failures are a harness/planner gap, not a model failure.
- Track C: `uncertainty` is a **weak** quality predictor across heterogeneous tasks (ρ ≈ −0.3),
  strong only at flagging wholesale task-fit failure. It measures output stability +
  citation-resolvability, which is *useful for triage* but is not a quality score.
- The most defensible demo: an EU **review/analyze** task with clean PDF/DOCX/TXT docs in
  data-privacy (citations resolve against the seeded corpus), where the cockpit shows verified
  citations + a caught fabricated one → review lane → human sign-off.
