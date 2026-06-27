# Architecture — Supervision Cockpit for Human and AI Legal Teams

> **Hack the Law (Cambridge) · Clifford Chance track**
> Problem: *How do we supervise legal AI agents?*

This document is the single source of truth. Everything else (data model, services, API, UI)
derives from it. Read this and `current_progress.md` first.

---

## 1. Goal and scope

Build a working web demo of a system that **delegates legal work under partner approval, then
supervises it**: it triages completed outputs, surfaces *checkable* flags, and records defensible
sign-off, so a supervising partner stays accountable without manually reviewing every output.

The one design principle that runs through everything:

> **Agents surface checkable claims. They never render verdicts. The human decides.**

A component that outputs "score 0.82, pass" asks the partner to *trust* it. A component that
outputs "this clause deviates from your firm's standard indemnity template, and the case it cites
does not support the proposition" is useful even when wrong, because the human verifies it in
seconds. We build the second kind.

**Build the whole spine, keep every component thin.** Depth goes into the supervision layer
(worker → checker → ranker → cockpit → audit) — that is what this track rewards. Delegation and
orchestration are built to working breadth.

| Component | Depth | Meaning |
|---|---|---|
| Planner | Breadth | Sensible task list + assignments. Not optimal. |
| Coordinator | Breadth | Routes + tracks status. Simple state machine. |
| Associate interface | Breadth | Inbox + submit. Minimal styling. |
| Worker (review) | **Depth** | Structured output with citations + audit trail. |
| Checker + ranker | **Depth** | Three signals, the queue, the sampling lane. The centrepiece. |
| Cockpit | **Depth** | Queue, flag panel with one-click sources, approve/amend/reject, audit. |
| Debrief | Breadth | Templated summary from the case record. |

**Fallback ordering (cut from the bottom if time runs short):** debrief → associate interface
(simulate the human submission) → planner depth (hand-author one plan). Protect checker, ranker,
cockpit, audit to the end.

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
| Store | **SQLite** (one file) | Case store, task/assignment records, append-only audit log. `InMemoryRepo` for tests. |
| LLM | **Anthropic Claude** behind one `LLMProvider` | `PROVIDER_MODE=mock` (default) replays fixtures → the whole demo runs offline, keyless. |
| Run | One backend command + one frontend command | No Celery/Redis/Supabase/Stripe/Docker — deliberately. |

**Why this shape.** The brief (§5) steers explicitly to "a small local store… one LLM provider
behind a single service module… runnable from one command… runs offline from fixtures." Heavy
infra would fight the on-stage demo. We keep the *conventions* that make a stack maintainable —
docs-driven, provider-behind-a-factory, repo pattern, mock-mode boot, no-network tests — without
the operational weight.

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

- **Phase 0 (the offline demo).** One SQLite file, FastAPI + Next.js dev servers, mock provider.
  Runs on a laptop, offline. Still the fallback for a keyless, network-free demo.
- **Phase 1 (now — the real run).** Same one SQLite file; `PROVIDER_MODE=real` + `ENV=production`
  against Anthropic Claude. **SQLite is the production store — we are not moving to Supabase/Postgres.**
  The repo seam stays (so a different store *could* drop in later) but is not exercised. Real auth
  (SSO/JWKS) in front of the `core/auth.py` seam is the remaining step before non-demo use.

The deployment answer for a *real* legal deployment — where it runs, what is retained, data
residency, privilege — is a slide, not build scope (see §13). A Clifford Chance judge will ask early.

---

## 5. Data model

SQLite tables, each a resource on the `Repo`. `id`s are uuid4 strings; timestamps are UTC ISO.

| Table | Key fields | Notes |
|---|---|---|
| `associates` | `name, practice_area, current_load, capacity` | Human-maintained capability + capacity registry. **Not scraped** (GDPR Art. 22 — see §13). The planner reads it to *propose*; the partner approves. |
| `corpus_documents` | `celex, title, kind, source_url, text, planted_defects(json), ground_truth(json)` | `kind ∈ legislation\|case_law\|firm_standard\|process_doc`. EU Cellar-modelled + synthetic firm standard/process doc. |
| `cases` | `title, brief_text, goal, process_doc_id, firm_standard_id, status, created_by` | `status ∈ open\|closed`. |
| `plans` | `case_id, status, approved_by, approved_at` | `status ∈ proposed\|approved`. The plan is a **proposal**; nothing dispatches until `approved`. |
| `tasks` | `case_id, plan_id, title, description, task_type, assignee_type, assignee_id, severity, input_brief_slice, input_process_section, ai_instruction, status, order_index` | `assignee_type ∈ human\|ai\|hybrid`; `severity ∈ low\|medium\|high` set **up front** from the process doc. |
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
- **Severity label** — drawn from the process document, set **at plan time**, not inferred later.
- **Inputs** — the slice of the brief, the relevant process-doc section, and (hybrid) the AI instruction.

The plan renders in the cockpit as an **editable proposal**. The partner can change an assignee,
split/merge tasks, adjust severity, or reject, then approves. **Only on approval does the
coordinator dispatch anything.** This is intentionally a thin state machine — the intelligence that
matters for this track is in the checker and cockpit, not the routing.

---

## 7. The risk signal (the heart of the product)

Severity and uncertainty come from different places and must **not** be fused into one model guess.

### 7.1 Severity — set up front, owned by humans/policy
A label attached to each task when the plan is created, drawn from the process document (e.g.
verifying a binding obligation = High; summarising a non-key recital = Low). Auditable as a
deliberate choice, never a model inference.

### 7.2 Uncertainty — measured after the fact from checkable signals
A tunable weighted composite of three **independent, individually inspectable** signals. Each is
visible in the UI on its own, so no single number is load-bearing:

1. **Citation support rate.** For each claim with a cited source, retrieve the source and test
   whether it actually supports the claim. A fabricated or non-supporting citation is a **hard**
   signal — surfaced regardless of severity.
2. **Precedent deviation.** Structural + semantic distance between the output and the firm standard
   / process scaffold. High deviation raises the need for attention.
3. **Multi-run disagreement.** Run the review more than once (or with two models) and measure
   divergence in the conclusions/flags. The cheapest and most honest uncertainty signal — it relies
   on no one introspecting their own confidence.

The composite formula is simple and tunable (weights in `config.py`). The point is not the exact
formula; it is that each signal stands on its own in the UI.

### 7.3 Queue and routing (ranker)
- `priority = f(severity, uncertainty)`. High severity + high uncertainty = mandatory review, top
  of the queue.
- Low severity + low uncertainty → **auto-clear lane**: logged, and **randomly sampled** at a
  configurable rate (`SAMPLE_RATE`) into the partner's queue, like a financial audit. This is what
  lets us claim *scalable* supervision honestly instead of quietly moving accountability to a model.
- Hard-fail signals (e.g. a citation to a source that does not exist) are **always** surfaced.
- **Nothing is ever auto-approved.** The risk signal triages the queue; it does not sign work off.

---

## 8. Async orchestration

No Celery/Redis. Dispatching an approved AI/hybrid task runs the worker → checker → ranker pipeline,
each transition writing an audit event; the `coordinator` service is the state machine. Under real
models this pipeline is many slow calls, so dispatch runs on a **background thread pool**
(`core/background.py`, `ASYNC_DISPATCH=true`): the approve request returns immediately and the
cockpit polls, surfacing each task as its pipeline finishes. The store serialises writes and the
audit chain is written under a lock, so concurrent workers stay safe and the chain stays valid. In
mock mode the pipeline is instant; tests set `ASYNC_DISPATCH=false` to run it inline and keep
post-approve assertions deterministic. A pipeline failure **fails safe** — the task escalates to a
human, never silently dropped or auto-reassigned (§14.6). If this became real at scale, the same
service boundary is where a durable queue (Celery/SQS) would slot in — the code wouldn't change shape.

---

## 9. Storage

The "documents" are the corpus (EU Cellar-modelled legislation/case law + a synthetic firm standard
+ a process doc). They live in `corpus_documents` and are seeded from `backend/app/fixtures/` on
boot. Bulk document upload at case creation (`POST /api/cases/{id}/documents`, PDF/DOCX/text) is
implemented: each file's extracted text becomes a `draft` `corpus_document` tagged with its
`case_id`, and the planner scopes tasks over a case's uploads (falling back to the seeded drafts when
none were uploaded). Extraction is best-effort plain text — no OCR, no object store. `source_ref` on
a flag is `{corpus_document_id, locator}` so the cockpit links straight to the cited passage.

---

## 10. Auth

A real legal deployment needs proper auth (JWKS, SSO, RLS). For the demo we use a lightweight
`CurrentUser` defaulting to the supervising **partner** identity, overridable by header for the
associate view. The seam (`core/auth.py`) is where real auth drops in. Out of build scope, on a slide.

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
| `GET /api/associates` · `POST /api/associates` | Capability + capacity registry. |
| `POST /api/cases` · `GET /api/cases` · `GET /api/cases/{id}` | Case intake + list/detail. |
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
   retaining intermediate evidence raises waiver/confidentiality risk. The deployment answer (where
   it runs, what is retained, data residency) is a slide, out of build scope.
3. **Sampling rate is a policy lever, not a constant.** Too low → drift slips through; too high → the
   efficiency claim weakens. Set per task type by the firm (`SAMPLE_RATE`).
4. **Standards quality is a dependency.** Precedent deviation is only as good as the firm standard it
   compares against. Garbage scaffold, garbage signal.
5. **Breadth risk.** The full spine is a large surface for a hackathon. Mitigated by the depth table
   (§1) and the bottom-up fallback ordering.

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
