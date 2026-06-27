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
- [ ] **Give associates a rich-text editor for their submission + document upload.** The associate's
      submission is currently a bare `<textarea>` bound to `summary` (`app/inbox/page.tsx` →
      `submitTask({ summary, findings })`). Upgrade it to a markdown editor in the spirit of a
      GitHub-style comment box — **Write / Preview tabs**, a light formatting toolbar (heading, bold,
      italic, link, code, bulleted/numbered list — buttons insert markdown into the textarea), and
      **attach files** (click / paste / drag-drop) so an associate can upload supporting documents
      with their work. Reuse the existing `Markdown` component (`components/Markdown.tsx`) for the
      Preview tab — `summary` is already markdown elsewhere — so no new rendering path is needed.
      - **Design alignment (important — do NOT copy the reference image's GitHub dark style).** Build
        it in the product's existing light visual language: `Panel`/`Field` containers, the `.input`
        focus ring (`brand` border + `brand-soft` ring), `text-ink`/`text-muted`/`canvas`/`line`
        tokens. Use the **segmented-control pattern already in the codebase** for the Write/Preview
        toggle (same look as the audit filter toggle and the role toggle), and keep the toolbar
        glyphs consistent with existing iconography. It should read as the same app, not a
        transplanted GitHub widget.
      - **Backend seam for attachments (decide before building the upload).** File attachment on a
        submission has no endpoint yet — documents only attach at the case level today
        (`uploadCaseDocuments` → `POST /cases/{id}/documents`). The rich-text editing of `summary` is
        frontend-only, but the upload needs a call: simplest is to reuse the case-documents endpoint
        so the associate's file lands in the case corpus (tagged to the task), rather than adding a
        new submission-attachment table. Record the attachment in the audit/submission record so it's
        traceable. Keep submissions checkable claims that re-enter the flow — never an auto-decision.
- [ ] **Cut redundant hint/helper text that clutters the view.** Several screens carry long muted
      explainer sentences (the `text-[11px]`/`text-xs text-muted` paragraphs) that restate what the
      adjacent control already makes obvious — visual noise for a time-poor partner. Trim them: keep
      a hint only where it carries information the UI can't show on its own; delete the rest, or fold
      it into a one-line label / a hover title. Known offenders to review (not exhaustive — grep the
      `text-muted` explainer spans per file): the severity blurb and the upload + create helper
      paragraphs in `app/page.tsx`; the "Severity is a deliberate policy choice…" sentence in
      `plan/page.tsx`; the explainer lines scattered through `components/ItemDetail.tsx` (the most
      hint-heavy file) and the cockpit lane sub-captions in `app/cases/[id]/cockpit/page.tsx`. Prefer
      progressive disclosure (tooltip / "?" affordance) over an always-on paragraph where the context
      genuinely helps a first-timer.
      - **Guardrail (do NOT strip these):** some muted text is load-bearing, not decoration — the
        one-rule framing that keeps the product honest ("these are points to check, not verdicts",
        "nothing is dispatched until you approve", the debrief honesty footer, the "uncertainty is
        measured, not self-reported" notes). Those stay. Remove redundancy and decoration, never the
        checkable-claim/never-a-verdict messaging.
- [ ] **Reshape the case debrief into an issue-centric memo (backend + frontend).** A senior partner
      found the debrief unnatural: it's laid out by the system's data-model entity types — four flat,
      parallel sections **Tasks / Flags raised / Partner decisions / Carry forward** (one per SQLite
      table + a footer) — not the way a lawyer reads a closed matter. The partner thinks *per issue*
      ("the liability cap — what did we find, what did I decide, is it resolved?"), but that single
      issue is **shattered across three sections** (its task in §1, its flag in §2, the decision in
      §3), forcing the reader to mentally re-join the tables. Also: `DecisionCard` references its task
      by a truncated UUID (`task 3f9a2b1c`) while `TaskCard` shows only the title and no ID — so the
      decision→task link is literally unfollowable in the UI. The cockpit already got the
      figure/ground + group-the-exceptions treatment (commit `b79c2ff`); the debrief is the surface
      that didn't. **Do it properly — compose the join server-side, where the objects still have
      their relationships, instead of regex-parsing it back out of flattened markdown.**
      - **Backend — `services/debrief.py` + provider `generate_debrief` (mock + real).** Stop
        emitting three independent lists. Build, per task, an *issue record* that already joins the
        task to its flags (`repo.list(FLAGS, task_id=...)`) and its decision
        (`repo.list(DECISIONS, task_id=...)`). Partition tasks into **needs-attention** (has a flag
        and/or a recorded decision) vs **cleared without flags**. Emit a structured payload the
        frontend can render without guessing — prefer changing `DebriefDoc.content` from a markdown
        blob to a typed JSON shape (e.g. `{ goal, summary_counts, issues[], cleared[], carry_forward[] }`
        where each `issue` = `{ task_title, severity, status, flags[], decision }`), carrying real
        task **titles** (not UUIDs) and keeping each flag's `source_ref` so the partner can still
        reach the source in one click. Update the mock fixture/generator and the real Anthropic
        prompt + structured-output parsing together; add/adjust a backend test for the new shape.
      - **Frontend — `components/DebriefReport.tsx` + `debrief/page.tsx`.** Rebuild around the new
        payload (delete the string-parsing in `parseSections`/`renderCard` and the brittle regexes in
        `TaskCard`/`FlagCard`/`DecisionCard`). Layout, top to bottom: (1) a **synthesis line** in the
        letterhead — `N tasks · N hard flags · N rejected · N to carry forward` (counts, never a
        verdict); (2) **Needs-attention items, ordered worst-first** (severity/hard-flag sort, the
        same ordering the cockpit uses), each as **one composed card** showing task title + severity
        + status, its flag(s) with signal-type chip and a source link, and **your decision** (action
        + note) together — no cross-referencing; (3) **Cleared without flags** collapsed into a
        compact expandable summary showing just the count (progressive disclosure, like the cockpit's
        secondary lanes); (4) **Carry forward** kept prominent as the action list. Keep the printable
        letterhead + honesty footer.
      - **Guardrail (the one rule).** This is recomposition and ordering only — flags stay checkable
        flags, the decision stays the *partner's own recorded* decision, the synthesis is counts.
        Never fuse them into an agent pass/fail. Worst-first ordering is a sort, not a judgment.
      - **Docs:** note the debrief reshape in `frontend/DESIGN.md` (same figure/ground + exceptions-
        over-routine rationale as the cockpit) and log it in `current_progress.md`.
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
- [ ] **Add an explicit task filter to the audit page.** The audit view already filters by task,
      but only implicitly — clicking an entry "follows" its `task_id` (the `task`/`setTask` state +
      `taskTitles`). Add a task selector to the filter bar alongside the "Who" actor dropdown
      (`app/cases/[id]/audit/page.tsx`), so a partner can pick a task directly instead of having to
      find one of its entries first. Reuse the existing `task` state and the `clearFilters` reset.
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
- [x] **Hide the plan-approval button when there is no plan.** "Approve plan" currently renders even
      when the case has no proposed plan. Gate it on a plan existing in `proposed` status (partner
      only). Done: `plan/page.tsx` now treats a 404 as the expected "no plan yet" state (not an
      error) and renders an empty-state panel with a partner-only **Generate plan** button instead of
      the proposal banner + dead Approve button.
- [x] **Split case creation from plan generation.** Creating a case should not also generate the
      plan in the same click. Create the case first, then expose plan generation as a separate,
      explicit action (the home `onCreate` currently chains createCase → uploadCaseDocuments →
      createPlan → route). Done: `onCreate` now creates + uploads, then routes to the case's plan
      page where generation is the explicit next step; the create button no longer plans.

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
