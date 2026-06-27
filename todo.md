# TODO — product backlog

Newest first. Build order protects the supervision layer (depth) over delegation (breadth);
cut from the bottom if time runs short.

## Presentation
- [ ] Update the README with demo videos and screenshots.
- [ ] Create the demo video.
- [ ] Create a PNG architecture diagram and add it to the README.

## Frontend / UX
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
- [ ] **PPTX ingestion.** Add `.pptx` to document upload — extract slide text via `python-pptx`,
      alongside the existing PDF/DOCX/text extractors in `services/documents.py`. Same path: each
      becomes a `case_id`-tagged `draft` corpus document the planner scopes over.
- [ ] **Celery + Redis dispatch.** Replace the in-process background thread pool
      (`core/background.py`) with Celery workers backed by Redis to run the agentic
      worker→checker→ranker flows — durable, retryable, horizontally scalable, surviving restarts.
      The `coordinator` service boundary stays; only the dispatch mechanism changes (architecture §8).
- [ ] **Perplexity web search.** Give AI agents web-search via Perplexity, behind a tool/provider
      seam, so workers can retrieve live external sources when checking citations and gathering
      context — improving citation-support retrieval quality (§13.1). Keep it checkable: every fetched
      source is recorded with its URL for one-click verification, and remains a claim, never a verdict.

## Real integrations
- [x] Run on real Anthropic (`PROVIDER_MODE=real`, `ENV=production`); SQLite stays the store.
- [ ] Tune the real review/plan prompts; verify structured output parsing; raise `max_tokens`.
- [ ] Live EU Cellar API connector (keep fixtures as the offline fallback).
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
