# Supervision Cockpit for Human and AI Legal Teams

**Hack the Law (Cambridge) · Clifford Chance track** — *How do we supervise legal AI agents?*

An end-to-end demo that delegates legal work under partner approval, then **supervises** it: it
triages completed AI output by a risk signal, surfaces **checkable flags** (never verdicts), and
records **defensible, signed sign-off** — so a supervising partner stays accountable without
manually reviewing every output.

> Agents surface checkable claims. They never render verdicts. The human decides.

Runs **fully offline** in mock mode (no API key) — the LLM sits behind a provider that replays
fixtures, so the demo never depends on a live model.

## Quick start

```bash
make install        # backend (uv) + frontend (npm) deps
make dev            # FastAPI on :8000 + Next.js on :3000
# then open http://localhost:3000
```

Or run the two halves separately:

```bash
make backend        # cd backend && uv run uvicorn app.main:app --reload   (:8000)
make frontend       # cd frontend && npm run dev                            (:3000)
make test           # backend tests, offline
```

## What's here
- `architecture.md` — the design spine (read this first).
- `current_progress.md` — running build log. `todo.md` — backlog. `marketing.md` — GTM.
- `backend/` — FastAPI + SQLite + the worker/checker/ranker/planner/coordinator/debrief services.
- `frontend/` — Next.js cockpit (queue, flag panel, approve/amend/reject), plan approval, associate
  inbox, audit view, debrief.
- `system-design/` — the original technical brief and diagrams.

## The demo path
Create a case → planner proposes tasks → edit + **approve the plan** (gate) → an AI task runs and one
lands in the associate inbox → cockpit shows the queue sorted by risk → open the top item, see the
failed-citation and template-deviation flags, click through to each source → **approve with an
amendment** (signed) → audit view shows the plan approval + the decision, separate from the flags →
the auto-clear lane shows a randomly sampled item → close the case → debrief generates.

To use a real model: set `ANTHROPIC_API_KEY` and `PROVIDER_MODE=real` in `backend/.env`.
