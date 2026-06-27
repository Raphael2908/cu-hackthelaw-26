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
- [ ] Tune the uncertainty composite weights + `SAMPLE_RATE` against a small labelled set.
- [ ] Cockpit polish: keyboard-navigable queue, side-by-side source diff for deviation flags.
- [ ] Show each of the three signals as its own row in the flag panel (no fused number).

## Next (breadth)
- [ ] Planner: smarter task decomposition from the goal + process doc (currently template-led).
- [ ] Coordinator: surface escalations as their own cockpit lane.
- [ ] Associate inbox: richer task context; show hybrid AI instruction inline with submit.
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
