# TODO — product backlog

Newest first. Build order protects the supervision layer (depth) over delegation (breadth);
cut from the bottom if time runs short.

## Bug fixes
- [ ] **Frontend cannot talk to backend in Docker.** Browser/server requests from the Next.js
      container fail because they target `localhost`, which resolves to the frontend container, not
      the backend. Fix: address the backend by its Docker Compose service/container name over the
      shared Docker network (e.g. `http://backend:8000`), wired through the `.env` so the API base
      URL differs between local dev and Compose.

## Presentation
- [x] Update the README with screenshots (full partner-first walkthrough in `docs/screenshots/`).
- [ ] Create the demo video. _(README has a "Demo video — coming soon" placeholder ready for the embed.)_
- [x] Create a PNG architecture diagram and add it to the README (landscape, high-res
      `system-design/architecture.png` + `happy_path.png`, embedded in the README Architecture section).

## Frontend / UX
- [ ] **Cockpit worker-task progress: elapsed timer + streamed thoughts.** In the cockpit,
      while a `worker→checker→ranker` task runs, show (a) a live **elapsed timer** per task and
      (b) **stream the worker model's thinking** into the task view as it's produced. Scope of
      the broader streaming item below, applied to the cockpit's per-task worker runs.
      **Guardrail (architecture §14):** streamed thoughts are transient UX only — never persist
      them as the audit record (decisions + checkable evidence only).
- [ ] **Live progress for slow AI processes.** Real-model runs take tens of seconds, so every AI
      process (plan generation, each worker→checker→ranker task, debrief) needs visible progress:
      (a) an **elapsed timer** while it runs, and (b) **stream the model's thinking live** into the
      UI via the Anthropic streaming API (`stream=True`), surfaced to the frontend (SSE /
      `ReadableStream`). When implementing, pull current docs with Context7
      (`~/.claude/skills/context7-mcp`): Anthropic Messages streaming + extended thinking, and
      Next.js App Router streaming / route handlers. **Guardrail (architecture §14):** streamed
      thoughts are transient UX only — never persist them as the audit record, which stays decisions
      + checkable evidence.
- [ ] **Hide the plan-approval button when there is no plan.** "Approve plan" currently renders even
      when the case has no proposed plan. Gate it on a plan existing in `proposed` status (partner
      only).
- [ ] **Split case creation from plan generation.** Creating a case should not also generate the
      plan in the same click. Create the case first, then expose plan generation as a separate,
      explicit action (the home `onCreate` currently chains createCase → uploadCaseDocuments →
      createPlan → route).

## Now (depth — the centrepiece, protect these)
- [x] **Flexible worker — the planner tasks it via the process map.** The worker is no longer fixed to
      "review a draft against the firm standard." A process-map section carries a worker spec (`kind`
      ∈ review|summarize|extract|draft, `instruction`, `checklist`, `checks`, `requires_standard`); the
      planner copies it onto each task; `services/task_spec.py::build_task_spec` resolves it once and
      calls the single provider entry `run_task`. Every kind still emits the universal `findings` the
      checker reads, with the type-specific product in `payload`. Checks are selected per task and the
      uncertainty composite is **renormalised** over applied signals; a non-applicable signal shows as
      "n/a", never a fabricated 0.0 (architecture.md §6/§7.2). See `current_progress.md`.
- [ ] Tune the uncertainty composite weights + `SAMPLE_RATE` against a small labelled set.
- [ ] Cockpit polish: keyboard-navigable queue, side-by-side source diff for deviation flags.
- [ ] Show each of the three signals as its own row in the flag panel (no fused number).
- [ ] Flexible-worker follow-ups: let the partner edit `worker_instruction`/`checklist` per task
      pre-approval (`TaskPatch`); show the instruction/checklist on the plan page; surface a `draft`
      task's `payload` in the associate inbox; tune the real per-kind prompts.

## Next (breadth)
- [x] **Planner delegation guided by the Trust Matrix.** The `plan_case` system prompt reads each
      task on two task-intrinsic axes — stakes × verifiability — and maps the four quadrants to
      `assignee_type` (Reserve→human, Augment→hybrid, Monitor→ai, Delegate→ai). Stakes is the task's
      own consequence-of-error, never the matter's severity (architecture.md §6). Follow-up: eval the
      prompt on real cases to confirm quadrant placement.
- [x] **Process maps + per-map agentic track record drive delegation.** Delegation (human/ai/hybrid)
      is the planner agent's judgment of task *nature*, never severity. A selectable/optional *process
      map* (a `process_doc` with sections) is the unit of "clean slate": a fresh map → the
      nature-based suggestion stands and the partner decides where to insert AI; a reused map
      accumulates a per-section track record (`services/track_record.py`) that **graduates** a section
      to AI on a clean record or **pulls it back** to a human on an adverse one. New endpoints
      `GET/POST /api/process-maps`, `GET /api/track-record`; each task carries an `assignee_rationale`;
      a `/track-record` page surfaces per-map stats + the completed-task log. See `current_progress.md`.
- [ ] **Use *actual* process maps (document upload).** The current "add process map" is a lightweight
      structured create (title + section labels). Support uploading a real process-map document
      (PDF/DOCX) — reuse `services/documents.py` to extract text, then derive sections/`task_types`
      via an LLM step behind the provider seam, with partner review before the map is used.
- [ ] **Process map is optional.** A case may run with no map (generic decomposition, all clean
      slate); selecting/adding a map is what enables the per-map track record and graduate/pull-back
      delegation. (Implemented as a fallback to the seeded map today; expose a true "no map" path.)
- [x] **Planner: smarter task decomposition from the goal + process doc.** The mock planner now
      walks the process doc's `task_types` in document order and emits one task per section
      (was a static fixture), staying deterministic; the real Anthropic prompt decomposes per
      section. Raw scoping only — severity/label/assignee/ordering stay in the planner service.
      See `current_progress.md`.
- [x] **Coordinator: surface escalations as their own cockpit lane.** `views.cockpit` returns a
      dedicated `escalated` lane (narrowing `decided` to signed-off only); the cockpit renders a
      distinct rose-styled Escalations section. See `current_progress.md`.
- [ ] Associate inbox: richer task context; show hybrid AI instruction inline with submit.
      _(The hybrid AI-instruction-inline part already ships; remaining: process-guideline +
      target-document excerpt in the inbox card.)_
- [ ] Debrief: include carry-forward notes derived from flags the partner amended.

## Production scale-up (next)
- [x] **PPTX ingestion.** Add `.pptx` to document upload — extract slide text via `python-pptx`,
      alongside the existing PDF/DOCX/text extractors in `services/documents.py`. Same path: each
      becomes a `case_id`-tagged `draft` corpus document the planner scopes over.
- [x] **Celery + Redis dispatch.** Replaced the in-process background thread pool with Celery
      workers backed by Redis for the agentic worker→checker→ranker flows — durable, retryable,
      horizontally scalable, surviving restarts. The `coordinator` boundary stayed; only the
      dispatch mechanism changed (architecture §8). Audit-chain integrity made cross-process safe
      (SQLite WAL + BEGIN IMMEDIATE via a new `Repo.insert_chained`). See `current_progress.md`.
- [ ] **Perplexity web search.** Give AI agents web-search via Perplexity, behind a tool/provider
      seam, so workers can retrieve live external sources when checking citations and gathering
      context — improving citation-support retrieval quality (§13.1). Keep it checkable: every fetched
      source is recorded with its URL for one-click verification, and remains a claim, never a verdict.

## Real integrations
- [x] Run on real Anthropic (`PROVIDER_MODE=real`, `ENV=production`); SQLite stays the store.
- [ ] Tune the real review/plan prompts; verify structured output parsing. (`max_tokens` raised
      2048 → 32768 in `providers/real/anthropic_llm.py` — done; prompts + parsing still to do.)
- [x] Live EU Cellar API connector (keep fixtures as the offline fallback). Opt-in `CELLAR_ENABLED`;
      `providers/cellar.py` (Null default + Http impl behind `get_cellar()`); citation-support fetches
      a source by CELEX on a corpus miss and caches it; outage → soft "unverifiable" flag, never a
      false fabrication (architecture §7.1/§9/§14.1). Uses the **official CELLAR API** (REST content
      negotiation for XHTML/Formex + SPARQL metadata), not HTML scraping. The **worker** also grounds
      citations against real Cellar sources while drafting via Anthropic tool-use (`fetch_eu_source`).
      **Verified against the live API** (303→XHTML for modern + pre-2014 docs; case-law detected;
      bogus CELEX → absent; English-language SPARQL title; no auth).
- [ ] Real auth (SSO/JWKS); per-firm process-doc + standard management. (No Postgres/Supabase —
      SQLite is the production store.)

## Acceptance criteria (from brief §5) — keep green
- [ ] Partner creates a case; planner proposes tasks w/ assignee type + severity; partner edits + approves before anything runs.
- [ ] No task dispatched, no work reassigned into the machine, without an explicit partner action in the audit log.
- [ ] Associate receives a task and submits work that re-enters the flow; hybrid task shows the AI instruction.
- [ ] Cockpit queue sorted by risk; ≥1 high-severity/high-uncertainty item at the top; ≥1 low-risk item in the auto-clear lane.
- [ ] Every planted defect surfaces as a flag with its source reachable in one click.
- [ ] No screen presents an agent pass/fail verdict.
- [ ] Approve/amend/reject writes an immutable, timestamped record in the audit view.
- [ ] The auto-clear lane visibly pulls a random sample into the queue.
- [ ] Debrief generates from the case record at close.
- [ ] The whole flow runs offline from fixtures if the LLM is unavailable.

## Explicitly cut (do not build — brief §2.3)
- LinkedIn/CV scraping for capability profiling (GDPR Art. 22) → human-maintained registry instead.
- AI grading of purely human work product.
- Raw chain-of-thought stored/presented as the audit record.
