# Technical Brief: Supervision Cockpit for Human and AI Legal Teams

**Hackathon:** Hack the Law (Cambridge), Clifford Chance track
**Problem:** How do we supervise legal AI agents?
**One line:** An end to end system for human and AI legal teams that delegates work under partner approval, then supervises it: it triages completed outputs, surfaces checkable flags, and records defensible sign off, so a supervising partner stays accountable without manually reviewing every output.

---

## 1. Framing

The system delegates work, but the part the Clifford Chance challenge actually asks for, and the part judges will probe, is supervision and accountability. Delegation is the easy half and many teams will build it. A human cannot review every AI output but remains legally responsible for all of it. The trap that most designs fall into is to answer "I cannot trust the worker AI" by adding a checker AI, which only relocates the trust question to a new black box. The judge's first question will be "who watches the watchmen." So we build the delegation spine thin and put our depth into supervision.

Our answer is a single design principle that runs through everything below:

> **Agents surface checkable claims. They never render verdicts. The human decides.**

A component that outputs "score 0.82, pass" asks the partner to trust it. A component that outputs "this clause deviates from your firm's standard indemnity template, and the case it cites does not support the proposition" is useful even when it is wrong, because the human can verify it in seconds. We build the second kind.

---

## 2. Scope

We are building the full system end to end: case intake, AI driven task delegation, execution by human and AI workers, supervision, sign off, and debrief. The guiding rule is **build the whole spine, but keep every component thin.** The supervision layer (cockpit, checker, ranker, audit) is the part that wins this track, so it is built to depth. The delegation and orchestration layer is built to working breadth, not depth.

### 2.1 In scope (what we build and demo)

**Case and delegation**

1. **Case intake.** Partner creates a case, uploads the brief, selects a firm process or standard document, and writes the goal.
2. **Planner agent.** Scopes the goal into discrete tasks, attaches a severity label to each from the process document, and proposes an assignment for each task: human associate, AI agent, or hybrid (human instructed to use AI). The plan is a proposal, never an action.
3. **Plan approval gate.** The partner reviews, edits and approves the plan in the cockpit before any work starts. No task is dispatched without explicit approval.
4. **Coordinator agent.** Dispatches approved tasks to the right worker (human or AI), tracks status, routes escalations to the partner, and handles approved reassignment of redo tasks.
5. **Associate interface.** A task inbox where a human associate sees assigned tasks with their brief, process document and (for hybrid tasks) the AI instruction, and submits work back.

**Supervision (built to depth)**

6. **One task type for the review and checking flow: document review against a firm standard.** Other task types can be planned and assigned, but the deep checker signals are demonstrated on review, where supervision is most checkable.
7. **The partner supervision cockpit.** A queue of completed outputs, sorted by a risk signal, highest first. Clicking an item opens a flag panel showing the checkable signals with the source one click away, plus approve, amend and reject controls that each write a signed record.
8. **The checker as a signal generator,** running three independent, inspectable signals (see 3.1). It emits flags. It does not emit a pass or fail verdict.
9. **The ranker,** which combines the up front severity label with flag density to order the partner's queue, and routes low risk items to an auto clear lane with random sampling.

**Close out**

10. **Debrief agent.** At case close, generates a debrief document summarising what was done, what was flagged, what the partner decided, and what carries forward to the next case.

**Cross cutting**

11. **A working audit trail at every step:** plan proposed and approved, sources used, citations checked, flags raised, human submissions, and every human decision.
12. **A small EU Cellar sourced corpus** with planted citation errors and template deviations, so the signals have something real to detect.

### 2.2 Build to breadth vs build to depth

To stop "build everything" from becoming "build everything shallow and nothing well," each component has a target depth set in advance:

| Component | Depth | What that means |
|---|---|---|
| Planner | Breadth | Produces a sensible task list and assignments. Does not need to be optimal. |
| Coordinator | Breadth | Routes and tracks status. Simple state machine, not a real queue system. |
| Associate interface | Breadth | Inbox plus submit. Minimal styling. |
| Worker (review) | Depth | Produces structured output with citations and an audit trail. |
| Checker + ranker | Depth | The three signals, the queue, the sampling lane. This is the centrepiece. |
| Cockpit | Depth | Queue, flag panel with one click sources, approve / amend / reject, audit view. |
| Debrief | Breadth | Templated summary from the case record. |

**Fallback ordering (if time runs short on the day).** Cut from the bottom up in this order: debrief first, then the associate interface (replace with a simulated human submission), then planner depth (hand author one plan). Protect the checker, ranker, cockpit and audit trail to the end. Those four are the answer to the actual challenge.

### 2.3 Explicitly cut

- **Auto scraped capability profiling from LinkedIn or CV.** The planner needs some notion of who is available and what they do, but automatically scraping personal data and making allocation decisions from it runs straight into GDPR Article 22 and employment concerns. Instead we use a **human maintained capability and capacity registry** (associate name, practice area, current load), which the partner or the associate controls. The planner reads from it to propose assignments, and the partner approves. Assignment is suggested, never automated.
- **AI grading of purely human work product.** An AI scoring a qualified lawyer's submission has obvious professional and liability problems. The checker only inspects AI generated output (including the AI portion of a hybrid task).
- **Storing and presenting raw chain of thought as the audit record.** Reasoning traces are often post hoc rationalisation and are not a faithful record of why an output was produced. Presenting them to a court or regulator could be actively misleading. We log decisions and checkable evidence, not model introspection.

### 2.4 Non-negotiable design principles

1. Agents surface checkable claims, never verdicts.
2. **Nothing is ever auto approved.** The risk signal triages the partner's queue. It does not sign work off.
3. **Severity is set up front,** as a policy or human choice in the process document, not inferred by an AI after the fact.
4. **Uncertainty is measured from checkable signals,** never from a model's self reported confidence.
5. **Low risk items that clear without full review are randomly sampled,** like a financial audit. This is what lets us claim scalable supervision honestly rather than quietly moving accountability to a model.
6. Escalation toward a human may be automatic (failing safe). Auto reassignment of flagged work back into the machine without a human seeing it is not permitted.
7. **The plan is a proposal and assignment is suggested.** The planner and coordinator never dispatch work or allocate it to a person without the partner's explicit approval.

---

## 3. High-level system design

Three layers (see architecture diagram).

**Presentation layer.** The partner supervision cockpit (triaged queue, flag panel, approve / amend / reject) and a lighter associate view for hybrid tasks.

**Orchestration layer (AI agents).** Planner, coordinator, worker agents, the checker (three signal generators), the ranker, and the debrief generator. All are built. The planner, coordinator and debrief are built to working breadth; the worker, checker and ranker are built to depth.

**Data and services layer.** Case store, append only audit log, firm standards and process documents, and the EU Cellar API connector. A shared LLM provider sits alongside.

The control flow forms a loop: the partner opens a case, the planner scopes it and proposes assignments, the partner approves the plan, the coordinator dispatches tasks to human or AI workers, workers review documents against the firm standard while pulling sources from EU Cellar, the checker generates flags, the ranker orders them, and the cockpit presents the queue back to the partner for decision. At case close the debrief agent summarises the record.

### 3.0 The delegation model

The planner turns a goal into a set of tasks, each carrying three attributes:

- **Assignee type:** human associate, AI agent, or hybrid. Hybrid means a human is told to use a specific AI step and remains the owner of the result.
- **Severity label:** drawn from the process document, set here at plan time, not inferred later (see 3.1).
- **Inputs:** the slice of the brief, the relevant process document section, and for hybrid tasks the AI instruction.

The plan is rendered in the cockpit as an editable proposal. The partner can change an assignee, split or merge tasks, adjust severity, or reject the plan, then approves. Only on approval does the coordinator dispatch anything.

The coordinator is a simple state machine over each task: proposed, approved, dispatched, in progress, submitted, checked, in review, signed off, or escalated. Human tasks land in the associate inbox; AI tasks trigger a worker agent; hybrid tasks do both. When the checker raises a serious flag, the coordinator routes the task to the partner's queue. It does not silently send work back into the machine; any redo is a decision the partner takes (which can then be reassigned).

This is the part of the system that is most tempting to over engineer. It is deliberately a thin state machine. The intelligence that matters for this track lives in the checker and the cockpit, not in clever routing.

### 3.1 The risk signal, specified concretely

This is the heart of the product, so it is specified rather than left "to be fleshed out." Severity and uncertainty come from different places and must not be fused into one model guess.

**Severity (set up front, owned by humans or policy).**
A label attached to each task when the plan is created, drawn from the process document. For example, verifying a binding obligation is High; summarising a non key recital is Low. Severity is auditable as a deliberate choice, not a model inference.

**Uncertainty (measured after the fact from checkable signals).**
A composite of three independent, inspectable signals:

1. **Citation support rate.** For each claim with a cited source, retrieve the source and test whether it actually supports the claim. A fabricated or non supporting citation is a hard signal, surfaced regardless of severity.
2. **Precedent deviation.** Distance between the output and the firm standard or process scaffold, structural and semantic. High deviation raises the need for attention.
3. **Multi-run disagreement.** Run the review task more than once, or with two models, and measure divergence in the conclusions and flags produced. Disagreement is the single most honest and cheapest uncertainty signal, because it does not rely on anyone introspecting on their own confidence.

The composite is a simple, tunable weighted combination. The point is not the exact formula. The point is that **each signal is independently visible in the UI**, so no single number is load bearing on its own.

**Queue and routing.**
- Priority is a function of severity and measured uncertainty. High severity with high uncertainty is mandatory review and sits at the top.
- Low severity with low uncertainty is auto cleared into an audit lane, logged, and randomly sampled at a configurable rate.
- Hard fail signals (for example a citation to a source that does not exist) are always surfaced.

### 3.2 Two kinds of audit, kept separate

- **Audit for accountability.** A defensible, append only, signed record of who decided what, when, and on what evidence. This is the legal cover.
- **Audit for supervision.** Actionable signal (the flags) that routes a human's attention. This is what makes the partner faster.

Merging the two produces a log that provides legal cover but no supervision, because nobody reads it. We keep them distinct.

### 3.3 Data and the EU Cellar API

The corpus is built from the EU Publications Office Cellar API (EU legislation, case law and related documents). For a reliable stage demo we recommend a small, curated set with **deliberately planted defects**: a handful of citations that do not support their claims, and a few clauses that deviate from a synthetic firm standard. This gives the three signals something real to detect, matches the Hack the Law data steer, and avoids the risk of a live broad query breaking on stage. Treat full live Cellar querying as a stretch goal, not a dependency.

---

## 4. Risks and open questions (kept visible, not hidden)

1. **Calibration of uncertainty.** Even our three signals are imperfect. Multi run disagreement is the most trustworthy; citation checking depends on retrieval quality; deviation depends on a good firm standard. We claim a useful triage signal, not a correct one.
2. **Privilege and confidentiality.** Live matters carry legal professional privilege and conflict concerns. Routing privileged material through multiple agents and retaining intermediate evidence raises waiver and confidentiality risk. The deployment answer (where it runs, what is retained, data residency) belongs on a slide even though it is out of build scope. A Clifford Chance judge will ask early.
3. **The sampling rate is a policy lever, not a constant.** Too low and drift slips through; too high and the efficiency claim weakens. It should be set by the firm per task type.
4. **Standards quality is a dependency.** Precedent deviation is only as good as the firm standard it compares against. Garbage scaffold, garbage signal.
5. **Breadth risk (the big one for this build).** Building the full spine means the surface area is large for a hackathon. The mitigation is the depth table in 2.2 and the fallback ordering: the delegation layer is intentionally thin, and if time runs out it gets cut from the bottom up so the supervision layer always survives. The failure mode to avoid is a polished planner and coordinator wrapped around a shallow checker, because the checker is what the challenge actually asks for.

---

## 5. Goal for an AI agent to execute (build spec)

The following is written as a directive an autonomous coding agent can act on to produce the demo.

**Objective.** Build a working web demo of the full system: case intake, AI task delegation with partner approval, execution by human and AI workers, supervision via the checker and cockpit, signed sign off, and a debrief. Build the whole spine, keep delegation thin, and build the supervision layer to depth.

**Suggested stack.** A single web app (for example Next.js or a Vite React front end with a thin Python or Node backend). Use a small local store (SQLite or flat JSON) for the case store, the task and assignment records, and the append only audit log. Use one LLM provider behind a single service module. Keep everything runnable from one command.

**Build order (milestones).** Build in this order so that the highest value parts exist earliest and the cuttable parts come last.

1. **Corpus and fixtures.** Assemble 5 to 10 documents sourced from the EU Cellar API. Create one synthetic firm standard for the review task and a short process document that defines task types and their severity labels. Plant a known set of defects: at least two non supporting or fabricated citations and at least two clauses that deviate from the standard. Record the ground truth so the demo is repeatable.
2. **Worker review and audit trail (depth).** Implement a worker that reviews a document against the firm standard and emits structured output: findings, the clauses it relies on, and the citations it makes, plus an audit trail of sources used and actions taken. It can call the LLM or replay fixtures; the demo must not depend on a live model being fast or available.
3. **Checker signals (depth).** Implement the three signal generators as separate, inspectable functions: citation support rate, precedent deviation, and multi run disagreement. Each returns structured flags, never a pass or fail verdict.
4. **Severity and ranker (depth).** Read severity from the process document config per task type. Implement the ranker as a tunable function of severity and the composite uncertainty, producing an ordered queue, plus the auto clear lane with a configurable random sampling rate.
5. **Cockpit (depth).** Build the queue view (sorted, highest risk first, severity and top flag per row), the item detail view (each flag with its evidence and a one click link to the source), the approve / amend / reject controls (each writes a signed record), and the read only audit view distinguishing decisions from flags.
6. **Planner and plan approval (breadth).** Implement a planner that turns the case goal into a task list with assignee type, severity and inputs, rendered as an editable proposal in the cockpit. The partner edits and approves. Nothing dispatches before approval.
7. **Coordinator (breadth).** Implement the task state machine: dispatch approved tasks to the right worker, track status, route escalations to the partner's queue, and apply partner approved reassignment. Keep it a simple in process state machine.
8. **Associate interface (breadth).** A task inbox showing assigned tasks with their inputs and, for hybrid tasks, the AI instruction, plus a submit control that returns work into the flow. A human maintained capability and capacity registry feeds the planner's assignment proposals.
9. **Debrief (breadth).** At case close, generate a templated debrief from the case record: tasks done, flags raised, partner decisions, and carry forward notes.

**Acceptance criteria.**
- The partner can create a case, and the planner proposes a task list with per task assignee type and severity that the partner can edit and must approve before anything runs.
- No task is dispatched, and no work is reassigned into the machine, without an explicit partner action recorded in the audit log.
- A human associate can receive a task in the inbox and submit work that re enters the flow; a hybrid task shows the AI instruction.
- The cockpit shows a queue sorted by the risk signal, with at least one high severity high uncertainty item at the top and at least one low risk item in the auto clear lane.
- Every planted defect in the corpus is surfaced as a flag with its source reachable in one click.
- No screen anywhere presents an agent generated pass or fail verdict. The human is always the decider.
- Approving, amending or rejecting an item writes an immutable, timestamped record visible in the audit view.
- The auto clear lane visibly pulls a random sample into the partner's queue.
- The debrief generates from the case record at close.
- The whole flow runs offline from fixtures if the LLM is unavailable.

**Fallback if time runs short.** Cut from the bottom up: debrief, then the associate interface (replace with a simulated human submission), then planner depth (hand author one plan and skip live planning). Never sacrifice the checker, ranker, cockpit or audit trail.

**Demo script (target five to seven minutes).** Create a case and upload the brief, goal and process document. Show the planner's proposed task list, reassign one task and adjust a severity, then approve the plan. Show one task running as AI and one arriving in the associate inbox, and submit the human one. Move to the cockpit, show the queue sorted by risk, open the top item, point to the failed citation flag and the template deviation flag, click through to each source to verify in seconds, then approve with an amendment. Show the audit view recording the plan approval and that decision. Point at the auto clear lane and the sampled item to make the scalability and accountability argument. Close the case and show the generated debrief.
