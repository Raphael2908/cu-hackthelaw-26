# Frontend design rationale — heuristics + cognitive walkthrough

This document records *why* the cockpit UI looks and behaves the way it does. It is grounded in two
NN/g methods and is meant to be read alongside `../architecture.md` (the product spine).

- **Nielsen's 10 usability heuristics** — <https://www.nngroup.com/articles/ten-usability-heuristics/>
- **Cognitive walkthrough** — <https://www.nngroup.com/articles/cognitive-walkthroughs/>

The product's one rule — *agents surface checkable claims, never verdicts; the human decides* — is
also a usability constraint, not only an ethical one. A verdict ("score 0.82, pass") fails
**H1 visibility** and **H2 match with the real world**: it hides the system state behind a number a
partner cannot act on. Every decision below is in service of making the *checkable thing* visible.

---

## Part A — Design decisions, heuristic by heuristic

### H1 · Visibility of system status
- **Cockpit lanes are labelled with live counts** (`Review queue 3`, `Auto-clear lane 5`) so the
  partner sees, without drilling in, where work sits and how much needs them.
- **The three uncertainty signals are shown individually** (citation / firm-standard / consistency
  checks), never collapsed into one number. Each is **read in plain language** with the measured
  figure kept alongside (e.g. *"Every citation checks out" · 100% of cited sources support the
  claim*), so the state is legible to a non-technical partner without hiding the number. The
  cockpit queue leads with **"High / Medium / Low priority"** and *"2 points to check"* rather than
  raw `priority 71%` / `uncertainty 47%`. None of these readings is a verdict — see H2 below.
- **Audit chain-validity banner** ("Audit chain verified ✓" / tamper warning) makes the integrity
  state of the record continuously visible.
- **Added (walkthrough gap G1):** each **case card carries an at-a-glance status line** — items in
  review, hard flags present, decided — so the partner knows a case needs them *before* opening it.
- **Added (walkthrough gap G2):** a **chain-of-custody timeline** on each task shows where the work
  is in its lifecycle (dispatched → submitted → checked → in review → signed off).

### H2 · Match between system and the real world
- Vocabulary is a partner's, not an engineer's: *Plan, Review queue, Sign off, Amend, Reject,
  Source, Audit trail* — not "records", "rows", "payloads".
- Severity uses the firm's own words (high/medium/low drawn from the process document), not a model
  score.
- **Added:** the audit sub-nav tab is captioned **"who did what, when"** so the partner recognises it
  as *trace my team's work*, which is their real-world goal (see walkthrough G3).

### H3 · User control and freedom
- The plan is an **editable proposal**; nothing dispatches until the partner approves. Assignee and
  severity are overridable inline. Approval is an explicit, separate, partner-only action.
- Decision flow is **two-step** (choose action → confirm) with a **Cancel** that backs out cleanly —
  an "emergency exit" before anything is written.
- The source drawer opens over context and closes without losing the partner's place.

### H4 · Consistency and standards
- One component library (`components/ui.tsx`): `SeverityBadge`, `StatusPill`, `AssigneeTag`,
  `HardSoftChip`, `SignalStat`, `Button`, `Panel`. The same severity always looks the same; the same
  status pill means the same thing on every screen.
- Colour is a consistent code: **red = hard / high / danger**, **amber = attention / soft signal**,
  **emerald = cleared / signed off**, **brand navy = primary action**. Never decorative.

### H5 · Error prevention
- Approve/amend/reject require selecting the action first, then confirming — you cannot fat-finger a
  sign-off. Amend reveals a dedicated amendment field so the partner cannot "amend" with no text.
- Destructive/consequential controls are partner-gated; the associate view disables them with an
  explanation rather than failing on submit.
- "Generate plan" is idempotent and re-runnable; "New case" requires a title before it will submit.

### H6 · Recognition rather than recall
- Persistent case sub-nav (Plan / Cockpit / Audit / Debrief) so the partner never has to remember a
  route. The active tab is highlighted.
- Flags name their **signal type** and carry a **"View source →"** button right there — the partner
  recognises and verifies in place rather than recalling a citation and hunting for it.
- **Added (G2):** the task trace strip means the partner recognises a task's history instead of
  reconstructing it from memory.

### H7 · Flexibility and efficiency of use
- **Deep links as accelerators:** "View this task's full trail in Audit →" jumps straight to the
  audit pre-filtered to that task (`/audit?task=…`). Expert partners trace one item in one click;
  novices can still browse the whole log.
- **Added (G4):** audit **filters by actor and by task** so a partner can isolate one associate's
  work or one task's history — the literal "trace my minion" path — without reading the whole chain.

### H8 · Aesthetic and minimalist design
- Restrained palette, one accent (brand navy), generous whitespace, no chart-junk. Each panel
  answers one question. Numbers are `tabular-nums` so columns of percentages scan cleanly.
- Secondary metadata (hashes, ids, timestamps) is de-emphasised (mono, muted, truncated) so it is
  *available* without competing with the decision.

### H9 · Help users recognise, diagnose, and recover from errors
- Errors are plain language tied to the cause: "Cannot reach the backend. Is it running on :8000?"
  rather than a status code.
- The **hard-flag → source drawer** path is the product's signature recovery affordance: a fabricated
  citation doesn't silently fail — the drawer states "No such source exists in the corpus — citation
  cannot be verified," diagnosing exactly what is wrong and where.
- The tamper banner diagnoses an integrity failure and points at the broken link.

### H10 · Help and documentation
- Every panel has an inline caption explaining *what this is and why it exists* ("Three independent
  checks. None is a pass/fail.", "A random sample is pulled into the queue, like a financial audit.").
  The teaching is embedded at the point of use — the partner never leaves to read a manual.
- This document is the designer-facing companion to that in-product help.

### Gestalt grouping — the cockpit declutter
A senior partner shown the first cockpit found it unreadable: too many lanes competing for
attention and cards carrying six pieces of information each. The rework applies Gestalt grouping to
restore a clear focal point and a followable order — *without hiding any signal* (the one rule and H1
still hold; this is re-grouping and progressive disclosure, never a fused verdict).

- **Figure/ground (queue rail).** "Needs your review" is the one prominent lane; the handled/in-flight
  lanes (Cleared automatically, With a person, You've decided) collapse to a one-line summary with a
  count, so the partner sees they exist but they stay out of the way until expanded.
- **Proximity + similarity (queue).** Review items are grouped under High / Medium / Low priority
  bands, so priority is read from the *grouping* — letting each card drop its own priority pill and
  progress bar. A card is now three things: title · one line of what to check · severity/must-check.
- **Continuity (item review).** The per-item pane is a numbered path with a connecting spine —
  1 who did it & where it stands → 2 what was produced → 3 what to check → 4 your decision — so the
  partner follows produce → check → decide instead of facing six rival panels.
- **Focal point.** Steps 1–3 are visually light; the decision (step 4) is emphasised as the endpoint
  the whole path leads to.
- **Common region (checks).** The three checks (the steer) and the flags (the concrete things to
  verify) merge into one "What to check" region, since they answer the same question together.

### Issue-centric debrief — the same lens at close
The first debrief was laid out by the system's data-model tables — Tasks / Flags raised / Partner
decisions as three parallel lists — so a single issue ("the liability cap") was shattered across
three sections and the reader had to mentally re-join them (and the decision pointed at a task by a
truncated UUID). The reshape applies the cockpit's figure/ground + exceptions-over-routine lens to
the close-of-matter view, *without* fusing anything into a verdict:

- **Compose the join server-side.** The debrief service builds one *issue* per needs-attention task —
  the task + its flags + the partner's own decision, together — so the reader never re-joins tables.
  Stored as a typed payload, not markdown the frontend has to regex back apart.
- **Synthesis first (figure).** A one-line bottom-line in the letterhead (N tasks · N hard flags ·
  N rejected · N to carry forward) — counts, never a judgment.
- **Exceptions over routine.** Needs-attention issues lead, ordered worst-first (the same severity /
  hard-flag sort the cockpit uses); routine *cleared* work collapses to a count (progressive
  disclosure). Carry-forward stays prominent as the action list.
- **Still checkable.** Each flag keeps its `source_ref`/`work_ref`, so the source (and the quoting
  passage) is one click away in the debrief too. The decision stays the partner's own recorded
  decision; the honesty footer stays.

---

## Part B — Cognitive walkthrough: senior partner, traceability task

**Persona.** Margaret, senior partner. Accountable for the work, time-poor, non-technical. Mental
model: *"Show me what my team — human associates and AI agents — did, prove it, and let me sign off
or push back."*

**Task.** Trace a completed piece of delegated work end-to-end: who did it → what was produced →
what was checked → what sources back it → what was decided → prove the record is intact.

For each step the walkthrough asks: **(Q1)** Will she try the right action? **(Q2)** Will she notice
it is available? **(Q3)** Will she link the action to her goal? **(Q4)** Will she see progress?

| # | Step | Q1 | Q2 | Q3 | Q4 | Verdict |
|---|------|----|----|----|----|---------|
| 1 | Find the case that needs her, from the Cases list | ✓ | ✓ | ⚠ | **✗** | **G1** |
| 2 | Open the case and see what is awaiting review | ✓ | ✓ | ✓ | ✓ | pass |
| 3 | Pick the top-priority flagged item | ✓ | ✓ | ✓ | ✓ | pass |
| 4 | See *who* produced it and *what happened to it* | ✓ | ⚠ | ✗ | ✗ | **G2** |
| 5 | Verify a flag against its source | ✓ | ✓ | ✓ | ✓ | pass (signature strength) |
| 6 | Record sign-off / amend / reject | ✓ | ✓ | ✓ | ✓ | pass |
| 7 | Recognise *where* to prove the whole trail | ⚠ | ⚠ | ✗ | – | **G3** |
| 8 | Isolate one associate's / one task's history in the trail | ✗ | ✗ | – | – | **G4** |
| 9 | Confirm the record is tamper-evident | ✓ | ✓ | ✓ | ✓ | pass |

### Gaps found and how each is fixed

**G1 — Cases list gives no status signal (H1, H6).**
Step 1 fails Q4: the card shows title/goal/buttons but nothing about *state*, so Margaret cannot
tell which case needs her without opening each cockpit. → **Fix:** a per-case status line
(`N in review · hard flag · N decided`) rendered on the card, fetched from the cockpit summary.

**G2 — No chain of custody on a task (H1, H6).**
Step 4 fails Q2–Q4: the item detail shows "produced by ai/human" but not *which* associate, nor the
journey the task took. Margaret cannot trace provenance — the core of the task. → **Fix:** a
**chain-of-custody timeline** on each item (assignee identity + lifecycle stepper:
dispatched → submitted → checked → in review → decided).

**G3 — "Audit" is not recognised as "trace my team's work", and reads like a developer log (H2, H6, H8, H10).**
Step 7 fails Q1/Q3: the partner's goal is "trace what my people did"; the tab is labelled "Audit",
an engineer/compliance word, and the page itself surfaced raw event types, hashes, sequence numbers
and payload keys — unreadable for a time-poor, non-technical partner. → **Fix:** (a) caption the
Audit tab **"Trace who did what, when"**; (b) retitle the page **"What happened on this matter"**;
(c) render every event as a **plain-English sentence in one chronological timeline** ("You signed off
on the indemnity review", "The AI worker submitted their work", "Quality check raised a must-check
flag: …"), with a friendly glyph per event; (d) replace the hash/"chain valid" jargon with a plain
trust line — **"Complete and tamper-proof record"** — and move the cryptographic explanation into an
optional *"How do we know?"* disclosure; (e) keep all technical fields (raw type, sequence, hash,
payload) available but collapsed behind a per-entry **"Technical details"** disclosure. The two record
kinds stay distinct (architecture §11) via a per-entry tag — **"Decision record"** (signed legal
trail) vs **"Quality flag"** (attention only, never a verdict) — and a simple Everything / Decisions /
Flags filter, instead of two jargon-headed columns.

**G4 — The trail can't be sliced by actor or task (H7).**
Step 8 fails Q1/Q2 outright: there is no way to isolate one associate's or one task's events — the
literal "trace my minion" path forces reading the entire log. → **Fix:** **actor and task filters**
on the audit view, plus a **deep link** from each item ("View this task's full trail in Audit →")
that pre-filters the trail to that task.

### Result
After the fixes, every step of the traceability task passes Q1–Q4: Margaret can (1) see from the list
which case needs her, (2)–(6) review and decide an item with its full provenance visible, (7) reach
the trail by its real-world name, (8) isolate exactly the associate or task she is tracing, and
(9) confirm the chain is intact — recognising each step and able to perform it without recall.
</content>
