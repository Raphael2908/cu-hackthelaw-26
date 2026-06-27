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
- [ ] **Let the partner add free-text instructions when creating a case — and feed them to the
      planner (backend + frontend).** The new-case form (`app/page.tsx`) captures the matter's
      structured fields (title, goal, uploaded documents) but gives the partner no place to write
      their own direction for *how* the work should be approached — e.g. "keep all liability review
      human-led", "focus on the data-transfer clauses", "the client is risk-averse on indemnities".
      Add an optional **"Specific instructions for the planner"** free-text field to the create form,
      persist it on the case, and pass it into plan generation so the planner can respect it when it
      proposes tasks/assignees/severity.
      - **Backend.** Add an optional `instructions` (free text) field to the case model; thread it
        through case creation and into the planner — `provider.generate_plan(case, ...)` should
        receive the partner's instructions (mock: deterministic influence/passthrough into the
        fixture; real: include them in the plan prompt). Record the instructions as part of the
        delegation record (accountability audit) — they're the partner authoring the delegation.
      - **Frontend.** Add the field to the new-case form (`app/page.tsx`), reusing the existing
        `Field`/`.input` styling; send it via `createCase`. Pairs with the "new case as a foreground
        modal" item below (same form) and the iterative-planning revise loop (this is the *initial*
        steer; the revise loop is the *follow-up* steer).
      - **Guardrail (the one rule):** this is the human shaping the delegation up front; the planner
        still only proposes and the partner still approves before anything dispatches. The
        instructions never auto-act.
- [ ] **Source verification: show BOTH the quoting passage in the work AND the quoted passage in the
      source (backend + frontend).** The source drawer (`components/SourceDrawer.tsx`) today shows
      only the source side — its "DOCUMENT TEXT" is the cited corpus document's text (the authority /
      firm-standard doc via `getCorpusDoc`), with the cited locator clause highlighted. It does **not**
      show the part of the *submitted work* that quoted/relied on the source. A lawyer we interviewed
      wants both visible side by side: the exact passage in the submitted work that cited this
      source/standard, and the part of the source that was quoted — so the partner can directly check
      "did the work represent the source correctly?" (citation_support) and "how does this clause
      deviate from the standard?" (precedent_deviation). The data exists but isn't wired through: a
      `Flag` carries `submission_id` + `source_ref`, and the submission's `Finding` has `clause_ref`
      (the *work's* clause), `statement` (what the output asserted), and `citation.claim` (what it
      claimed the source says).
      - **Backend.** When the checker raises a flag it has both the submission and the source — have it
        record the quoting passage on the flag (e.g. in `source_ref`/`evidence`): the work clause_ref,
        the output's statement/claimed text, alongside the existing source locator + clause text. So
        the flag self-describes both sides.
      - **Frontend.** Reframe the drawer as a two-part comparison: **"In the submitted work"** (clause
        ref + the exact statement/claim that cited this source) and **"In the source"** (the cited
        locator clause text — already shown). Relabel the bare "Document text" so it's clearly the
        source, not the work. Make it work for both citation_support (source = cited authority) and
        precedent_deviation (source = firm standard).
      - **Note:** overlaps the existing "side-by-side source diff for deviation flags" line
        under *Now (depth)* — fold them together. **One rule:** still just surfacing two checkable
        passages for the human to compare; the system never renders the verdict (keep the footer).
- [x] **Iterative planning — the partner critiques the plan and the planner revises (backend +
      frontend).** Today the planner proposes a plan and the partner can only edit task fields
      (assignee/severity) or regenerate from scratch — there's no way to give natural-language
      direction ("make the liability review human-led", "add a task for the data-transfer clause",
      "drop the recital summary", "split this into two") and have the planner return a *revised* plan
      that respects it. Add a partner-input → re-plan loop so the plan is a conversation, not a
      one-shot proposal. All partner input here is the human authoring the delegation; the planner
      only ever proposes and the partner still approves before anything dispatches (the one rule).
      - **Backend.** A revise endpoint (e.g. `POST /cases/{id}/plan/revise` with the partner's
        feedback) + a provider `revise_plan(case, current_plan, feedback)` that takes the existing
        proposed plan plus the partner's notes and returns a new PROPOSED plan (mock: deterministic
        transform/fixture; real: re-prompt with the current plan + feedback, structured-output
        parsing). Nothing dispatches. Record the revision + the partner's input as an accountability
        event — the partner's direction is part of the delegation record.
      - **Frontend.** On `plan/page.tsx`, a feedback box ("Tell the planner what to change…") that
        submits the partner's views and re-renders the revised proposed plan; keep the per-field edits
        and the approval gate, and show that a revision happened (version / iteration marker).
      - **Guardrail (one rule):** the planner only proposes; the partner's input drives it and the
        partner approves before anything runs. No auto-dispatch from a revision.
      - **Sub-item — structured partner input: propose & edit the AI/associate split for hybrid
        tasks.** A more structured form of the same "partner shapes the plan" loop. A hybrid task
        already carries `ai_instruction` (what the AI does), which the planner sets and `TaskPatch`
        can already edit — but the plan page shows it **read-only** and only lets the partner edit
        assignee type + severity, and there's **no field for what the *associate* does** (the human
        half is implicit). For each hybrid task, propose an explicit split and make both halves
        editable before approval:
        - **Backend.** Add a `human_instruction` (associate's part) field to the Task model alongside
          `ai_instruction`; have the planner propose a default for both on hybrid tasks (mock fixture
          + real prompt/parsing); add `human_instruction` to `TaskPatch` (it's already patchable for
          `ai_instruction`).
        - **Frontend.** In the plan table, hybrid rows show a two-part **"AI does … / Associate does
          …"** suggestion, each inline-editable (same edit-on-`proposed` gating as assignee/severity,
          saved via `patchTask`); make `ai_instruction` editable here too, not just displayed.
        - **Downstream.** Surface `human_instruction` to the associate in the inbox (pairs with the
          "make the AI/associate division of labour explicit" item below).
        - **Partial (split authoring done).** Backend `human_instruction` field (model + planner +
          mock fixture + `TaskPatch`) and the editable two-part "AI does / Associate does" UI on the
          plan page are in. **Remaining:** the natural-language revise loop (parent item), and
          surfacing the `human_instruction` *text* in the associate inbox (the attribution item below
          marks the AI/You split but doesn't yet show the human_instruction wording).
- [x] **Add a short justification to each planner output (for verifiability).** The planner proposes
      tasks (title, assignee type, severity) with no stated reasoning, so the partner can't quickly
      sanity-check *why* — why this is AI vs human, why this severity, why this task exists. Have the
      planner emit a one-line `rationale` per task (and optionally a plan-level summary), surfaced in
      the plan table so the partner can verify the reasoning before approving — and so the iterative
      critique loop above has something concrete to push back on. Backend: add `rationale` to the task
      the planner produces (mock fixture + real prompt/parsing). Frontend: show it per row on
      `plan/page.tsx`, quiet/secondary. **One rule:** the rationale is a checkable explanation to aid
      the partner's judgement, never a verdict or a licence to auto-act — the partner still edits and
      approves.
      - **Done.** Planner now emits a per-task `rationale` (mock fixture + `planner.py` passthrough,
        `base.py` docstring); the plan page shows it as a quiet read-only "Why" line per row. Real
        prompt enhancement deferred (real provider returns `None` until its prompt is updated).
- [ ] **Editable plan at both individual-task and whole-plan granularity.** Plan editing today is
      limited to per-task assignee/severity selects on `plan/page.tsx`. Make the proposed plan fully
      editable before approval at two levels:
      - **Individual task:** edit all of a task's fields inline — title, description, `ai_instruction`
        / `human_instruction`, assignee type/id, severity. (title/description/`ai_instruction` are
        already patchable via `TaskPatch`; just surface them as editable fields.)
      - **Whole plan:** add a task, remove a task, and reorder — needs backend (add/delete-task
        endpoints + `order_index` in `TaskPatch`) — plus the natural-language revise loop above.
      Keep the edit-on-`proposed` gating and the approval gate throughout; nothing dispatches until
      the partner approves.
      - **Partial (individual-task done).** `plan/page.tsx` now inline-edits title, description,
        `ai_instruction`, and `human_instruction` (commit-on-blur via `patchTask`; `human_instruction`
        added to `TaskPatch`), on top of the existing assignee/severity selects, all gated on
        `proposed`. **Remaining:** whole-plan add/remove/reorder (backend endpoints + `order_index`).
- [x] **Make the AI/associate division of labour explicit per task in the associate view.** In the
      inbox (`app/inbox/page.tsx`) a hybrid task already shows several blocks — the "AI instruction"
      (indigo), the "AI first-pass review (you remain the owner)" (violet), the brief slice, and the
      associate's own submission box — but nothing frames *which parts are the AI's work and which are
      the associate's responsibility*. An associate scanning a task can't tell at a glance what was
      machine-produced (a draft to verify) vs what they own and must do. Make the split unmistakable:
      - **Consistent attribution.** Label every contribution block by who produced it — a small "AI"
        vs "You" badge/tag (reuse `AssigneeTag`/the existing chip styling, not new chrome) on the
        AI-first-pass block and the submission block, so the boundary is visual, not just colour.
      - **At-a-glance "who does what"** for the task, keyed off `assignee_type`: for **hybrid**, "AI
        drafted a first pass → you verify, amend, and own the final submission"; for **human**, "this
        is yours — no AI pass" (and the checker doesn't grade human work); for the (rare) AI-surfaced
        context, mark it clearly as machine output.
      - **Reinforce the one rule:** the AI first pass is a *draft of checkable claims the associate
        owns and must verify*, never finished work and never a verdict. Keep "you remain the owner"
        framing prominent. No backend change — this is labelling/attribution in the associate UI.
      - **Done.** `inbox/page.tsx`: an `OriginTag` chip (violet "AI" / sky "You") marks the AI
        instruction, AI first-pass, and submission blocks; a per-task banner keyed off `assignee_type`
        states the division of labour (hybrid vs human); the one-rule "draft you own and verify, never
        a verdict" caption reinforces the first-pass block. (Surfacing the `human_instruction` *text*
        here is tracked under the hybrid-split sub-item above.)
- [ ] **Separate "new case" from the case list with a foreground modal.** On the partner's cases page
      (`app/page.tsx`) the New-case form is a persistent left column (`Panel`, `lg:col-span-1`) always
      competing with the case list (`lg:col-span-2`) — the create form is on screen even when the
      partner just wants to scan existing cases. Replace it with an on-demand foreground:
      - Add a **"New case" button** on the cases page (e.g. top-right of the list header). The list of
        current cases becomes the default, full-width view.
      - Pressing it opens the existing new-case card as a **foreground modal/overlay** (the same form,
        unchanged) over a **dimmed backdrop**, with the case list visible-but-receded behind it.
      - On successful create the modal **dismisses and the list comes back into focus** — with the new
        case now present in it. Build it in the product's visual language (the existing `Panel`/
        `Field`/`.input` styling, `brand` tokens), not a generic modal chrome. Include the basics:
        Esc to close, backdrop-click to dismiss, focus-trap, and restore focus to the "New case"
        button on close.
      - **Resolve the routing interaction:** `onCreate` currently `router.push`es to the new case's
        plan page (the "split case creation from plan generation" flow). That conflicts with "the
        modal closes and the list refocuses". Decide one: either (a) keep routing to the plan page
        (the modal is just the entry point, and the partner lands on plan to generate it), or (b) stay
        on the cases page, close the modal, refresh the list, and let the partner open the new case to
        generate its plan. Pick one and keep the create→plan story coherent; don't do both.
- [x] **Bring the rich-text editor to the partner's view too.** The partner also types into bare
      textareas in `components/ItemDetail.tsx`: the decision **note** (`note`, ~lines 366–376), the
      **amendment** text (`amendment`, ~377–385), and the **reply to the associate** (`reply`,
      ~291–297). Give these the same markdown editor as the associate's submission/concern boxes —
      Write/Preview + light formatting toolbar — so amendments and remarks can be written legibly
      (lists, emphasis, inline references). Reuse the single shared editor component (see the
      rich-text-editor item below) rather than a second implementation; the note/amendment still save
      via `decideTask` and the reply via `postMessage`, unchanged. Render the saved markdown wherever
      these are read back (the audit trail decision notes, the associate's inbox thread) using the
      existing `Markdown` component so authoring and display stay consistent. Guardrail: this is a
      free-text editor for the human's own words — it stays the partner's recorded decision/remark,
      never an agent-generated verdict.
      - **Done (authoring).** All three partner boxes (note, amendment, reply) now use the shared
        `MarkdownEditor`; saves are unchanged (`decideTask` / `postMessage`). **Remaining:** rendering
        the saved markdown in the read-back spots that sit on a **dark** background — the partner's
        navy message bubble in `MessageThread` and the audit note sentence — needs a theme-aware
        `Markdown` (its colors are hardcoded light), so those stay plain for now. The submission
        summary read-back (light bg) is rendered via `Markdown`.
- [ ] **Generalise the associate's "ask the partner a question" box to questions *or* concerns, on
      the rich-text editor.** Today the associate→partner channel is framed narrowly as a *question*
      (`app/inbox/page.tsx`): the button "Ask the partner a question" (~line 238), the box heading
      "Question for the partner — this hands the task to them until they reply." (~246), the
      placeholder "What do you need clarified before you can finish?…" (~252), and "Send question"
      (~257). An associate may also want to **raise a concern / flag something** before submitting, and
      the current wording discourages that. Reword to a generic prompt — e.g. button "Message the
      partner", heading "Raise a question or concern — this hands the task to them until they reply.",
      placeholder "Ask a question or raise a concern…", send "Send to partner". Keep the behaviour
      (still routes through `postMessage`, still hands the task back via `awaiting_clarification`).
      - **Use the rich-text editor here too.** This box should reuse the same markdown editor as the
        submission box (see the rich-text-editor item below) — Write/Preview + light toolbar — not a
        bare textarea, so concerns can be written legibly. Build the editor once and use it in both
        places.
      - **Keep downstream labels consistent.** If the channel is no longer "questions only", reflect it
        on the partner side: the cockpit lane title "Questions from associates"
        (`cockpit/page.tsx:65`) and the `m.kind === "question"` filtering (`cockpit/page.tsx:289`),
        plus the partner reply wording in `ItemDetail.tsx` ("Answer the associate's question"). Decide
        whether `kind` stays `"question"` semantically (just relabelled in the UI) or broadens — don't
        leave the two sides describing the channel differently.
      - **Partial (relabel done).** Decision: `kind` **stays `"question"` semantically** (no backend
        change — concerns route through the same channel/`postMessage`/`awaiting_clarification`); the
        UI is relabelled consistently on both sides. Associate (`inbox/page.tsx`): button "Message the
        partner", heading "Raise a question or concern…", placeholder "Ask a question or raise a
        concern…", send "Send to partner", waiting/error copy. Partner (`ItemDetail.tsx`): "Reply to
        the associate's question or concern", "Send reply & return…", pill "message awaiting your
        reply", step-4 hint. Cockpit lane "Questions & concerns from associates" + the row chip
        "Message" (filter still `kind === "question"`, which catches concerns). Shared maps:
        `MessageThread` bubble "Question or concern" / "Reply"; `ui.tsx` status "awaiting reply"; audit
        sentences "raised a question or concern" / "replied to the associate". `tsc --noEmit` clean.
        **Done:** both boxes now use the shared `MarkdownEditor` (see the rich-text-editor item below).
- [x] **Block debrief generation while tasks are still pending (backend + frontend).** Closing a case
      (`POST /cases/{id}/close`, `backend/app/api/routers/cases.py`) immediately flips it to `closed`
      and generates the debrief with **no guard** — so a partner can produce a "case summary at close"
      while work is still mid-flight. A debrief drawn from an incomplete record is misleading. Gate it
      on every task being resolved.
      - **Define done.** Terminal task states are `signed_off`, `escalated`, `cleared` (see
        `coordinator`). Everything else is **pending**: `proposed`/`approved` (planned but not run),
        `dispatched`/`in_progress`/`returned`/`awaiting_clarification` (an associate hasn't gotten
        back), and `submitted`/`checked`/`in_review` (awaiting the partner's decision).
      - **Backend guard (authoritative).** The close endpoint should reject with `409` if any task is
        in a non-terminal status, returning the count/breakdown of what's outstanding. This is the
        real enforcement — the button being disabled is not enough.
      - **Frontend.** On `debrief/page.tsx`, disable "Close case & generate debrief" while pending
        tasks exist and say why ("N tasks still need a decision / are with an associate — resolve them
        first"), surfacing the outstanding count (reuse the cockpit's queue / awaiting_human /
        needs_reply numbers). Handle the `409` gracefully if the state changed under them.
      - Once closed, the existing flow is unchanged (debrief generates, "Regenerate" stays available).
      - **Done.** Backend: `close_case` (`api/routers/cases.py`) now `409`s with a readable breakdown
        when any task is non-terminal; `views.pending_summary()` defines terminal = `signed_off`/
        `escalated`/`cleared` and buckets the rest (awaiting_decision / with_associate / not_run), and
        the cockpit view exposes a complete `pending` count. Frontend: `debrief/page.tsx` fetches the
        cockpit, disables Close/Regenerate while `pending.total > 0`, shows an amber "Not ready to
        close" banner with the breakdown, and handles the `409`. Tests: `test_close_blocked_while_
        tasks_pending` + updated happy path drain everything before close. 27 backend tests green,
        ruff clean, frontend `tsc` clean.
- [x] **Signpost the actor vs. task on each audit entry, and make both read as clickable.** On the
      audit timeline each entry's metadata line is `timestamp · actor · taskTitle`
      (`app/cases/[id]/audit/page.tsx`, the `Entry` component ~lines 266–280) — three near-identical
      muted spans separated by `·`. Two problems: (1) nothing signposts that one is **WHO** (the
      person/agent who did it) and the other is **WHICH TASK** it's on — a reader can't tell them
      apart without already knowing; (2) both are buttons (actor → filter by `actor`, task → follow
      `task_id`) but only signal interactivity via `hover:text-brand` + a `title` tooltip, so their
      clickability is invisible until hover. Fix both:
      - **Signpost the roles.** Label each: a small leading icon or word — e.g. a person glyph / "by"
        for the actor, a task-or-document glyph / "on" for the task (`by Dana Okafor · on Review DPA
        liability…`). Keep it terse; this is the audit trail, not prose.
      - **Show they're clickable.** Give the two buttons an affordance consistent with the product
        (e.g. underline-on-default or a subtle chip/link treatment with the `brand` hover), not just a
        hover colour shift. The actor filters the trail to that person/agent; the task "follows" it —
        align the styling with the existing filter bar (the "Who" dropdown and the "Following:" chip)
        so it reads as the same filtering vocabulary.
      - Keep the `Technical details` disclosure and the decision/flag tag as-is; this is metadata-line
        only. No verdict semantics involved — purely affordance + labelling.
      - **Done.** The `Entry` metadata line in `audit/page.tsx` now reads `timestamp · by <actor> · on
        <task>`: muted "by"/"on" signpost words label the two roles, and the actor/task buttons carry
        a dotted-underline link affordance (`text-ink-soft` → `hover:text-brand`, `decoration-line` →
        `hover:decoration-brand`) so their clickability shows without hovering. Tooltips reworded to
        "Filter the trail to this person/agent" / "…this task" to match the filter-bar vocabulary
        (clicking still drives the same `setActor`/`setTask` filters). Technical-details disclosure and
        the decision/flag tag untouched. `tsc --noEmit` clean.
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
      - **Partial (editor done; upload deferred).** Built the shared `components/MarkdownEditor.tsx`
        — Write/Preview segmented toggle (same look as the audit/role toggles) + a light formatting
        toolbar (H, B, I, link, code, bulleted/numbered list; buttons wrap/prefix the textarea
        selection and restore it) in the product's light visual language, Preview via the shared
        `Markdown`. Extended `Markdown` to render italic (`*…*`), links (`[t](url)`), and numbered
        lists so Preview is faithful to the toolbar. Wired into the associate **submission** + the
        **question/concern** box (`inbox/page.tsx`) and all three partner boxes (note/amendment/reply,
        `ItemDetail.tsx`) — one editor, five call-sites. The submission summary read-back renders via
        `Markdown`. Production build clean. **Remaining:** file attach (click/paste/drag-drop) — needs
        the backend seam above; dark-bg read-back (message bubbles / audit note) needs theme-aware
        `Markdown`.
- [x] **Cut redundant hint/helper text that clutters the view.** Several screens carry long muted
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
      - **Done:** trimmed the severity/upload/create blurbs in `page.tsx` (kept "nothing is dispatched
        until you approve"), shortened the `plan/page.tsx` severity note (kept "not an AI inference"),
        removed the duplicate "a steer for where to look — you decide" + "each links to its source"
        in `ItemDetail.tsx` (kept the step-3 "none is a verdict" hint and the step-4 decision
        framing), and tightened three cockpit lane captions. All load-bearing one-rule text kept.
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
- [x] **Add an explicit task filter to the audit page.** The audit view already filters by task,
      but only implicitly — clicking an entry "follows" its `task_id` (the `task`/`setTask` state +
      `taskTitles`). Add a task selector to the filter bar alongside the "Who" actor dropdown
      (`app/cases/[id]/audit/page.tsx`), so a partner can pick a task directly instead of having to
      find one of its entries first. Reuse the existing `task` state and the `clearFilters` reset.
      - **Done.** `audit/page.tsx` now has a **"Task"** `<select>` in the filter bar styled like the
        "Who" actor dropdown. Options come from a new `tasks` memo derived from audit entries that
        carry a `task_id` (mirroring the `actors` memo), titled via the existing `taskTitles` map
        with a `task <id>` fallback — so it only offers tasks that have events. It binds to the
        existing `task` state (`"all"` ⇄ `null`), composing with the existing filter predicate, the
        URL deep-link seed, and `clearFilters`. Replaced the passive "Following: …" chip; no backend,
        no new API calls, no new state. `tsc --noEmit` clean.
- [ ] **Wire the reassign action into the cockpit.** The backend exposes `POST /tasks/{id}/reassign`
      (and a `task_reassigned` audit event), and `reassignTask()` + `getAssociates()` already exist in
      `lib/api.ts` — but no component calls them, so a partner can't move work between a person and the
      AI, or hand it to a different associate. Add a partner-only reassign control in `ItemDetail` (pick
      assignee type → associate from `getAssociates()` → optional note), routed through the coordinator.
      It's a delegation action, so it must write to the accountability audit log; never auto-dispatch
      without the explicit partner action (the one rule holds).
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
