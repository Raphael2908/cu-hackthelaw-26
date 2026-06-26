# Legal Drafting Copilot — Implementation Progress

> The running build log and the second source of truth (with `architecture.md`). Future sessions read
> this first to learn where the project actually is.

## Where we are

**Scaffold stood up (2026-06-26).** The full stack boots in mock mode with no secrets; backend tests
green offline. The agent pipeline (plan → coordinate → web/doc research → rerank → evaluate top-N →
synthesise) runs end-to-end against **mock** providers — every external vendor (Anthropic LLM,
Perplexity, CELLAR, reranker) is stubbed behind an interface and returns canned, deterministic data. No
real keys, Supabase project, or S3 bucket exist yet.

## What's built

- **Backend core** — `app/config.py` (all keys mock-safe, prod fail-fast), repo pattern (`SupabaseRepo`
  + `InMemoryRepo`) for tasks/documents/candidates/agent_runs/outputs, JWKS auth, FastAPI factory +
  routers (`health`, `tasks`, `documents`, `uploads`), structured JSON logging + request-id correlation.
- **Providers** — interfaces + factory + mock impls for LLM, Perplexity, CELLAR, reranker. Real impls
  are stubbed (`app/providers/real/`) and raise loudly if a key is missing.
- **Pipeline** — Celery app with per-stage queues (`plan`, `research`, `doc`, `rerank`, `eval`, `synth`),
  agent tasks in `app/tasks/agents.py`, a beat watchdog, signal-based correlation. `services/pipeline.py`
  builds + enqueues the chain.
- **Storage** — presigned S3 PUT/GET in `services/storage.py`; `/uploads/presign` route.
- **Frontend** — Next App Router, Supabase auth, `apiClient`, authed `(app)/tasks` route, landing + login.
- **Infra** — docker-compose (redis/api/worker/beat/frontend/caddy), Caddyfile, redis.conf,
  migration `0001_init`, graceful-deploy script, AWS IAM/lifecycle JSON.

## Verification (2026-06-26)

- `uv run pytest -q` → **8 passed** offline (no network, mock providers, in-memory repo, eager Celery).
  Covers health, task CRUD + auth 404, presign, and the full pipeline end-to-end (status → `complete`,
  output produced, all candidates ranked, exactly N evaluated + flagged for synthesis).
- `uv run ruff check .` → clean.
- All 35 backend modules import cleanly (incl. real-provider stubs, supabase/redis singletons).
- `docker compose config` → valid.
- **Not yet run on this machine** (no Docker host available here): `make up` full-stack boot and the
  frontend `npm run build`. The Dockerfiles + compose are in place; run on a Docker host to confirm.

## Conventions / decisions locked

- **Billing out of scope** for MVP (free) — no Stripe/credit ledger. `agent_runs.cost` still recorded.
- **CELLAR** is the EU legal corpus channel (Publications Office central content + metadata store).
- **`eval_doc_count` (N)** is lawyer-set and is the main cost/latency lever.
- Mock mode is total — every external call is behind a provider/repo, so the stack runs keyless.

## What's next

1. Provision Supabase (run `0001_init.sql`), create the S3 bucket, get Anthropic + Perplexity keys;
   fill `.env`; flip `PROVIDER_MODE=real`.
2. Write the first real provider — recommend the LLM provider (`app/providers/real/llm.py`) so the
   Planner/agents produce real output, then Perplexity, then CELLAR.
3. Implement real document parsing in the doc agent (PDF/DOCX → passages).
4. Build out the frontend evidence/ranking + argument viewer screens.

## Open questions

Mirror `architecture.md` §15. Still open: reranker (deterministic vs Cohere), CELLAR access path,
whether Neo4j graph layer is in scope, document-graph clause-level review, evaluator accept/reject pass,
multi-tenancy.
