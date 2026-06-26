# TODO — product backlog

Newest first. Build order protects the supervision layer (depth) over delegation (breadth);
cut from the bottom if time runs short.

## Now (depth — the centrepiece, protect these)
- [ ] Tune the uncertainty composite weights + `SAMPLE_RATE` against a small labelled set.
- [ ] Cockpit polish: keyboard-navigable queue, side-by-side source diff for deviation flags.
- [ ] Show each of the three signals as its own row in the flag panel (no fused number).

## Next (breadth)
- [ ] Planner: smarter task decomposition from the goal + process doc (currently template-led).
- [ ] Coordinator: surface escalations as their own cockpit lane.
- [ ] Associate inbox: richer task context; show hybrid AI instruction inline with submit.
- [ ] Debrief: include carry-forward notes derived from flags the partner amended.

## Real integrations (post-demo)
- [ ] Real Anthropic review prompts; verify structured output parsing; `PROVIDER_MODE=real`.
- [ ] Live EU Cellar API connector (keep fixtures as the offline demo fallback).
- [ ] Postgres-backed repo; real auth (SSO/JWKS); per-firm process-doc + standard management.

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
