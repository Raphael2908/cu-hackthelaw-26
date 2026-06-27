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
- [x] **Declutter the partner cockpit with Gestalt grouping.** A senior partner found the cockpit
      unreadable — too many competing sections and overloaded cards. Reduce visual load and make the
      per-item review read as a clear process, without hiding any signal (the one rule holds; see
      `frontend/DESIGN.md`). Two surfaces:
      - **Left rail / queue** (`app/cases/[id]/cockpit/page.tsx`): make **"Needs your review" the one
        focal lane** (figure/ground). **Group its cards under High / Medium / Low headers**
        (proximity + similarity) so priority is shown by grouping — then drop the per-card priority
        pill *and* the redundant progress bar. **Collapse the secondary lanes** (Cleared
        automatically, With a person, You've decided) into compact expandable summaries showing just
        counts (common region). Slim each queue card to three things: title · one-line "what to
        check" · severity/must-check only when present (remove the duplicate attention-phrase line).
        Keep "Questions from associates" as a slim distinct actionable banner.
      - **Right pane / per-item review** (`components/ItemDetail.tsx`): reframe the six equal-weight
        panels as a **numbered review path** with continuity — 1 Who did it & where it is (merge
        header + `TaskTrace`) → 2 What was produced → 3 What to check (**merge "What the checks
        found" + "Points to check"** into one region: the three signals as the steer, the flags as
        the concrete things to verify with source links) → 4 **Your decision** as the visually
        dominant focal endpoint (consider sticky). Lower border/shadow weight on steps 1–3 so they
        read as one flow, not six rival cards.
      - **Docs:** add a short "Gestalt grouping" subsection to `frontend/DESIGN.md`. Guardrail: every
        signal stays individually visible with its number — re-grouping and progressive disclosure
        only, never a fused verdict.
- [ ] **Surface async-dispatch health / stalled tasks in the cockpit.** Dispatch now runs on a
      separate Celery worker over Redis (architecture §8), not the in-process pool. The cockpit only
      polls every 3s and shows an error if the *fetch* fails — it can't tell "still working" from
      "the worker or Redis is down / the task is stuck." Add a frontend signal: detect tasks sitting
      in a pre-review state (dispatched/in_progress/checked) past a threshold and show a "still
      processing… / taking longer than expected" hint, distinct from the AI-pipeline failure that
      already fail-safes to escalation. Pairs with the live-progress item below. Keep it a checkable
      status, never a verdict.
- [ ] **Wire the reassign action into the cockpit.** The backend exposes `POST /tasks/{id}/reassign`
      (and a `task_reassigned` audit event), and `reassignTask()` + `getAssociates()` already exist in
      `lib/api.ts` — but no component calls them, so a partner can't move work between a person and the
      AI, or hand it to a different associate. Add a partner-only reassign control in `ItemDetail` (pick
      assignee type → associate from `getAssociates()` → optional note), routed through the coordinator.
      It's a delegation action, so it must write to the accountability audit log; never auto-dispatch
      without the explicit partner action (the one rule holds).
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
