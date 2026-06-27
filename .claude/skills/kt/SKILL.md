---
name: kt
description: Knowledge transfer — load the project's source-of-truth docs (architecture.md, current_progress.md, todo.md) into context before doing a task. Use for "/kt <task>", "knowledge transfer", "get up to speed", "read the project docs first", or any task where you must understand the Supervision Cockpit design before acting.
---

# kt — knowledge transfer

Loads the three source-of-truth docs into context, then carries out the task the
user gave with `/kt <task>`. Run this **first**, before touching code or
answering, so every change respects the architecture and the one rule:

> Agents surface checkable claims. They never render verdicts. The human decides.

## Steps

1. **Read all three docs, in full, in this order** (paths are relative to the
   repo root `/Users/raphael/Develop/cu-hackthelaw-26`):
   - `architecture.md` — the design spine and non-negotiable principles (§14).
   - `current_progress.md` — running build log, newest at the top: what's done,
     what's decided, what's next.
   - `todo.md` — the product backlog and acceptance criteria.

   Read them with the Read tool. Do not skim or rely on memory — these change
   between sessions.

2. **Then execute the task** passed as the argument (`/kt <task>`). If no task
   was given, summarise the current state (where the build is, what's next) and
   ask what to work on.

3. **Hold the guardrails while you work.** From `architecture.md` §14:
   no agent-generated pass/fail verdicts; nothing auto-approved; severity is
   set up front by the partner; uncertainty is measured from the three checker
   signals; low-risk auto-clear items are randomly sampled; escalation to a
   human may be automatic but auto-reassignment into the machine is not.
   Honour the conventions in `CLAUDE.md` (provider behind a factory, repo
   pattern, centralized config, thin API + logic in services, hash-chained
   audit).

## Notes

- This skill is just-in-time context loading; there is no app to launch and no
  driver to run. The Read calls in step 1 are the whole harness.
- If a doc has moved or is missing, say so and read whatever is present rather
  than failing silently.
