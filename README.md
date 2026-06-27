# Supervision Cockpit for Human and AI Legal Teams

**Hack the Law (Cambridge) · Clifford Chance track** — *How do we supervise legal AI agents?*

A system that delegates legal work under partner approval, then **supervises** it: it triages
completed AI output by a risk signal, surfaces **checkable flags** (never verdicts), and records
**defensible, signed sign-off** — so a supervising partner stays accountable without manually
reviewing every output.

> Agents surface checkable claims. They never render verdicts. The human decides.

Runs **fully offline** in mock mode (no API key) — the LLM sits behind a provider that replays
fixtures, so the whole flow works keyless and deterministically (and the test suite never touches the
network).

## Does the supervision signal actually work?

We tested the core claim — *does our measured `uncertainty` predict where the AI's work is bad?* —
against the [Harvey](https://www.harvey.ai/) benchmark of real legal tasks, each graded against a
lawyer-authored pass/fail rubric. For each EU/GDPR task we run the shipped `worker → checker → ranker`
pipeline, grade the output against the rubric with an independent strict judge (`Q = passed / total`),
and correlate our supervision `uncertainty` against that quality (Spearman ρ). A strong **negative** ρ
means higher uncertainty reliably flags lower-quality work — the cockpit sends a partner's attention to
the right place.

| Task | uncertainty | Harvey Q (passed/total) |
|---|---|---|
| review-master-services | 0.750 | 0.658 (27/41) |
| map-eu-ai-act | 0.786 | 0.638 (30/47) |
| summarize-new-gdpr | 0.882 | 0.630 (29/46) |
| compare-privacy-notice | 0.991 | 0.378 (14/37) |
| identify-issues-DPA | 1.000 | 0.167 (7/42) |

**Spearman ρ = −1.000 (perfect), n=5** — every task's uncertainty rank is the exact inverse of its
quality rank, up from **−0.60** before routing each task through the planner. The worst task
(`identify-issues-DPA`, Q=0.167) pegs uncertainty at its ceiling, so the cockpit floats it straight to
the top of the review queue. A perfect match at n=5 is small-sample (p≈0.017); across **9 graded EU
tasks** the planner-driven correlation is **ρ = −0.703** (vs −0.32 without the planner) — still clearly
stronger. Worker model `claude-sonnet-4-6`; full methodology and caveats in
[`final_harvey_benchmark_results.md`](final_harvey_benchmark_results.md).

## Architecture
Three layers — presentation, orchestration (the AI agents), and data/services — with depth
concentrated in the supervision spine (worker → checker → ranker → cockpit → audit). See
[`architecture.md`](architecture.md) for the full design.

![System architecture](system-design/architecture.png)

The control loop, end to end — every transition writes to the append-only, hash-chained audit log:

![Happy path](system-design/happy_path.png)

## What it does

**Plan — delegate under approval, and shape the delegation.** The partner opens a case (severity set
up front, optional free-text instructions to steer the planner, optional document upload). The
planner **proposes** tasks decomposed from the firm's process document, each with an assignee type
(human / AI / hybrid), a one-line **rationale** the partner can verify, and — for hybrid tasks — an
explicit *"AI does / associate does"* split. The plan is a **working surface**, not a one-shot: edit
any field, **add / remove / reorder** tasks, pick **which associate** owns each one, or give the
planner natural-language direction and have it **re-propose** (the iterative revise loop). **Nothing
dispatches until the partner approves.**

**Supervise — the centrepiece.** On approval the coordinator dispatches: AI/hybrid tasks run the
worker → checker → ranker pipeline off the request path (Celery + Redis; inline in mock/test mode),
human/hybrid work lands in the associate inbox. The cockpit triages the queue by risk, built from
**three independent, individually-inspectable uncertainty signals** — citation support, precedent
deviation, multi-run disagreement — shown separately and **never fused into one verdict**; severity
stays the partner's up-front call. Every flag is **checkable**: one-click source verification shows
**both** the quoting passage in the submitted work *and* the quoted passage in the source, so the
partner checks *claimed vs actual* directly (or sees plainly that a fabricated citation has no
source). Cited EU law can resolve **live against the official EU Cellar API** (opt-in). The partner
**approves / amends / rejects** (signed), **reassigns** or escalates — escalations get their own lane
— and the **auto-clear lane** logs low-risk work and **randomly samples** it back into the queue,
like a financial audit. Nothing is ever auto-approved.

**Partner ⇄ associate loop.** Tasks carry a conversation thread (the associate raises a question *or*
a concern); every human free-text box uses a shared markdown editor; associates **attach supporting
documents** to their work, reachable by the partner in one click.

**Close — accountable.** Closing is **gated on every task being resolved** (a debrief drawn from an
in-flight matter would misrepresent it). The debrief reads as an **issue-centric memo**: each
needs-attention task joins its flags **and** the partner's decision in one entry, ordered worst-first,
with a synthesis line and carry-forward notes. Throughout, the audit keeps two streams — **decisions
(accountability)** separate from **flags (supervision)** — hash-chained so tampering is detectable.

## Screenshots
A walk through the path, partner first.

**Cases — delegate under approval.** Create a case, set severity up front, attach documents. Nothing
is dispatched until you approve a plan.

![Cases](docs/screenshots/01-home.png)

**Plan — the approval gate.** The planner *proposes* tasks with assignee type and severity; the
partner edits and approves. Only on approval does the coordinator dispatch anything.

![Plan approval](docs/screenshots/02-plan.png)

**Cockpit — the supervision centrepiece.** The queue is triaged by risk. The flag panel shows the
**three independent uncertainty signals** (never fused into one verdict), the worker's submission,
and each checkable flag — with approve / amend / reject controls. Nothing is auto-approved.

![Supervision cockpit](docs/screenshots/03-cockpit.png)

**One-click source verification.** Every flag links straight to its cited source — showing both the
passage in the submitted work and the part of the source quoted (or stating plainly that a fabricated
citation has no such source). The agent surfaces a checkable claim; the human verifies it in seconds.

![Source verification](docs/screenshots/04-source.png)

**Audit — accountability vs supervision, kept separate.** A signed, hash-chained record of who
decided what (left) is rendered apart from the actionable flag stream (right). The chain is verified
end to end.

![Audit](docs/screenshots/05-audit.png)

**Debrief & associate inbox.** At close, an issue-centric debrief is composed from the case record.
Human and hybrid tasks land in the associate inbox, with the hybrid AI instruction shown inline.

| Debrief | Associate inbox |
|---|---|
| ![Debrief](docs/screenshots/06-debrief.png) | ![Associate inbox](docs/screenshots/07-inbox.png) |

## Demo video

[![Watch the demo](https://img.youtube.com/vi/8IT96NAoXOo/hqdefault.jpg)](https://youtu.be/8IT96NAoXOo)

## Quick start

Fill in your Anthropic key, then bring the whole stack up with Docker Compose — redis + backend +
worker + frontend, rebuilt fresh so the latest code runs (this is what the `/run-build` skill drives):

```bash
cp .env.example .env             # then set ANTHROPIC_API_KEY + PROVIDER_MODE=real in .env
                                 # (leave it untouched to boot keyless in mock mode)
docker compose up -d --build     # rebuild images + start detached
# wait until `docker compose ps` shows backend "healthy", then open http://localhost:3000
```

- Cockpit / frontend: http://localhost:3000
- API base: http://localhost:8000/api  (health: http://localhost:8000/healthz)
- backend + worker share one SQLite volume and read the root `.env` (mounted read-only).
- Stop: `docker compose down` (keeps the SQLite volume) · full reset: `docker compose down -v`.
- Logs: `docker compose logs -f` (or `… backend` / `worker` / `frontend`).

Mock mode is the default — keyless, offline, deterministic. Real mode needs `ANTHROPIC_API_KEY` +
`PROVIDER_MODE=real`; `CELLAR_ENABLED=true` resolves cited EU law live against the official EU
Cellar API.

### Local dev without Docker (make)

```bash
make install        # backend (uv) + frontend (npm) deps
make dev            # FastAPI on :8000 + Next.js on :3000 — then open http://localhost:3000
# or run the pieces: make backend · make frontend · make worker (Celery, needs Redis)
make test           # 78 backend tests, fully offline   ·   make lint   # ruff
```

For `make`, real-mode keys go in `backend/.env` (the Docker path uses the root `.env`).

## What's here
- `architecture.md` — the design spine (read this first).
- `current_progress.md` — running build log. `todo.md` — backlog + acceptance criteria. `marketing.md` — GTM.
- `backend/` — FastAPI + SQLite + the worker / checker / ranker / planner / coordinator / debrief
  services, the Anthropic + Cellar providers behind factories, and the Celery dispatch worker.
- `frontend/` — Next.js cockpit (queue, flag panel, approve/amend/reject), the editable plan, the
  associate inbox, the audit view, and the debrief.
- `system-design/` — the original technical brief and diagrams.

## The demo path
Create a case (severity + optional planner instructions) → the planner **proposes** tasks; edit them,
reorder, reassign, or tell the planner what to change, then **approve the plan** (the gate) → AI tasks
run and human/hybrid tasks land in the associate inbox → the cockpit shows the queue sorted by risk →
open the top item, see the failed-citation and template-deviation flags, and click a flag to compare
the submitted work against the cited source → **approve with an amendment** (signed) → the audit view
shows the plan approval and the decision, separate from the flags → the auto-clear lane shows a
randomly sampled item → resolve the rest, **close the case** → the issue-centric debrief generates.
