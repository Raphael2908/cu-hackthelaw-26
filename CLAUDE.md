# CLAUDE.md

Supervision Cockpit for Human and AI Legal Teams — Hack the Law (Cambridge), Clifford Chance track.

**Read first:** `architecture.md` (the design spine) and `current_progress.md` (running log).
The product brief is `system-design/technical_brief.md`.

## What this is
A web demo that delegates legal work under partner approval, then supervises completed AI output:
triages it by a risk signal, surfaces **checkable flags (never verdicts)**, and records signed
sign-off. Build the whole spine, keep it thin, put depth in the supervision layer (worker → checker
→ ranker → cockpit → audit).

## The one rule
> Agents surface checkable claims. They never render verdicts. The human decides.
Never add a screen or endpoint that emits an agent-generated pass/fail. Nothing is ever auto-approved.

## Stack
- Backend: FastAPI (Python 3.12, `uv`, Pydantic v2), **SQLite**, Anthropic Claude behind one
  `LLMProvider`. `PROVIDER_MODE=mock` (default) replays fixtures → runs offline, keyless.
- Frontend: Next.js (App Router) + Tailwind. All API calls through `lib/apiClient.ts`.

## Commands
```
make install     # backend deps (uv) + frontend deps (npm)
make backend     # run FastAPI on :8000  (or: cd backend && uv run uvicorn app.main:app --reload)
make frontend    # run Next.js on :3000  (or: cd frontend && npm run dev)
make dev         # both (backend in background + frontend)
make test        # backend pytest, offline
make lint        # ruff
```

## Conventions (don't break these)
- **Provider behind a factory** (`app/providers/`): add capabilities behind the `LLMProvider`
  interface, never in orchestration. Mock impl must stay network-free and deterministic.
- **Repo pattern** (`app/db/repo.py`): all data access via the `Repo`; `SqliteRepo` (prod),
  `InMemoryRepo` (tests). Never import the sqlite SDK in routers/services.
- **Centralized config** (`app/config.py`): every external key has a mock-safe blank default;
  the stack must boot with no secrets.
- **Thin API, logic in services** (`app/services/`): worker, checker, ranker, planner, coordinator,
  debrief. Routers validate/authorize/record.
- **Audit** (`app/core/audit.py`): append-only, hash-chained. Keep `kind=accountability`
  (decisions/approvals) separate from `kind=supervision` (flags).
- **Severity up front** (from the process doc); **uncertainty measured** from the three checker
  signals — never a model's self-reported confidence. Each signal stays individually visible.
- Backend style: ruff (line length 100, `E/F/I/UP/B`), `from __future__ import annotations`, 3.12.

## Tests
`make test` runs offline (no network, no key). Keep every external call behind the provider/repo so
mock mode is total.
