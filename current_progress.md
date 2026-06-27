# Current progress

Running build log. Newest at the top. Read `architecture.md` first for the design.

---

## Hint-text declutter — trim redundant helper copy

**Where we are.** A partner-facing readability pass: several screens carried long muted explainer
sentences that restated what the adjacent control already showed — visual noise for a time-poor
partner. Trimmed the redundancy while keeping every load-bearing one-rule statement (the product's
honesty messaging is not decoration).

**Cut**
- `app/page.tsx`: severity blurb 3 sentences → 1; upload hint dropped the "planner scopes tasks"
  clause → just the accepted formats; create helper dropped the navigation explainer — **kept**
  "Nothing is dispatched until you approve the plan".
- `app/cases/[id]/plan/page.tsx`: severity note 2 sentences → 1 — **kept** "not an AI inference".
- `components/ItemDetail.tsx`: removed "A steer for where to look — you decide" (duplicated the
  Step 3 hint) and "— each links to its source" (the View-source buttons make it obvious) — **kept**
  the Step 3 "none is a verdict" hint and the whole Step 4 decision framing.
- `app/cases/[id]/cockpit/page.tsx`: tightened three lane captions; dropped "like a financial audit"
  (still in the spot-check tag's tooltip) — **kept** the spot-check disclosure itself.

**Guardrail held.** Removed redundancy and decoration only; every "points to check, not verdicts" /
"nothing dispatched until you approve" / "not an AI inference" claim stays. Typecheck clean
(`tsc --noEmit`).

---

## Cockpit declutter, numbered review path, and plan-flow fixes

**Where we are.** Continuing the partner-facing pass on `feat/frontend-mockup`. A senior partner
found the cockpit unreadable (too many competing lanes, overloaded cards) and the create→plan flow
surprising. This work applies Gestalt grouping to the cockpit, reframes the per-item review as a
numbered process, and splits case creation from plan generation. All re-grouping and progressive
disclosure — every signal stays individually visible, never a fused verdict (the one rule holds).

**Built**
- **Cockpit queue declutter** (`app/cases/[id]/cockpit/page.tsx`). "Needs your review" is the one
  focal lane (figure/ground); its cards group under High/Medium/Low bands so priority is shown by
  grouping (proximity + similarity) — dropped the redundant per-card priority pill and progress bar.
  Each queue card slimmed to three things (title · one line of what to check, with flag count folded
  in as "+N more to check" · severity/spot-check). Secondary lanes (Cleared automatically, With a
  person, You've decided) collapse into expandable count-only summaries; "Questions from associates"
  stays a distinct actionable banner.
- **Numbered review path** (`components/ItemDetail.tsx`). The per-item pane's six equal-weight panels
  became a numbered path with a connecting spine (continuity): 1 Who did it & where it stands (header
  merged with the chain of custody — `TaskTrace` gained a `bare` mode to embed without a nested card)
  → 2 What was produced → 3 What to check (merged "what the checks found" + "points to check": the
  three signals as the steer, flags as concrete things to verify with source links) → 4 Your decision
  as the dominant focal endpoint. Steps 1–3 are light so they read as one flow; the associate
  conversation sits as a contextual block before the decision.
- **Split case creation from plan generation** (`app/page.tsx`, `app/cases/[id]/plan/page.tsx`).
  `onCreate` no longer chains `createPlan` — it creates + uploads, then routes to the plan page where
  generating the plan is an explicit partner step. The plan page now treats a missing plan (404) as
  the expected "no plan yet" state (not an error) and renders an empty-state with a partner-only
  **Generate plan** button; the proposal banner + **Approve plan** button only appear once a
  `proposed` plan exists. Two deliberate actions (generate, then approve) before anything dispatches.
- **PPTX upload hint** (`app/page.tsx`). The picker already accepted `.pptx` (backend PPTX ingestion
  landed earlier); the helper text now names PowerPoint so partners know decks are scoped too.
- **Docs.** `frontend/DESIGN.md` gained a "Gestalt grouping" subsection (figure/ground, proximity +
  similarity, continuity, focal point, common region). Typecheck clean (`tsc --noEmit`); ESLint is
  not configured in this project so it isn't a gate.

**Backlog groomed (queued in `todo.md`, not built).** Reassign action has no UI though the backend
endpoint + audit event exist; async-dispatch health / stalled-task hint for the Celery path; explicit
task filter on the audit page; **reshape the debrief into an issue-centric memo** (it's laid out by
data-model entity type, not by the matter — detailed backend+frontend steps recorded); cut redundant
hint text (with a guardrail to keep the load-bearing one-rule framing).

**What's next.** Pick up one of the queued items — reassign action or the debrief reshape are the
highest-value. Live progress / streaming for slow real-model runs remains the big frontend lift.

---

## Celery + Redis dispatch — thread pool retired

**Where we are.** The committed scale-up path (architecture.md §8) is in: the in-process
`ThreadPoolExecutor` is gone, replaced by **Celery workers backed by Redis** — durable, retryable,
horizontally scalable, surviving restarts. The `coordinator` boundary is unchanged; only the
dispatch mechanism moved.

**Built**
- `core/celery_app.py` (the Celery app, no app-internal imports) + `core/tasks.py`
  (`dispatch.run`). Only the serializable `task_id` crosses the process boundary; the worker
  rebuilds repo + provider from their factories (`get_repo()` / `get_llm_provider()`).
- `coordinator.dispatch_task` now enqueues `run_dispatch_task.delay(task_id)` when
  `ASYNC_DISPATCH` is on (lazy import to avoid the cycle). `ASYNC_DISPATCH=false` still runs the
  pipeline inline in-process — the test/offline fallback. Deleted `core/background.py`.
- **Cross-process audit-chain integrity (the load-bearing fix).** With the pipeline on a separate
  worker process, the in-process `threading.Lock`s in `audit.py`/`repo.py` no longer coordinate
  with the API process — concurrent appends could fork the hash chain. Fixed at the store: SQLite
  now runs in **WAL** with `busy_timeout` + `synchronous=NORMAL`, and writes use **BEGIN
  IMMEDIATE** so read-then-write is atomic across processes. Added a generic
  `Repo.insert_chained(table, build)` primitive (atomic last→build→insert); `audit.record_event`
  uses it and the module-level `_chain_lock` is gone.
- Docker: `redis` (7-alpine, healthchecked) + a `worker` service (same image, runs
  `celery -A app.core.celery_app.celery_app worker`) sharing the **same** SQLite volume as the
  backend — the WAL/BEGIN IMMEDIATE writes are what make that shared file safe. Backend + worker
  get `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` pointed at `redis://redis:...`.
- Config + env (`CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`, mock-safe localhost defaults;
  dropped `DISPATCH_WORKERS`), `make worker` target, and `.env.example` section.
- Tests stay offline: conftest sets `task_always_eager` so the one async test exercises `.delay()`
  with no broker; new `test_dispatch.py` covers `insert_chained` chain integrity and the task body
  reconstructing repo/provider + routing. `make test` green (19), `make lint` clean. Verified a
  real worker boots against live Redis and registers `dispatch.run`.

**What's next**
- PPTX ingestion and Perplexity web search (the remaining scale-up items in `todo.md`).
- Replace stub auth with real SSO/JWKS before any non-demo use.

---

## Partner-facing UX pass — traceability, plain language, conversation loop

**Where we are.** The supervision surfaces were built but read like a developer tool. This branch
(`feat/frontend-mockup`) reworks the frontend for a time-poor, non-technical supervising partner,
adds a partner↔associate conversation loop end to end, and records the design lens behind it. The
backend gains one new capability (task messaging / return-to-associate); everything else is UI.

**Decisions locked**
- **Design-led, evaluated against heuristics.** `frontend/DESIGN.md` records Nielsen's 10 usability
  heuristics applied decision-by-decision plus a cognitive walkthrough of a senior partner doing an
  end-to-end traceability task. The walkthrough named gaps (G1–G4 + a deep-link accelerator) that
  the following commits close.
- **Plain language without hiding the signals.** Every reframing keeps the measured figure visible
  alongside the friendly wording — still checkable claims, never a verdict (the one rule holds).
- **The role toggle is the view switcher**, not just an identity label: partner ⇄ associate switches
  the whole workspace.
- **Rejected work returns to the associate; escalation toward a human is permitted** (architecture
  §14.6). AI-only work still escalates (no associate to receive it).

**Built**
- **Traceability for the partner** (`8adbc39`): `TaskTrace` per-task chain of custody (owner +
  lifecycle stepper) with a deep link into the audit trail pre-filtered to that task (G2); at-a-glance
  status pills on the cases list so a case needing the partner is visible before opening it (G1);
  plain-language hints per tab in the case sub-nav (G3).
- **Plain-language audit + cockpit** (`dba28dc`): audit rewritten as one chronological timeline of
  plain sentences ("You signed off on…", "The AI worker submitted their work") with a friendly
  tamper-proof banner (hash tucked into a disclosure) and actor / task / kind filters;
  accountability vs supervision kept distinct per entry via a tag, not two jargon columns (G3/G4).
  Cockpit shows High/Medium/Low priority bands and "N points to check" instead of raw
  priority/uncertainty percentages; item detail's "What the checks found" reads each of the three
  checks in words with the figure alongside. Shared readings in `lib/plain.ts`.
- **Role toggle drives the view** (`595761c`): role-aware nav (partner = Cases, associate = My
  inbox), toggle + logo route to each role's home (`ROLE_HOME`), standalone Inbox link removed,
  inbox reworded as the associate's workspace with a banner if a partner deep-links in.
- **Debrief as a review-friendly report** (`32e8afa`): letterhead header (title, status, goal
  callout, generated date), Print / Save PDF action, and an honesty footer (a summary, not a
  sign-off); `DebriefReport` renders sections as cards (tasks with assignee/severity/status badges,
  flags colour-coded hard/soft with the signal chip, decisions with signed-off/amended/rejected
  pills, carry-forward as a checklist), falling back to Markdown cards for free-form real-model
  output.
- **Partner↔associate ping-pong — backend** (`bf9fed7`): reject on human/hybrid work returns it to
  the associate (status `returned`) with the partner's note as a message instead of dead-ending at
  `escalated`; new `task_messages` table + thread so an associate can ask a question
  (`awaiting_clarification`, surfaced in the cockpit) and the partner answers (`returned`).
  `POST /tasks/{id}/message` is role-aware; cockpit gains a needs_reply lane; inbox carries returned
  + awaiting tasks with their thread. Tests cover return-and-resubmit, the Q&A loop, the
  no-open-question guard, and AI-still-escalates (`test_pingpong.py`).
- **Partner↔associate conversation — frontend** (`31999e2`): `MessageThread` chat UI (partner
  right/navy, associate left/sky, bubbles labelled return / question / answer); item-detail
  conversation panel with status-aware actions (reply box when a question is open, "sent back,
  awaiting rework" when returned, reject relabelled "Reject & send back"); cockpit "Questions from
  associates" lane; inbox shows returned tasks with the partner's reason + Resubmit and an "Ask the
  partner a question" action; audit timeline + trace stepper handle the new events/statuses.

**What's next**
- The Frontend / UX backlog in `todo.md`: live progress + streamed thinking for slow real-model
  runs, hide the plan-approval button when there is no proposed plan, and split case creation from
  plan generation.
- Cockpit depth: keyboard-navigable queue and a side-by-side source diff for deviation flags.

---

## Production stance — building the real product now

**Where we are.** This is no longer framed as a hackathon demo: it is the **production build**.
The stack runs against real Anthropic Claude on SQLite, Dockerized, with async dispatch. PR #2 is
retitled and rewritten as the production build, and `architecture.md` has been swept to a production
stance (offline mock mode is now the keyless *fallback*, not the default story).

**Done**
- Reframed `architecture.md` from "working web demo / on a slide / out of build scope / no infra
  deliberately" to a production posture: real Anthropic on SQLite is the run, Docker is in, Celery/
  Redis is the named scale-up path, real auth is the next step (not a slide).

**Done (production scale-up)**
- **PPTX ingestion** — `.pptx` now accepted at document upload. `_extract_pptx` (`python-pptx`,
  lazy-imported) walks each slide's text-frame shapes; joins slide blocks with `\n\n`. Same
  extractor path and error handling as PDF/DOCX/text: image-only/empty decks raise `ValueError`
  → HTTP 415, like scanned PDFs. Speaker notes excluded (on-slide visible text only). Frontend
  `accept` list updated; new offline `test_documents.py` covers happy path + empty-deck 415.

**Planned next (production scale-up — see `todo.md`)**
- **Celery + Redis** — replace the in-process background thread pool (`core/background.py`) with
  durable, retryable, horizontally-scalable Celery workers for the agentic worker→checker→ranker
  flows. The `coordinator` boundary stays; only the dispatch mechanism changes.
- **Perplexity web search** — give AI agents live web retrieval behind a tool/provider seam to
  improve citation-support retrieval; every fetched source recorded with its URL, still a claim and
  never a verdict.

---

## Real mode + bulk document upload + partner-chosen severity

**Where we are.** Committed to the real Anthropic provider and added case document upload. The stack
runs against Claude on SQLite, end to end.

**Decisions locked**
- **Real, not mock, from here on.** `.env` sets `PROVIDER_MODE=real` and `ENV=production`, so a
  missing key now fails loudly at boot (`config.py` validator). The mock-safe default stays in
  `config.py`, and `conftest.py` still forces mock, so the test suite runs offline with no key.
- **SQLite is the production store too — no Supabase/Postgres.** The earlier "Phase 1: swap
  `SqliteRepo` → Postgres" plan is dropped. SQLite (one file) is what we run for real; the repo seam
  stays, but we are not migrating off it.
- **Severity is the partner's up-front choice at case creation** (`low | medium | high | extreme`,
  with `extreme` newly added) — a dropdown, not derived from the process doc and never
  model-inferred. It defaults every task in the plan; the partner can still override per task.

**Built**
- Bulk document upload at case creation: `POST/GET /api/cases/{id}/documents` (PDF via `pypdf`,
  DOCX via `python-docx`, text decoded UTF-8; multipart via `python-multipart`). Uploads become
  `case_id`-tagged `draft` corpus docs; the planner prefers a case's uploads and falls back to the
  seeded demo drafts. Best-effort text extraction only — no OCR for scanned PDFs (rejected as 415).
- Planner severity/assignee/ordering enrichment moved provider → service (`services/planner.py`), so
  mock and real are symmetric and real mode no longer `KeyError`s on `severity`. Providers now
  return raw task scoping only. Added defensive `target_document_id` validation.
- `extreme` severity wired through ranker weights (1.0), the severity types (backend + frontend),
  and the badge. Auto-clear still only triggers on `low`, so `extreme` never auto-clears.
- Frontend: severity dropdown + multi-file upload on the create form, multipart-aware `apiClient`,
  `uploadCaseDocuments` wrapper, create → upload → plan flow.
- **Async dispatch (real-mode latency fix).** Approving a plan used to run every task's
  worker→checker→ranker pipeline synchronously inside the request — minutes of real model calls, so
  the approve request effectively hung (a 6-task plan processed ~4 tasks in 10 min). Dispatch now
  runs on a background thread pool (`core/background.py`, `ASYNC_DISPATCH`, `DISPATCH_WORKERS=4`):
  approve returns immediately and the cockpit polls (every 3s) to surface tasks as each finishes.
  The audit chain write is now lock-guarded so concurrent workers can't fork it; tests run inline
  (`ASYNC_DISPATCH=false`) for deterministic assertions. Pipeline failures fail safe → escalate to a
  human, recorded in the audit log.
- Docker: `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` (real `.env` mounted
  read-only; SQLite on a named volume).

**What's next**
- Tune the real `plan_case` / `review_document` prompts for quality; raise `max_tokens` for large
  documents (currently 2048 — may truncate).
- Replace stub auth with real SSO/JWKS before any non-demo use.

---

## Scaffold stood up — initial build

**Where we are.** Full spine scaffolded against the brief, runnable offline in mock mode.

**Built**
- Docs-first: `architecture.md` (spine), this log, `todo.md`, `marketing.md`, `CLAUDE.md`, `README.md`.
- Backend (FastAPI, Python 3.12, `uv`): typed config (mock-safe), `Repo` ABC + `SqliteRepo` +
  `InMemoryRepo`, hash-chained append-only audit, Pydantic schemas.
- LLM provider behind a factory: `LLMProvider` interface, `MockLLMProvider` (replays fixtures,
  honours planted defects, controlled multi-run divergence), real Anthropic impl wired (lazy).
- Corpus + fixtures: EU Cellar-modelled docs, synthetic firm standard, process doc with severity
  labels, planted defects (≥2 non-supporting citations, ≥2 template deviations) + recorded ground truth.
- Supervision depth: worker review service, the three checker signals (citation support / precedent
  deviation / multi-run disagreement), ranker with auto-clear lane + random sampling.
- Breadth: planner (goal → proposed tasks), coordinator state machine, associate inbox + registry,
  templated debrief.
- Frontend (Next.js App Router + Tailwind): cases, plan approval, cockpit (queue + flag panel +
  one-click sources + approve/amend/reject), audit view, associate inbox, debrief.
- No-network tests: `conftest.py` (InMemoryRepo + mock mode) + coverage of worker, each signal,
  ranker lane/sampling, approval gate, decision audit chain, end-to-end happy path.

**Conventions locked**
- Provider-behind-factory; repo pattern; mock-safe centralized config; thin API + logic in services.
- Agents emit checkable claims/flags, never verdicts. Severity up front; uncertainty measured.
- Append-only, hash-chained audit; accountability vs supervision kept separate.

**What's next / first real steps**
- Provision a real Anthropic key, set `PROVIDER_MODE=real`, write/verify the real review prompts.
- Swap the curated corpus for live EU Cellar pulls (stretch goal — keep fixtures as the demo fallback).
- Tune signal weights + `SAMPLE_RATE` against a labelled set.
- Replace stub auth with real SSO/JWKS before any non-demo use.
