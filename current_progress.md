# Current progress

Running build log. Newest at the top. Read `architecture.md` first for the design.

---

## Reassign action wired into the cockpit

**Where we are.** The backend reassign path (`POST /tasks/{id}/reassign` → `coordinator.reassign`,
`task_reassigned` audit event) and the `reassignTask()` / `getAssociates()` API-client helpers
already existed, but nothing called them — a partner couldn't move work between a person and the AI,
or hand it to a different associate. Now wired into the per-item review. It's a delegation action, so
it goes through an explicit partner click and writes to the accountability log (the one rule).

**Built (frontend only)**
- **`components/ItemDetail.tsx`.** A partner-only **"Reassign this work…"** control in the decision
  step (step 4), gated `isPartner && task.status !== "signed_off"` — available for actionable and
  **escalated** tasks (the redo path), hidden once work is accepted. Expands to: a **To** select
  (a person / hybrid / the AI), an **Associate** select loaded lazily from `getAssociates()` on first
  open (name · practice area · current_load/capacity; hidden when target is the AI; an "Unassigned"
  option → `assignee_id: undefined`), and an optional note. Confirm → `reassignTask()` then `load()` +
  `onDecided()`. Opening it collapses any in-progress approve/amend/reject form; all reassign state
  resets on task change.
- **Guardrail copy.** "Move this work to a person or the AI. It re-dispatches under your name and is
  recorded in the audit log — never reassigned automatically." No verdict semantics.
- **Verified.** `tsc --noEmit` + production `next build` clean; `/api/associates` returns the registry
  live (Amara / Ben / Chen).

---

## Whole-plan editing + human_instruction in the inbox (Cluster A, increment 3)

**Where we are.** The plan is now fully editable before approval, and the associate sees their
explicit half of a hybrid task. This finishes Cluster A's plan-as-a-working-surface arc (increment 1
fields + rationale, increment 2 the revise loop, increment 3 here).

**Built**
- **Whole-plan editing (committed).** `Repo.delete()` added to the protocol + in-memory + sqlite
  impls. New `POST /cases/{id}/plan/tasks` (`planner.add_task` → a blank proposed task on the latest
  proposed plan, `task_added` event) and `DELETE /tasks/{id}` (proposed-only, `task_removed` event);
  `order_index` added to `TaskPatch` for reordering. The plan table gained a per-row **Edit** column
  (move ↑/↓ + remove ✕) and an **"+ Add task"** button; reorder swaps `order_index` via two PATCHes.
  `addPlanTask`/`deleteTask` + `order_index` added to the API client. Everything gated on the plan
  being `proposed`; all three actions write to the accountability audit.
- **`human_instruction` in the inbox.** A sky "Your part" block (with the "You" tag) now shows the
  associate's half of a hybrid task in `inbox/page.tsx`, mirroring the AI-instruction block — closing
  the loop from "author the split at planning" to "show it at execution". *(This edit lives in
  `inbox/page.tsx`, which is co-owned with the in-flight shared-markdown-editor work, so it's left
  uncommitted to land with that stream — by design, not an oversight.)*
- **Verified.** New test `test_whole_plan_edit_add_remove_reorder` (add/reorder/remove + audit events
  + approved-plan refusal). 30 backend tests green, ruff clean, frontend tsc clean. Live: add→201,
  reorder→200, delete→204; inbox hybrid task carries its `human_instruction`.

**Cluster A complete.** Remaining cross-cutting follow-ups (not Cluster A): real-provider prompts for
rationale/revise; the free-text instructions-at-case-creation item (initial steer).

---

## Shared markdown editor for all human free-text boxes

**Where we are.** Every human free-text box was a bare `<textarea>` — no formatting, no preview.
Built one shared rich-text editor and wired it into all five authoring spots, so partners and
associates can write legibly (headings, emphasis, lists, links). It's a free-text editor for the
human's own words — never an agent-generated verdict (the one rule holds).

**Built (frontend only)**
- **`components/MarkdownEditor.tsx` (new, shared).** GitHub-style comment box in the product's *light*
  visual language (not the GitHub dark widget): a **Write/Preview** segmented toggle (same look as the
  audit filter + role toggles) and a light formatting toolbar — **H, B, I, link, code, • list, 1.
  list**. Toolbar buttons wrap the selection (bold/italic/code), insert a link with the `url` portion
  pre-selected, or prefix the spanned lines (heading/lists); selection is restored after the parent
  re-renders (`pendingSel` ref + `useEffect` on value). `onMouseDown preventDefault` keeps the
  textarea selection when a toolbar button is pressed. Preview reuses the shared `Markdown`.
- **`components/Markdown.tsx` extended.** Now also renders italic (`*…*`), links (`[text](url)`,
  open-in-new-tab), and **numbered lists** (`1. `, tracked separately from bullets) so Preview is
  faithful to what the toolbar inserts. Additive — existing bold/code/bullets/headings unchanged.
- **Wired into five call-sites, one component.** Associate **submission** + **question/concern** box
  (`app/inbox/page.tsx`); partner **note**, **amendment**, **reply** boxes (`components/ItemDetail.tsx`).
  Saves unchanged (`submitTask` / `postMessage` / `decideTask`). The submission summary read-back now
  renders via `Markdown` (light bg) instead of a plain `<p>`.
- **Verified.** `tsc --noEmit` + production `next build` both clean.

**Deferred.** (1) File attach (click/paste/drag-drop) on the submission — needs the backend seam
(reuse `POST /cases/{id}/documents`, tag to task). (2) Markdown read-back on **dark** backgrounds —
the partner's navy message bubble and the audit note sentence — needs a theme-aware `Markdown`
(colors are hardcoded light); those stay plain for now.

---

## Associate channel: "question" → "question or concern" (relabel)

**Where we are.** The associate→partner channel was framed narrowly as a *question*, which
discouraged an associate from raising a concern/flag before submitting. Relabelled it to a generic
"question or concern" consistently across both sides. **No backend change** — the message `kind`
stays `"question"` semantically (concerns route through the same `postMessage` /
`awaiting_clarification` path), so this is purely UI copy.

**Built (frontend only)**
- **Associate (`app/inbox/page.tsx`).** Button "Ask the partner a question" → "Message the partner";
  heading → "Raise a question or concern…"; placeholder → "Ask a question or raise a concern…"; send
  → "Send to partner"; waiting banner and error copy generalised to "message".
- **Partner (`components/ItemDetail.tsx`).** "Answer the associate's question" → "Reply to the
  associate's question or concern"; button → "Send reply & return to associate"; pill "question
  awaiting your reply" → "message awaiting your reply"; step-4 hint generalised.
- **Cockpit (`app/cases/[id]/cockpit/page.tsx`).** Lane title "Questions from associates" → "Questions
  & concerns from associates"; row chip "Question" → "Message". Filter stays `m.kind === "question"`
  (still catches concerns).
- **Shared maps.** `MessageThread` bubble labels "Question"→"Question or concern", "Answer"→"Reply";
  `ui.tsx` status `awaiting_clarification` "question raised" → "awaiting reply"; audit sentences
  "asked the partner a question"→"raised a question or concern", "answered the associate's
  question"→"replied to the associate".
- **Verified.** Frontend `tsc --noEmit` clean.

**Deferred.** Swapping both boxes to the shared rich-text editor (blocked on the rich-text-editor
backlog item — bare textareas stay until that lands).

---

## Iterative planning — partner critiques, the planner revises (Cluster A, increment 2)

**Where we are.** The plan is now a conversation, not a one-shot proposal: the partner gives
free-text direction and the planner returns a revised PROPOSAL. Still gated — nothing dispatches
until the partner approves (the one rule).

**Built**
- **Provider seam.** `LLMProvider.revise_plan(case, current_tasks, feedback)` returns FULL task
  dicts (so the partner's edits survive). The base class ships a **safe no-op default** (returns the
  current tasks), so the real provider stays valid until its prompt is written. The **mock** override
  applies deterministic, demonstrable keyword transforms: "human-led" → AI tasks become hybrid;
  "automate/use ai" → human tasks become hybrid; "remove/drop" → drops a task; "add/another" →
  appends a partner-requested task. Unmatched feedback re-proposes unchanged.
- **Service + endpoint.** `planner.revise_plan` re-stamps the revised tasks onto a **fresh proposed
  plan** (latest-plan-wins, like regenerate — the repo has no delete), preserving per-task severity/
  assignee/instruction edits, and records a `plan_revised` accountability event carrying the
  feedback. `POST /cases/{id}/plan/revise` (`PlanReviseRequest`); 409 if there's no plan or it's
  already approved.
- **Frontend.** Plan page gains a "Shape the plan" feedback box (`onRevise` → `revisePlan`) that
  re-renders the revised plan and shows a "Revised ×N" marker; gated on `proposed` + partner. Added
  `revisePlan` to `lib/api.ts`.
- **Verified.** New tests `test_revise_plan_respects_feedback_and_stays_proposed` +
  `test_plan_carries_rationale_and_hybrid_split`. **29 backend tests green, ruff clean, frontend tsc
  clean.** Live: `['ai','hybrid','ai','human']` + "make human-led, add a task" → `['hybrid','hybrid',
  'hybrid','human','hybrid']`, status stays `proposed`, audit shows `plan_revised`.

**Next (Cluster A).** Whole-plan add/remove/reorder (endpoints + `order_index` in `TaskPatch`);
surface the `human_instruction` text in the associate inbox; real-provider prompts for
rationale/revise.

---

## Audit entries signpost actor vs. task and read as clickable

**Where we are.** Each audit entry's metadata line was `timestamp · actor · taskTitle` — three
near-identical muted spans split by `·`. A reader couldn't tell *who* did it from *which task* it's
on, and the actor/task were clickable filters that only signalled it on hover. Both fixed; pairs with
the task-filter work above (clicking an entry's task now visibly drives the new Task dropdown).

**Built**
- **Frontend only (`app/cases/[id]/audit/page.tsx`, the `Entry` component).** Metadata line now reads
  `timestamp · by <actor> · on <task>`: muted "by"/"on" signpost words label the two roles. The
  actor/task buttons gained a dotted-underline link affordance (`text-ink-soft` → `hover:text-brand`,
  `decoration-line` → `hover:decoration-brand`) so their clickability is visible at rest, not just on
  hover. Tooltips reworded to "Filter the trail to this person/agent" / "…this task" to match the
  filter-bar vocabulary — clicking still drives the same `setActor`/`setTask` filters.
- **Untouched.** Technical-details disclosure and the decision/flag tag unchanged. No verdict
  semantics — labelling + affordance only.
- **Verified.** Frontend `tsc --noEmit` clean.

---

## Explicit task filter on the audit page

**Where we are.** The audit trail already filtered by task, but only *implicitly*: a partner had to
find an entry for the task and click it to "follow" its `task_id`. There was no way to pick a task
directly. Added an explicit selector so the audit filter bar reads as one consistent vocabulary
(Everything/Decisions/Flags · Who · Task).

**Built**
- **Frontend only (`app/cases/[id]/audit/page.tsx`).** Added a **"Task"** `<select>` to the filter
  bar, styled like the existing "Who" actor dropdown. Options come from a new `tasks` memo derived
  from audit entries that carry a `task_id` (mirroring the `actors` memo) — titled via the existing
  `taskTitles` map with a `task <id>` fallback — so it only offers tasks that actually have events.
  It binds to the existing `task` state (`"all"` ⇄ `null`), composing with the existing filter
  predicate (`e.task_id !== task`), the URL deep-link seed (the cockpit can still pre-select a task),
  and `clearFilters`. Replaced the passive "Following: …" chip.
- **No new plumbing.** Reused `task`/`setTask`, `taskTitles`, the predicate, and the reset — no
  backend, no new API calls, no new state. No verdict semantics touched (a filter affordance only).
- **Layout fix.** The filter bar's outer `flex-wrap` let the Task dropdown drop to its own line on
  narrow screens (Who up top, Task below). Wrapped **Who + Task** in their own default-nowrap flex
  container so they stay paired — they now wrap together as a unit instead of splitting.
- **Verified.** Frontend `tsc --noEmit` clean.

---

## Plan as a working surface + associate-view attribution (Cluster A, increment 1)

**Where we are.** Starting "Cluster A" — making the plan a real working/negotiation surface — with
the associate-view attribution built in parallel (a background subagent on `inbox/page.tsx`, disjoint
files). This increment lands the planner-output enrichments and per-task editing; the natural-language
revise loop and whole-plan add/remove/reorder are the next increments.

**Built**
- **Planner output enriched.** Each task now carries a one-line `rationale` (why this task / assignee
  / severity — for the partner to verify) and, for hybrid tasks, a `human_instruction` (the
  associate's half, alongside the existing `ai_instruction`). Wired through `mock_plan.json`,
  `planner.py` passthrough, and the `base.py` docstring. Storage needs no migration (rows are JSON
  blobs). Real provider returns `None` for the new fields until its prompt is updated (deferred).
- **Plan page editing (`plan/page.tsx`).** New `EditableText` (commit-on-blur, one PATCH per edit)
  and `InstructionField` helpers. On a `proposed` plan the partner now inline-edits title,
  description, `ai_instruction`, and `human_instruction` — hybrid rows show a two-part **"AI does /
  Associate does"** split — on top of the existing assignee/severity selects. The `rationale` shows as
  a quiet read-only "Why" line. `human_instruction` added to `TaskPatch` + the frontend
  `TaskPatchBody`/`Task` types.
- **Associate-view attribution (`inbox/page.tsx`, parallel subagent).** An `OriginTag` chip (violet
  "AI" / sky "You") marks each contribution block; a per-task banner keyed off `assignee_type` states
  the division of labour; the AI first-pass block reinforces "a draft you own and verify, never a
  verdict".
- **Verified.** 27 backend tests green, ruff clean, frontend `tsc` clean. Live: plan API returns
  `rationale` (all tasks) + `human_instruction` (hybrid); `PATCH human_instruction` persists.

**Next (Cluster A).** Iterative planning — partner gives natural-language direction and the planner
revises (`/plan/revise` + provider `revise_plan`); whole-plan add/remove/reorder (endpoints +
`order_index` in `TaskPatch`); surface the `human_instruction` text in the associate inbox.

---

## Gate case close on a fully-resolved record

**Where we are.** Closing a case generated the debrief with no guard, so a partner could produce a
"case summary at close" while work was still in flight — a debrief drawn from an incomplete record
misrepresents the matter. Closing is now gated on every task being resolved (the one rule: nothing
is signed off until the human has actually supervised it).

**Built**
- **Backend (authoritative).** `views.pending_summary()` defines terminal states
  (`signed_off`/`escalated`/`cleared`) and buckets the rest into `awaiting_decision`
  (submitted/checked/in_review), `with_associate` (dispatched/in_progress/returned/
  awaiting_clarification), and `not_run` (proposed/approved). `close_case` (`api/routers/cases.py`)
  now `409`s with a readable breakdown if `total > 0`; the case stays open and no debrief is written.
  The `cockpit` view also exposes a complete `pending` count (across every status, incl. the
  proposed/approved/submitted/checked that no lane shows) as the frontend readiness signal.
- **Frontend.** `debrief/page.tsx` fetches the cockpit, disables Close/Regenerate while
  `pending.total > 0`, shows an amber "Not ready to close" banner with the breakdown, and refreshes
  the count on a `409`. Added `PendingSummary` to `lib/types.ts` + the `Cockpit` type.
- **Tests.** New `test_close_blocked_while_tasks_pending` (409 + no debrief + still open, then succeeds
  once resolved); the happy-path test gained a `_resolve_remaining` drain before close. 27 backend
  tests green, ruff clean, frontend `tsc --noEmit` clean. Verified live: pending `{total:3,...}` →
  `409` with the breakdown → debrief 404 → close succeeds after resolving.

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

**Follow-up — header/lane subtitles removed (partner request).** A second pass stripped the
orientation captions the partner found unnecessary now that the structure speaks for itself:
- `cockpit/page.tsx`: removed the four lane captions entirely (Needs your review, Cleared
  automatically, With a person, You've decided); `SectionHeader`/`CollapsibleLane` now take `caption`
  as optional. Kept only the "Questions from associates" caption.
- `components/CaseSubNav.tsx`: removed the per-tab header hints (Plan/Cockpit/Audit/Debrief now show
  just their labels) and the now-unused `hint` field + its `title`/`aria-label` usages.
- `debrief/page.tsx`: removed the "A summary drawn from the case record…" header subtitle.
Typecheck clean.

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
