# Architecture — Supervision Cockpit for Human and AI Legal Teams

> **Production build.** Originated on the Hack the Law (Cambridge) · Clifford Chance track.
> The problem it answers: *How do we supervise legal AI agents?*

This document is the single source of truth. Everything else (data model, services, API, UI)
derives from it. Read this and `current_progress.md` first.

---

## 1. Goal and scope

A production system that **delegates legal work under partner approval, then supervises it**: it
triages completed outputs, surfaces *checkable* flags, and records defensible sign-off, so a
supervising partner stays accountable without manually reviewing every output. (It began on the
Hack the Law / Clifford Chance track; it is now being built out as the real product.)

The one design principle that runs through everything:

> **Agents surface checkable claims. They never render verdicts. The human decides.**

A component that outputs "score 0.82, pass" asks the partner to *trust* it. A component that
outputs "this clause deviates from your firm's standard indemnity template, and the case it cites
does not support the proposition" is useful even when wrong, because the human verifies it in
seconds. We build the second kind.

**The whole spine matters, but depth concentrates in the supervision layer** (worker → checker →
ranker → cockpit → audit) — that is where the product's value lives. Delegation and orchestration
are built to solid, working breadth.

| Component | Depth | Meaning |
|---|---|---|
| Planner | Breadth | Sensible task list + assignments. Not optimal. |
| Coordinator | Breadth | Routes + tracks status. Simple state machine. |
| Associate interface | Breadth | Inbox + submit. Minimal styling. |
| Worker (review) | **Depth** | Structured output with citations + audit trail. |
| Checker + ranker | **Depth** | Three signals, the queue, the sampling lane. The centrepiece. |
| Cockpit | **Depth** | Queue, flag panel with one-click sources, approve/amend/reject, audit. |
| Debrief | Breadth | Templated summary from the case record. |

**Criticality ordering (what must never regress):** checker, ranker, cockpit and audit are
load-bearing — the supervision and accountability guarantees rest on them. Planner, coordinator,
associate interface and debrief support the flow around that core.

---

## 2. System overview

Three layers (see `system-design/architecture.png`).

- **Presentation.** The partner supervision cockpit (triaged queue, flag panel, approve/amend/reject)
  and a lighter associate view for hybrid/human tasks.
- **Orchestration (AI agents).** Planner, coordinator, worker agents, the checker (three signal
  generators), the ranker, and the debrief generator. The planner/coordinator/debrief are breadth;
  the worker/checker/ranker are depth.
- **Data and services.** Case store, append-only audit log, firm standards + process documents, and
  the EU Cellar corpus. One LLM provider sits alongside, behind a single interface.

**Control loop:** partner opens a case → planner scopes it and *proposes* assignments → partner
approves the plan → coordinator dispatches tasks to human or AI workers → workers review documents
against the firm standard, pulling sources from the corpus → checker generates flags → ranker
orders them → cockpit presents the queue back to the partner for decision. At case close the
debrief agent summarises the record.

---

## 3. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js (App Router) + Tailwind | All API calls through `lib/apiClient.ts`. |
| API | FastAPI (Python 3.12, `uv`, Pydantic v2) | Thin: validate → authorize → record → orchestrate via services. |
| Store | **SQLite** (one file) | The production store. Case store, task/assignment records, append-only audit log. `InMemoryRepo` for tests. |
| LLM | **Anthropic Claude** behind one `LLMProvider` | `PROVIDER_MODE=real` in production; `mock` replays fixtures for a keyless, offline fallback and the test suite. |
| Run | **Docker Compose** (backend + frontend) | Dockerized. In-process background dispatch today; Celery/Redis is the committed scale-up path (§8). No Supabase/Stripe. |

**Why this shape.** We start lean — a small local SQLite store, one LLM provider behind a single
service module, an offline fixture mode — and scale up component by component. The *conventions*
that make this maintainable (docs-driven, provider-behind-a-factory, repo pattern, mock-mode boot,
no-network tests) are exactly the seams that let us add Celery/Redis dispatch, web-search tools, and
more without rewrites. SQLite is a deliberate production choice for this workload, not a stopgap:
one file, transactional, easy to back up and reason about.

**Conventions (load-bearing):**
- **Provider abstraction + factory.** Orchestration depends only on the `LLMProvider` interface.
  `get_llm_provider()` returns the mock when `PROVIDER_MODE=mock`, else lazily imports the real
  Anthropic impl (which raises if its key is missing). Add a capability behind the interface, never
  in the orchestration.
- **Repo pattern.** All data access via one `Repo` ABC. Prod = `SqliteRepo`; tests = `InMemoryRepo`.
  Handlers/services never touch the SQLite SDK directly.
- **Centralized typed config.** One `Settings` (pydantic-settings); every external key has a
  mock-safe blank default so the stack boots with no secrets. Production fails loudly if real mode
  has no key.
- **Thin API, logic in services.** Routers validate/authorize/record; the worker, checker, ranker,
  planner, coordinator and debrief logic live in `services/`.

---

## 4. Infra phasing

- **Phase 0 (offline fallback).** One SQLite file, FastAPI + Next.js dev servers, mock provider.
  Runs on a laptop, offline, keyless. Retained as the network-free fallback and the test mode.
- **Phase 1 (now — the real run).** Same one SQLite file; `PROVIDER_MODE=real` + `ENV=production`
  against Anthropic Claude. **SQLite is the production store — we are not moving to Supabase/Postgres.**
  The repo seam stays (so a different store *could* drop in later) but is not exercised. Real auth
  (SSO/JWKS) in front of the `core/auth.py` seam is the remaining step before non-demo use.

The deployment design for a real legal deployment — where it runs, what is retained, data
residency, privilege — is an open decision we must make (see §13), not yet built. Any firm's
security review will press on it early.

---

## 5. Data model

SQLite tables, each a resource on the `Repo`. `id`s are uuid4 strings; timestamps are UTC ISO.

| Table | Key fields | Notes |
|---|---|---|
| `associates` | `name, practice_area, current_load, capacity` | Human-maintained capability + capacity registry. **Not scraped** (GDPR Art. 22 — see §13). The planner reads it to *propose*; the partner approves. |
| `corpus_documents` | `celex, title, kind, source_url, text, case_id, planted_defects(json), ground_truth(json)`, plus `task_types(json)` on process maps | `kind ∈ legislation\|case_law\|firm_standard\|process_doc\|draft`. **Multiple `process_doc` rows are allowed** — each is a selectable *process map* carrying its `task_types` (the sections). EU Cellar-modelled + synthetic firm standard/process maps; uploaded case documents are stored as `draft` rows tagged with `case_id`. |
| `cases` | `title, brief_text, goal, severity, process_doc_id, firm_standard_id, status, created_by` | `status ∈ open\|closed`. `severity` is the partner's up-front choice for the matter. |
| `plans` | `case_id, status, approved_by, approved_at` | `status ∈ proposed\|approved`. The plan is a **proposal**; nothing dispatches until `approved`. |
| `tasks` | `case_id, plan_id, title, description, task_type, assignee_type, assignee_id, assignee_rationale, severity, input_brief_slice, input_process_section, ai_instruction, status, order_index` | `assignee_type ∈ human\|ai\|hybrid` (chosen by task nature + the map's track record, §6); `assignee_rationale` explains the proposal; `severity ∈ low\|medium\|high\|extreme` set **up front** by the partner at case creation. |
| `submissions` | `task_id, produced_by, run_index, summary, findings(json), citations(json), clauses_relied_on(json), audit_sources(json)` | Worker output. `run_index` supports multi-run disagreement. `produced_by ∈ ai\|human\|hybrid`. |
| `flags` | `task_id, submission_id, signal_type, hard(bool), title, description, evidence(json), source_ref(json)` | `signal_type ∈ citation_support\|precedent_deviation\|multi_run_disagreement`. **Never** a pass/fail. `source_ref` resolves to a corpus doc + locator for one-click verification. |
| `risk_scores` | `task_id, severity_label, citation_support_rate, deviation_score, disagreement_score, uncertainty, priority, lane, sampled(bool)` | `lane ∈ review\|auto_clear`. Every signal stored separately so none is hidden behind the composite. |
| `decisions` | `task_id, action, note, amendment, decided_by, decided_at` | `action ∈ approve\|amend\|reject`. Append-only, signed (hash). |
| `audit_events` | `case_id, task_id, kind, type, actor, payload(json), prev_hash, hash` | Append-only, **hash-chained**. `kind ∈ accountability\|supervision` (see §11). |
| `debriefs` | `case_id, content(md)` | Generated at case close. |

**Task status state machine:**
`proposed → approved → dispatched → in_progress → submitted → checked → in_review →
signed_off | escalated | cleared`. Redo loops back to `approved` only by an explicit partner action.

---

## 6. The delegation model

The planner turns a goal into tasks, each carrying:
- **Assignee type** — human associate, AI agent, or hybrid (a human told to use a specific AI step,
  who remains the owner of the result).
- **Severity label** — chosen by the partner at case creation (`low|medium|high|extreme`), applied
  as the default for every task in the plan and overridable per task; not inferred later.
- **Inputs** — the slice of the brief, the relevant process-doc section, and (hybrid) the AI instruction.

The plan renders in the cockpit as an **editable proposal**. The partner can change an assignee,
split/merge tasks, adjust severity, or reject, then approves. **Only on approval does the
coordinator dispatch anything.** This is intentionally a thin state machine — the intelligence that
matters for this track is in the checker and cockpit, not the routing.

**Delegation is decided by task *nature*, never severity.** The planner agent chooses `assignee_type`
from what the task *is* — mechanical / low-judgment work (grammar, a first-look data-room triage,
summarising non-operative recitals) leans AI; work needing legal judgment on binding obligations
leans human/hybrid. Gating delegation on severity would starve a high/extreme-heavy firm of any AI
help, so severity stays purely the partner's triage dial (§7), not a routing rule.

**Process maps + the agentic track record.** A *process map* is a (optional) `process_doc` the
partner selects or adds, describing how the firm runs a standard kind of matter as named sections
(the task types). The process map is the **unit of "clean slate"**: a freshly added map has no
history, so the planner's nature-based suggestion stands and the partner decides where to insert AI.
As a map is reused, it accumulates an agentic track record *scoped to that map* (per section). The
planner overlays it on the suggestion: a section AI has a **clean** record on (≥ `AI_TRACK_RECORD_MIN`
completed AI/hybrid tasks, none amended or rejected) **graduates to AI**; one with an **adverse**
record is **pulled back** to a human owner. The record is computed in `services/track_record.py` from
completed tasks + their decisions — outcomes (signed-off / amended / escalated), never a verdict — and
each task carries an `assignee_rationale` explaining the proposal. The plan stays a proposal the
partner edits (§14.7).

---

## 7. The risk signal (the heart of the product)

Severity and uncertainty come from different places and must **not** be fused into one model guess.

### 7.1 Severity — set up front, owned by humans/policy
The partner's up-front risk call for the matter, chosen at case creation (`low|medium|high|extreme`)
and applied as the default for every task in the plan (overridable per task). Auditable as a
deliberate human choice, never a model inference.

### 7.2 Uncertainty — measured after the fact from checkable signals
A tunable weighted composite of three **independent, individually inspectable** signals. Each is
visible in the UI on its own, so no single number is load-bearing.

**Implementation map.** The three signals are generated in `services/checker.py` (one function
each); the composite + queue priority + lane assignment are computed in `services/ranker.py`; the
weights and run count live in `config.py`. Each signal calls the model only through the
`LLMProvider` interface — `providers/mock.py` (fixture replay, deterministic) or
`providers/real/anthropic_llm.py` (Claude). The reference scaffold each signal compares against is
the seeded **firm standard** (`fixtures/corpus.json`, `kind=firm_standard`); see §9 and §13.4 — note
there is no firm-facing UI to upload or version a standard yet (the API accepts a
`cases.firm_standard_id` but always falls back to the single seeded fixture).

A signal is either **model-judged** (a model produces the number/boolean, about external evidence)
or **mechanical** (pure arithmetic, no model opinion). This matters for §14.4: only the mechanical
parts are fully free of model self-assessment.

| Signal | Function (`services/checker.py`) | Raw score | Flag threshold | Hard? | Nature |
|---|---|---|---|---|---|
| Citation support rate | `citation_support` | `supported / cited_claims` (default `1.0` if none); each claim judged by `provider.check_citation_support` | any non-supporting **or** fabricated citation | **hard** | model judges each claim (boolean); **rate is mechanical** |
| Precedent deviation | `precedent_deviation` | **max** clause-distance from the firm standard (`provider.assess_deviations`) | clause score ≥ `0.5` (`DEVIATION_FLAG_THRESHOLD`) | soft | **model-judged** score (vs an external standard) |
| Multi-run disagreement | `multi_run_disagreement` | `1 − (intersection ÷ union)` of finding-IDs across N runs | score ≥ `0.3` (`DISAGREEMENT_FLAG_THRESHOLD`) | soft | **mechanical** (set overlap; no model self-confidence) |

1. **Citation support rate.** For each cited claim, retrieve the source from the corpus by CELEX and
   test whether it actually supports the claim. A **fabricated** citation (no such source) or a
   **non-supporting** one is a **hard** signal — surfaced regardless of severity. The per-claim
   verdict is the model's; the rate is just `supported / cited`.
2. **Precedent deviation.** Per-clause structural + semantic distance between the draft and the firm
   standard. The model returns a `score` per deviating clause; the signal is the **single worst**
   clause (max, not mean), so one egregious deviation can't be averaged away. Each flag's
   `source_ref` points at the exact standard clause for one-click verification. This score is
   model-produced — trustworthy only insofar as the firm standard is good (§13.4).
3. **Multi-run disagreement.** Re-run the review `max(2, DISAGREEMENT_RUNS)` times and measure
   divergence as the Jaccard distance over the set of finding-IDs per run (`0` = identical every
   run, `1` = no finding common to all). The cheapest-in-concept and most honest signal: it is pure
   set arithmetic and **never asks a model how confident it is**. Its load-bearing assumption is that
   "the same" finding gets a stable ID across runs — guaranteed in mock mode (IDs fixed in the
   fixture, divergence scripted by a per-finding `runs` list), but in real mode the **model emits the
   IDs**, so semantic equivalence is reduced to string-ID equality (a known calibration risk;
   clustering by clause + meaning would harden it).

   *Worked example (the `draft-govlaw-atlas` fixture).* Each finding carries an `id` — a stable
   label for "this specific finding" (e.g. `f-gov-1`), **not** a hash of its prose and **not** an
   LLM judging whether two findings match; runs are compared by exact string equality of those
   labels. The fixture has two findings: `f-gov-1` (scripted to appear in every run) and `f-gov-2`
   (scripted to appear only in run 1, via its per-finding `runs` list). Reviewing 3 times yields the
   label-sets `run 0 = {f-gov-1}`, `run 1 = {f-gov-1, f-gov-2}`, `run 2 = {f-gov-1}`. So
   `union = {f-gov-1, f-gov-2}` (|2|), `intersection = {f-gov-1}` (|1|, the only finding in *all*
   runs), and `score = 1 − 1/2 = 0.5`. That clears `DISAGREEMENT_FLAG_THRESHOLD` (`0.3`) and flags
   "Conclusions unstable across 3 runs", with the unstable set `union − intersection = {f-gov-2}` —
   the finding that flickered. The whole computation is set arithmetic over the labels; its honesty
   rests entirely on `f-gov-2` keeping the same label across runs (guaranteed in mock; the model's
   job in real mode).

**Where run-to-run variation comes from (and the role of `temperature`).** The disagreement signal
needs the N runs to differ, or it always reads `0`. There is **no API seed** — the Anthropic
Messages API has no `seed` parameter. `review_document` does interpolate `run_index` into the prompt
as the literal text `(variation seed: N)`, but that only makes the prompts non-identical; it does
**not** seed or control anything. The actual divergence comes from **stochastic sampling**: the real
provider calls `messages.create` **without setting `temperature`**, so it samples at the API default
(`1.0`), and identical prompts yield different findings across runs. Consequences worth owning:
- The signal's sensitivity is governed by an **uncontrolled default temperature**, so it is neither
  reproducible nor tunable as written. Setting `temperature` explicitly per run (e.g. a fixed mid
  value, or a deliberate spread across runs) is the obvious hardening step, and would make the
  `(variation seed: N)` suffix redundant.
- At `temperature = 0` the runs would be near-identical and disagreement would collapse toward `0` —
  i.e. the signal would report false confidence. So this signal **depends on sampling being on**.
- None of this affects the demo: mock mode scripts divergence deterministically and never calls the
  API, so scores are exactly reproducible.

The composite is computed in `ranker.py::compute_uncertainty` and is intentionally simple and
tunable (weights `W_CITATION`/`W_DEVIATION`/`W_DISAGREEMENT` in `config.py`, defaults `0.5/0.3/0.2`):

```
uncertainty = ( W_CITATION·(1 − citation_support_rate)
              + W_DEVIATION·deviation_score
              + W_DISAGREEMENT·disagreement_score ) / (W_CITATION + W_DEVIATION + W_DISAGREEMENT)
```

Dividing by the weight sum normalises, so a weight can be retuned without rescaling the others. The
point is not the exact formula; it is that each signal is also stored separately on `risk_scores`
and shown on its own in the UI, so no single number is load-bearing.

### 7.3 Queue and routing (ranker)
Computed in `services/ranker.py::score_task`. Severity (the up-front human call, §7.1) and the
measured uncertainty enter through different doors and are combined — never fused into one model
guess:

```
priority = 0.5·severity_weight + 0.5·uncertainty          # severity_weight: low .2 / medium .55 / high .9 / extreme 1.0
if any hard flag:  priority = max(priority, 0.95)          # hard signals bypass the weighting entirely
```

- **High severity + high uncertainty → top of the queue**, mandatory review.
- **Auto-clear lane** only when `severity == low` **and** `uncertainty < 0.15`
  (`LOW_UNCERTAINTY_THRESHOLD`) **and** no hard flag. Auto-cleared items are logged and **randomly
  sampled** into the partner's queue at `SAMPLE_RATE` (default `0.2`), like a financial audit — this
  is what lets us claim *scalable* supervision honestly instead of quietly moving accountability to a
  model. (`extreme` can therefore never auto-clear.)
- **Hard-fail signals** (e.g. a citation to a source that does not exist) are **always** surfaced via
  the `max(…, 0.95)` floor.
- **Nothing is ever auto-approved.** The risk signal triages the queue; it does not sign work off.

---

## 8. Async orchestration

Dispatching an approved AI/hybrid task runs the worker → checker → ranker pipeline, each transition
writing an audit event; the `coordinator` service is the state machine. Under real models this
pipeline is many slow calls, so dispatch runs **off the request path**: approve returns immediately
and the cockpit polls, surfacing each task as its pipeline finishes. The store serialises writes and
the audit chain is written under a lock, so concurrent workers stay safe and the chain stays valid.
A pipeline failure **fails safe** — the task escalates to a human, never silently dropped or
auto-reassigned (§14.6). In mock mode the pipeline is instant; tests set `ASYNC_DISPATCH=false` to
run it inline and keep post-approve assertions deterministic.

**Dispatch mechanism — current and committed.** Today this runs on an in-process **background thread
pool** (`core/background.py`, `ASYNC_DISPATCH=true`) — correct and simple, but bounded to one
process and lost on restart. The committed production path is **Celery workers backed by Redis**
(roadmap, `todo.md`): durable, retryable, horizontally scalable, surviving restarts. The
`coordinator` boundary is exactly where it slots in — submitting a task to the queue replaces
submitting it to the thread pool, and nothing else changes shape.

---

## 9. Storage

The "documents" are the corpus (EU Cellar-modelled legislation/case law + a synthetic firm standard
+ a process doc). They live in `corpus_documents` and are seeded from `backend/app/fixtures/` on
boot. Bulk document upload at case creation (`POST /api/cases/{id}/documents`, PDF/DOCX/text — with
`.pptx` on the roadmap, `todo.md`) is implemented: each file's extracted text becomes a `draft`
`corpus_document` tagged with its `case_id`, and the planner scopes tasks over a case's uploads
(falling back to the seeded drafts when none were uploaded). Extraction is best-effort plain text —
no OCR, no object store. `source_ref` on a flag is `{corpus_document_id, locator}` so the cockpit
links straight to the cited passage. Live external sources retrieved by agents (web search via
Perplexity, on the roadmap) are recorded the same way — every fetched source kept with its URL for
one-click verification, so it stays a checkable claim, never a verdict.

**Live EU Cellar (opt-in, `CELLAR_ENABLED`).** Resolves a cited CELEX against `corpus_documents`
first; on a miss, if Cellar is enabled, it fetches the document live from the EU Publications Office
(`providers/cellar.py`, behind a factory like the LLM provider) and **caches it as a
`corpus_document`**, so checks run against real EU law and the cached source is one-click-openable
like any other. It uses the **official machine-readable API, not HTML scraping**: the CELLAR REST API
via HTTP content negotiation (`GET {base}/resource/celex/{CELEX}`, `Accept: application/xhtml+xml` →
clean XHTML, Formex XML for pre-2014 docs — both parsed by one namespace-agnostic XML walk) for
content, and the SPARQL endpoint (`{base}/webapi/rdf/sparql`, CDM ontology) for title/type metadata
(best-effort; `kind` still derives from the CELEX sector as the reliable default). Both are public
(no auth); the SOAP expert-search service and bulk data dump — which *do* need an EU Login — are not
used. The connector defaults **off**, so the seeded fixtures remain the network-free fallback and the
test suite never touches the network.

Two consumers, behind the same seam:
- **Checker (verification).** The citation-support signal (§7.1) distinguishes a genuine *absence*
  (no such CELEX → the existing hard "fabricated" flag) from a transient *failure* (outage → a soft
  "unverifiable" flag, claim excluded from the rate), so an outage can never be mistaken for a
  fabricated citation (§14.1).
- **Worker (grounding).** When enabled, the worker hands the model a `fetch_eu_source` **tool**
  (Anthropic tool-use) so it can pull the real source by CELEX *while drafting* and cite actual law
  instead of a hallucinated CELEX — cutting fabricated citations at the source. A failed fetch
  becomes a tool note, never aborting the review; the checker still verifies independently. The
  worker owns the corpus caching (the provider never touches the repo), so a source the worker
  fetches is reused by the checker. The checker's multi-run review calls stay un-grounded to bound
  tool-call cost.

---

## 10. Auth

A real legal deployment needs proper auth (JWKS, SSO, RLS). Today a lightweight `CurrentUser`
defaults to the supervising **partner** identity, overridable by header for the associate view. The
seam (`core/auth.py`) is where real auth drops in — and wiring it (SSO/JWKS) is the **next
production step** before any non-demo use, not a deferred slide.

---

## 11. Two kinds of audit, kept separate (brief §3.2)

- **Audit for accountability.** A defensible, append-only, signed, **hash-chained** record of who
  decided what, when, and on what evidence (plan approvals, decisions, reassignments, close). The
  legal cover.
- **Audit for supervision.** Actionable signal (the flags) that routes a human's attention. What
  makes the partner faster.

Merging them produces a log that gives legal cover but no supervision, because nobody reads it. The
`audit_events.kind` field keeps them distinct; the cockpit's audit view renders them in separate
streams. The hash chain (`prev_hash → hash`) makes tampering detectable.

---

## 12. API surface (mounted under `/api`)

| Method + path | Purpose |
|---|---|
| `GET /healthz`, `GET /api/healthz` | Liveness. |
| `GET /api/corpus`, `GET /api/corpus/{id}` | List / fetch corpus docs (for one-click source view). |
| `GET /api/process-maps` · `POST /api/process-maps` | List process maps; lightweight structured create (title + sections). |
| `GET /api/track-record?process_doc_id=` | Per-map agentic track record: per-section outcomes + completed-task log. No verdict. |
| `GET /api/associates` · `POST /api/associates` | Capability + capacity registry. |
| `POST /api/cases` · `GET /api/cases` · `GET /api/cases/{id}` | Case intake (with severity) + list/detail. |
| `POST /api/cases/{id}/documents` · `GET /api/cases/{id}/documents` | Bulk-attach case documents (PDF/DOCX/text) for the planner; list them. |
| `POST /api/cases/{id}/plan` | Run the planner → a **proposed** plan with tasks. |
| `GET /api/plans/{id}` · `PATCH /api/tasks/{id}` | Read plan; edit a proposed task (assignee/severity/split). |
| `POST /api/plans/{id}/approve` | **Approval gate** — records, then dispatches. |
| `GET /api/inbox` · `POST /api/tasks/{id}/submit` | Associate inbox + human submission. |
| `GET /api/cases/{id}/cockpit` | The ranked queue + auto-clear lane + sampled items. |
| `GET /api/tasks/{id}` | Task detail: submission, flags (with sources), risk breakdown. |
| `POST /api/tasks/{id}/decision` | approve / amend / reject → writes a signed record. |
| `POST /api/tasks/{id}/reassign` | Partner-approved redo/reassignment (never automatic). |
| `GET /api/cases/{id}/audit` | Read-only audit: decisions vs flags, hash chain. |
| `POST /api/cases/{id}/close` · `GET /api/cases/{id}/debrief` | Close + generated debrief. |

No endpoint returns an agent-generated verdict.

---

## 13. Observability & open questions (kept visible, not hidden — brief §4)

1. **Calibration of uncertainty.** Our three signals are imperfect. Multi-run disagreement is the
   most trustworthy; citation checking depends on retrieval quality; deviation depends on a good
   firm standard. We claim a useful *triage* signal, not a correct one.
2. **Privilege & confidentiality.** Routing privileged material through multiple agents and
   retaining intermediate evidence raises waiver/confidentiality risk. The deployment design (where
   it runs, what is retained, data residency) is an open decision to make before production use, and
   it gets sharper as agents reach out to the web (Perplexity) — what leaves the boundary must be
   governed.
3. **Sampling rate is a policy lever, not a constant.** Too low → drift slips through; too high → the
   efficiency claim weakens. Set per task type by the firm (`SAMPLE_RATE`).
4. **Standards quality is a dependency.** Precedent deviation is only as good as the firm standard it
   compares against. Garbage scaffold, garbage signal.
5. **Surface area.** The full spine is broad. Depth concentrates where it matters (§1), and the
   provider / repo / dispatch seams keep scale-up (Celery/Redis, web search, pptx) incremental
   rather than rewrites.

---

## 14. Non-negotiable design principles

1. Agents surface checkable claims, never verdicts.
2. Nothing is ever auto-approved.
3. Severity is set up front (policy/human choice), not inferred by an AI after the fact.
4. Uncertainty is measured from checkable signals, never a model's self-reported confidence.
5. Low-risk items that clear without full review are randomly sampled, like a financial audit.
6. Escalation toward a human may be automatic (fail safe). Auto-reassignment of flagged work back
   into the machine without a human seeing it is not permitted.
7. The plan is a proposal and assignment is suggested — never dispatched/allocated without the
   partner's explicit, recorded approval.

### Deliberate cuts (brief §2.3)
- No LinkedIn/CV scraping for capability profiling (GDPR Art. 22) → human-maintained registry.
- No AI grading of purely human work product → the checker inspects only AI/hybrid-AI output.
- No raw chain-of-thought as the audit record → we log decisions + checkable evidence, not model
  introspection (reasoning traces are often post-hoc rationalisation and can mislead a court).
