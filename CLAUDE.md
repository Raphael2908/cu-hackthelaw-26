# CLAUDE.md

Legal Drafting Copilot — an agentic system that turns a legal task brief (+ optional uploaded
documents) into a **synthesised argument** backed by a ranked, evaluated evidence set.

## Read these first

1. `architecture.md` — the design source of truth (agent pipeline, data model, API, infra).
2. `current_progress.md` — the running build log: where the project actually is, what's next.

`todo.md` is the product backlog; `marketing.md` is the GTM plan.

## What it does (the agent pipeline)

```
Planner → Coordinator ─┬─ web agent (Perplexity + CELLAR) ─┐
                       └─ doc agent (uploaded documents) ───┴─ reranker → evaluator(top-N) → synthesiser → argument
```

The lawyer sets **N** (`eval_doc_count`) — how many of the top-ranked documents the evaluator scrutinises.

## Commands

```
make up         # docker compose up --build (full stack: redis, api, worker, beat, frontend, caddy)
make down       # stop the stack
make test       # cd backend && uv run pytest -q   (offline, mock providers, in-memory repo)
make lint       # ruff check
make fmt        # ruff format
make logs       # tail compose logs
make migrate    # apply supabase migrations (manual: psql against infra/supabase/migrations)
```

Backend dev loop without Docker:

```
cd backend && uv venv && uv pip install -e ".[dev]" && uv run pytest -q
uv run uvicorn app.main:app --reload
```

## Architecture in brief

- **Thin API, heavy workers.** FastAPI validates/authorizes/enqueues; Celery agents do all long work.
  Postgres (Supabase) is the source of truth for state; Redis is transport + ephemeral.
- **Provider abstraction.** Every vendor (LLM, Perplexity, CELLAR, reranker) sits behind an interface in
  `app/providers/`; `factory.py` returns a **mock** (default) or **real** impl by `PROVIDER_MODE`.
- **Repo pattern.** All data access goes through `app/db/repo.py` (`SupabaseRepo` in prod, `InMemoryRepo`
  in tests). Never touch the Supabase SDK in handlers/tasks.
- **One image, ROLE dispatch.** `entrypoint.sh` switches `api|worker|beat`; compose runs each role.
- **Centralized config.** `app/config.py` — every key has a mock-safe blank default; the whole stack
  boots with no secrets. Production fails loudly if core creds are blank.

## Conventions / gotchas

- **Mock mode is total** — every external call is behind a provider/repo, so `make test` runs offline.
- Backend style: ruff (line length 100, `E/F/I/UP/B`), `from __future__ import annotations`, Python 3.12.
- Frontend: Next App Router; all API calls go through `lib/apiClient.ts`; `NEXT_PUBLIC_*` are build-time.
- Migrations numbered `0001…` in `infra/supabase/migrations/`.
- Billing is **out of scope** for the MVP (free); no Stripe/credit ledger yet.
