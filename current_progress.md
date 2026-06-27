# Current progress

Running build log. Newest at the top. Read `architecture.md` first for the design.

---

## EU Cellar — official API (not scraping) + worker grounding via tool-use

**Where we are.** Two follow-ups to the Cellar connector, on the same branch/PR. (1) The connector
now uses the **official CELLAR API** instead of scraping rendered HTML. (2) The **worker** can ground
its citations against real Cellar sources while drafting (Anthropic tool-use) — it's no longer only
the checker that touches Cellar. Both opt-in (`CELLAR_ENABLED`), default off, suite stays offline.

**Built**
- **Official API, not scraping (`providers/cellar.py`).** `HttpCellarConnector` now negotiates
  `application/xhtml+xml` (Formex XML for pre-2014 docs) and parses the result with a
  namespace-agnostic `xml.etree.ElementTree` walk that handles **both** XHTML and Formex; the old
  regex strip survives only as a defensive fallback when the payload isn't well-formed XML. Title +
  resource-type come from a best-effort **SPARQL** query (`/webapi/rdf/sparql`, CDM ontology); `kind`
  still derives from the CELEX sector as the reliable default and SPARQL only refines it. A proper
  `User-Agent` is sent. New config: `CELLAR_SPARQL_PATH`, `CELLAR_USER_AGENT`. The tri-state contract
  (found / absent / raise) and the §14.1 hard-vs-soft flag logic are unchanged.
- **Worker grounding via tool-use.** Added an optional `source_lookup` callable to
  `LLMProvider.review_document` (a plain `Callable`, so `base.py` gains no import and there's no
  provider→cellar cycle). The real Anthropic provider runs a bounded **tool-use loop** exposing a
  `fetch_eu_source` tool; the mock ignores it (offline, deterministic). `worker.run_review` builds a
  corpus-first, cache-on-hit `source_lookup` (repo access stays in the service) and passes it **only
  when `CELLAR_ENABLED`**, so mock/offline is unchanged and tool-free. The coordinator is untouched —
  worker and checker both resolve `get_cellar()` by default. The checker's multi-run review calls
  stay un-grounded to bound tool-call cost.
- Tests stay offline: `test_cellar.py` now drives `HttpCellarConnector` with a path-routing
  `MockTransport` (content vs SPARQL) — XHTML parse, Formex parse, malformed→regex fallback, SPARQL
  title precedence + type→kind refinement, English-language filter, junk-filename-title discard,
  SPARQL failure swallowed, status mapping — plus worker tests (source_lookup caches into the corpus;
  the tool is offered only when enabled). `make test` green (41), `make lint` clean.

**Verified against the LIVE EU Cellar API** (real `curl`s + the actual connector, not mocks):
- Content negotiation `GET /resource/celex/{CELEX}` with `Accept: application/xhtml+xml` returns a
  **303 → 200** to the cellar manifestation (`follow_redirects` handles it). Both modern
  (`32016R0679`, 351 KB) and **pre-2014** (`31990L0314`) docs come back as **XHTML** — the Pub Office
  converts old Formex via CONVEX — so one `ElementTree` walk parses everything; the DOCTYPE is
  harmless. A bogus CELEX (`99999X9999`) → `None` (absence), so fabrication detection holds.
- `62018CJ0311` (Schrems II) correctly resolves as **`case_law`** with the right English title.
- Two fixes the live test surfaced, now in: (1) the XHTML `<title>` is the internal OJ **filename**
  (`L_2016119EN.01000101.xml`), not a title → discarded via `_human_title`, real title comes from
  SPARQL; (2) the SPARQL title must be **filtered by language** — without it `LIMIT 1` returned
  *Croatian* for an English request → added an ISO-639-1 → Pub-Office language-authority map and an
  `expression_uses_language` filter. Both public endpoints; **no auth** needed.

**What's next**
- Still open: tune the `plan_case`/`review_document` prompts + harden structured-output parsing
  (`max_tokens` already raised). Perplexity web search; real SSO/JWKS auth.

---

## Live EU Cellar connector — citation signal can resolve real EU law

**Where we are.** The citation-support signal (architecture.md §7.1) is no longer limited to the
seeded fixtures. With `CELLAR_ENABLED` on, a cited CELEX that isn't in the corpus is fetched live
from the EU Publications Office, cached, and checked against the real source. Default is **off**, so
the stack and the test suite stay fully offline. Also raised the real-provider `max_tokens`
2048 → 32768 (both call sites) so large documents/plans don't truncate.

**Built**
- `providers/cellar.py` — a `CellarConnector` seam behind a `get_cellar()` factory, mirroring the
  LLM provider: `NullCellarConnector` (the default — always reports absence, keeps the stack
  offline/network-free) and `HttpCellarConnector` (lazy-imports `httpx`, fetches by CELEX via REST
  content negotiation `GET {base}/resource/celex/{CELEX}`, strips HTML → plain text, maps the CELEX
  sector → `legislation`/`case_law`). `get_cellar()` is `@lru_cache`d and returns the Null impl
  unless `CELLAR_ENABLED`.
- `services/checker.py` — `citation_support`/`run_checks` resolve a CELEX from the corpus first,
  then fetch live on a miss and **cache the fetched doc into `CORPUS`** (so it's one-click-openable
  via `GET /api/corpus/{id}`, like any seeded source). The `coordinator` is unchanged — it flows
  through the `get_cellar()` default.
- **The §14.1 guardrail, enforced + tested.** A fetch that *authoritatively* reports no such CELEX
  stays a **hard "fabricated"** flag; a fetch that *fails* (network/outage) is a **soft
  "unverifiable"** flag and the claim is dropped from the support-rate denominator — so an outage
  can never masquerade as a fabricated citation. The connector returns `None` for absence and
  **raises** (`RetryableError`/`ProviderError`) for transient failure to make this distinction
  load-bearing.
- Config + env: four mock-safe `CELLAR_*` settings (`ENABLED=false`, `BASE_URL`, `LANGUAGE`,
  `TIMEOUT`) + `.env.example` section. Architecture §9 documents the opt-in source.
- Tests stay offline: new `test_cellar.py` (10 cases) covers the hit (resolve + cache), absence
  (hard fabricated), and outage (soft unverifiable, excluded from rate) paths via an injected fake,
  plus `HttpCellarConnector` parsing/status handling via `httpx.MockTransport`. `make test` green
  (32, was 19), `make lint` clean. Existing tests unchanged — the Null default keeps them
  network-free.

**What's next**
- Confirm the exact EU Cellar `Accept` header / endpoint with a couple of live `curl`s before
  flipping `CELLAR_ENABLED=true` (the one external unknown; isolated to `HttpCellarConnector`).
- Still open on the real-provider todo: tune the `plan_case`/`review_document` prompts and harden
  structured-output parsing (only the `max_tokens` part of that item is done).
- Perplexity web search; real SSO/JWKS auth before any non-demo use.

---

## Breadth: planner decomposition + cockpit escalations lane

**Where we are.** Two of the four `## Next (breadth)` backlog items are done (branch
`feat/breadth-planner-escalations`, PR #7). Breadth components made solid and sensible — depth
stays in the checker/ranker/cockpit. All §14 guardrails held: no agent verdicts, nothing
auto-approved, severity stays the partner's up-front choice, mock stays deterministic, audit split
untouched.

**Built**
- **Planner now decomposes from the process doc.** The mock planner returned a static 4-task
  fixture regardless of the matter. It now walks the process doc's `task_types` **in document
  order and emits one task per section** — add/remove a section and the plan changes — fully
  deterministic for the offline demo and tests. `mock_plan.json` rekeyed from a flat list to a
  `task_type`→scoping map; new `fixtures.mock_plan_by_type()` (replaces `mock_plan()`); a generic
  deterministic fallback covers any section without scripted scoping. Still **raw scoping only** —
  severity (partner's choice), the process-section label, the default assignee and ordering stay
  in `services/planner.py`, so mock and real stay symmetric and severity is never a model
  inference (§6, §7.1). The real Anthropic `plan_case` prompt was strengthened to decompose per
  process-doc section and bind targets to supplied documents (not offline-verifiable).
- **Escalations get their own cockpit lane.** Escalated tasks — work that fell back to a human via
  a partner reject or a fail-safe pipeline failure — were lumped into the cockpit's "Decided" lane
  next to signed-off work, burying the one thing a partner most needs to act on.
  `services/views.py::cockpit` now returns a dedicated `escalated` lane and narrows `decided` to
  signed-off only (raw dict response, no schema change). The frontend `Cockpit` type gains
  `escalated: Card[]`; the cockpit page renders a distinct rose-styled **Escalations** section
  above the awaiting/decided grid, each row clickable into the detail panel; the "Decided" caption
  now reads "Signed off by the partner."
- Tests: `test_plan_decomposes_one_task_per_process_section` pins the doc-driven contract;
  `test_reject_moves_task_to_escalated_lane` covers the previously-untested reject path and asserts
  the task lands in `escalated`, not `decided`. `make test` green (24), `make lint` clean, frontend
  `tsc --noEmit` clean.

**What's next**
- The remaining two `## Next (breadth)` items: associate-inbox richer context (process-guideline +
  target-document excerpt; the hybrid AI-instruction-inline part already ships) and debrief
  carry-forward notes derived from amended flags.

---

## Presentation assets — README diagrams + screenshots

**Where we are.** The README is now presentation-ready. Done bar the demo video (placeholder in
place).

**Done**
- **Landscape, high-res diagrams.** Regenerated `system-design/architecture.png` (7752×3474) and
  `happy_path.png` (5985×3954) as balanced landscape diagrams via Mermaid → Chrome render, replacing
  the portrait/low-res originals. Corrected the happy-path copy to the locked design (severity is the
  partner's up-front choice, not derived from the process doc). Both embedded in a new README
  **Architecture** section.
- **Screenshots.** Captured seven real screens (mock mode, offline, deterministic) into
  `docs/screenshots/`: cases, plan-approval gate, cockpit (three independent signals + flag panel),
  one-click source verification, the two-stream hash-chained audit, debrief, and associate inbox.
  Driven through the live API + Playwright (system Chrome). Added a README **Screenshots** walkthrough
  and a **Demo video — coming soon** placeholder.

**What's next**
- Record the demo video and embed it under the placeholder.

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
