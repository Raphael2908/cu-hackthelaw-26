# Legal Drafting Copilot

An agentic system that turns a legal task brief (+ optional uploaded documents) into a **synthesised
argument** backed by a ranked, evaluated evidence set.

```
Planner → Coordinator ─┬─ web agent (Perplexity + CELLAR) ─┐
                       └─ doc agent (uploaded documents) ───┴─ reranker → evaluator(top-N) → synthesiser → argument
```

The lawyer sets **N** — how many of the top-ranked documents the evaluator scrutinises before synthesis.

## Quick start

The whole stack boots in **mock mode** with no secrets (canned provider data, in-memory-friendly tests):

```bash
cp .env.example .env          # defaults are mock-safe; no keys needed
make up                       # redis + api + worker + beat + frontend + caddy
# → frontend at http://localhost, API health at http://localhost/api/healthz
```

Backend tests, offline:

```bash
cd backend && uv venv && uv pip install -e ".[dev]" && uv run pytest -q
```

## Commands

`make up | down | build | logs | ps | test | lint | fmt | migrate`

## Docs

- [`architecture.md`](architecture.md) — design source of truth.
- [`current_progress.md`](current_progress.md) — running build log.
- [`todo.md`](todo.md) — product backlog · [`marketing.md`](marketing.md) — GTM.
- [`CLAUDE.md`](CLAUDE.md) — orientation for AI agents working in this repo.

Going to production: provision Supabase + S3, get Anthropic/Perplexity keys, fill `.env`, set
`PROVIDER_MODE=real`, and apply `infra/supabase/migrations/`.
