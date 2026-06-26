# Legal Drafting Copilot — Technical Architecture

> Working title; final product name TBD (see §15). This is the **design source of truth**. Everything
> else (data model, agent pipeline, API, infra) derives from it. It is reconstructed from the whiteboard
> sketch and the settled process description; sensible defaults are flagged in §15.

## 1. Goal & Scope

An agentic system that turns a legal task brief into a **synthesised argument**, backed by a ranked,
evaluated evidence set. A lawyer states a task (the canonical example: *"M&A first draft plan"*) and
optionally uploads source documents. The system plans the work, researches the relevant law (open web +
the EU's CELLAR repository) and reads the uploaded documents, **ranks** all of that material by
relevance, **evaluates** a lawyer-chosen number of the top documents, and finally **synthesises the
argument** from the evaluated evidence.

The product's value: the AI does the research and triage legwork and produces a defensible first draft,
while keeping the lawyer in control of *how much* evidence is scrutinised before synthesis.

### Phasing

- **Phase 1 (MVP):** one task type end-to-end (M&A first-draft plan). Brief (+ optional uploads) in →
  Planner → Coordinator → web + doc agents → reranker → evaluator (top-K, K set by the lawyer) →
  synthesiser → argument out. Single user, no billing.
- **Phase 2:** more task types (NDAs, term sheets, DD memos), document-graph review UI (flag clauses
  "requiring lawyer review"), a learned reranker, multi-user/org workspaces, optional metered billing.

## 2. System Overview

> This diagram is the **scale-up target**. At MVP launch we collapse all roles onto **one box** (§4
> Phase 0) and may run the agent pipeline **inline** (eager Celery) rather than via real workers.

```text
Browser ─► Next.js ─(HTTPS/JWT)─► FastAPI API tier ─enqueue─► Redis ─consume─► Celery workers ─► agents
                                       │ read/write                                  │
                                       ▼                                             ▼
                                 Supabase (Postgres + Auth + RLS)        LLM / Perplexity / CELLAR
                                                                                     │
                                                                                     ▼
                                                                          S3 + CDN (uploads, outputs)
```

### Agent pipeline (the heart of the system)

The settled, **sequential** process:

```text
Planner ──plan.md──► Coordinator ─┬─► web agent  (open web + CELLAR API) ──┐
                                  └─► doc agent  (lawyer-uploaded docs) ────┤
                                                                           ▼
                                                                      Reranker agent
                                                          (rank all documents by relevance)
                                                                           │
                                                                           ▼
                                                                    Evaluator agent
                                                  (evaluate top-N documents; N chosen by the lawyer)
                                                                           │
                                                                           ▼
                                                                   Synthesiser agent
                                                            (synthesise the argument) ──► Output
```

- **○ = agent.** Each agent is an LLM-driven role with a tool set, typed input, and typed output
  persisted to Postgres.
- **Planner** decomposes the brief into an ordered plan (`plan.md`): what to research, which uploads to
  read, what to draft.
- **Coordinator** executes the plan — dispatches the research/read steps to the web and doc agents and
  marshals their outputs into a single candidate pool.
- **Web agent** researches the **open web** (via Perplexity) and the **CELLAR API** — the Publications
  Office of the EU's central content + metadata store (statutes, directives, regulations, case law).
- **Doc agent** reads the **documents uploaded by the lawyer** and extracts relevant passages.
- **Reranker agent** orders the entire candidate pool (web + CELLAR + uploads) in **relative order of
  relevance** to the task.
- **Evaluator agent** evaluates the **top-N documents**, where **N is decided by the lawyer**, scoring
  each for relevance / risk / uncertainty and surfacing what needs checking.
- **Synthesiser agent** composes the final **argument** from the evaluated evidence → Output.

**Design principles**

- API tier is **stateless and thin** — validates, authorizes, enqueues. Never blocks on agent work.
- Workers/agents own all long-running work — LLM calls, web research, CELLAR queries, reranking.
- Postgres is the source of truth for task/run/candidate state; Redis is transport + ephemeral state.
- Every external dependency (LLM, Perplexity, CELLAR, reranker) sits behind a **provider interface**
  with a mock impl, so the whole stack boots and is testable with no API keys.

## 3. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js (App Router) + Tailwind v4 | Task console, evidence/ranking view, argument viewer. |
| API | FastAPI (Python 3.12, Pydantic v2) | thin, async; validate → authorize → enqueue. |
| Async jobs | Celery + Redis | one queue per agent stage (plan, research, doc, rerank, eval, synth). |
| DB / Auth | Supabase (Postgres + GoTrue + RLS) | JWT verified via JWKS; RLS keyed on `user_id`. |
| Object storage | S3 (+ CloudFront later) | uploaded source documents + generated outputs; presigned URLs. |
| Web research | Perplexity API | open-web legal research with citations. |
| EU legal corpus | CELLAR API | Publications Office of the EU central content + metadata store. |
| LLM | Anthropic Claude | all agent reasoning (Planner/Coordinator/web/doc/reranker/eval/synth). |
| Reranker | deterministic scorer *or* Cohere Rerank | ranks the candidate pool by relevance (§15). |
| Payments | — | **out of scope for MVP** (free); add Stripe + credit ledger later if metered. |
| Email | Resend | optional: "argument ready" notification. |
| Containers | Docker | one image, `ROLE=api\|worker\|beat`; compose runs all roles. |

### Model / vendor defaults

The whole stack boots in **mock mode** (`PROVIDER_MODE=mock`) with every key blank. Exact ids live in
`backend/app/config.py`.

| Role / vendor | Config var | Default (prod) | Note |
|---|---|---|---|
| Planner / Coordinator LLM | `LLM_MODEL_PLANNER` | `claude-opus-4-8` | deep reasoning for decomposition & orchestration. |
| Specialist agent LLM | `LLM_MODEL_AGENT` | `claude-sonnet-4-6` | web/doc/rerank/synth — cheaper, higher throughput. |
| Evaluator LLM | `LLM_MODEL_EVAL` | `claude-opus-4-8` | risk/uncertainty judgement wants the strongest model. |
| Anthropic key | `ANTHROPIC_API_KEY` | `""` (mock) | blank → mock returns canned agent outputs. |
| Perplexity | `PERPLEXITY_API_KEY` | `""` (mock) | open-web research. |
| CELLAR | `CELLAR_BASE_URL` | public endpoint | mock returns canned EU legal documents. |
| Reranker | `RERANK_MODE` | `deterministic` | `deterministic` \| `cohere`; see §15. |
| Provider switch | `PROVIDER_MODE` | `mock` | `mock` \| `real`. |

## 4. Infrastructure & Deployment

Phased to match demand. Launch on one cheap box; split into the §2 topology only at the scale trigger.

### Phase 0 — MVP / hackathon (launch)

One instance runs everything via docker-compose (api + worker + beat, or api-only with eager Celery for
the demo). Redis in a local container with AOF persistence. S3 + presigned URLs for documents/outputs.
Supabase free tier.

### Scale-up — trigger: sustained concurrent tasks / first paying teams

API tier behind an ALB in an ASG; worker tier on a separate ASG scaled on queue depth; Redis →
ElastiCache; CloudFront in front of S3; Secrets Manager. The one-image/ROLE design makes this mechanical.

## 5. Data Model (Supabase / Postgres)

Tables (RLS keyed on `user_id = auth.uid()` unless noted):

- **profiles** — mirrors `auth.users`: `id`, `email`, `org`, `plan`, `created_at`. Auto-provisioned by
  an `AFTER INSERT ON auth.users` trigger (`handle_new_user`).
- **tasks** — one legal task/brief: `id`, `user_id`, `task_type` (`ma_first_draft` | …), `title`,
  `brief`, `eval_doc_count` (**N: how many top-ranked docs the lawyer wants evaluated**),
  `status` (`planning|researching|ranking|evaluating|synthesizing|complete|failed`), `plan_md`,
  `created_at`. The top-level resource.
- **documents** — lawyer-uploaded source material: `id`, `task_id`, `user_id`, `filename`, `s3_key`,
  `mime`, `status`, `created_at`.
- **candidates** — the unified evidence pool produced by the web + doc agents: `id`, `task_id`,
  `origin` (`web|cellar|upload`), `title`, `url`, `source_document_id` (for uploads), `snippet`/`text`,
  `agent_run_id`, `rank` (set by reranker), `relevance_score`, `evaluated bool`, `eval_relevance`,
  `eval_risk`, `eval_uncertainty`, `eval_notes`, `use_in_synthesis bool`. The reranker writes `rank`;
  the evaluator fills the `eval_*` fields for the top-N rows; the synthesiser reads `use_in_synthesis`.
- **agent_runs** — one row per agent step (the unit Celery executes): `id`, `task_id`, `agent`
  (`planner|coordinator|web|doc|reranker|evaluator|synthesiser`), `status`
  (`queued|running|succeeded|failed|cancelled`), `provider`, `input jsonb`, `output jsonb`, `tokens`,
  `cost`, `attempts`, `idempotency_key`, timestamps.
- **outputs** — the synthesised argument: `id`, `task_id`, `version`, `content_md`, `s3_key`,
  `created_at`.

Indexes: `tasks(user_id, status)`, `agent_runs(task_id, agent)`,
`candidates(task_id, rank)`, `candidates(task_id, evaluated)`.

## 6. Agent Pipeline (state machine)

Each **task** advances through ordered agent stages; each stage is an **agent_run** row + a Celery task,
chained so one stage's output feeds the next.

```text
task created ─► [plan] ─► [coordinate] ─┬─► [web research] ─┐
                                        └─► [doc read] ─────┴─► [rerank] ─► [evaluate top-N] ─► [synthesize] ─► complete
```

**Stage contracts**

| Stage | Input | Action | Output | Failure |
|---|---|---|---|---|
| **plan** | brief, task_type | Planner LLM decomposes into ordered steps | `plan_md` on `tasks` | retryable |
| **coordinate** | plan_md | Coordinator dispatches research/read agents, marshals results | child agent_runs | retryable |
| **web research** | plan step | query Perplexity (open web) + CELLAR (EU corpus); collect passages | `candidates` (`origin=web\|cellar`) | retryable per-source; partial OK |
| **doc read** | uploaded documents | extract relevant passages from each upload | `candidates` (`origin=upload`) | retryable |
| **rerank** | the full candidate pool | order all candidates by relevance | `candidates.rank` | fatal if 0 candidates |
| **evaluate** | top-N candidates (N = `tasks.eval_doc_count`) | score relevance/risk/uncertainty per doc; mark `use_in_synthesis` | `candidates.eval_*` | retryable |
| **synthesize** | evaluated candidates | Synthesiser composes the argument | `outputs` row | retryable |

**Lawyer-in-the-loop on N.** The evaluator only evaluates the **top-N** ranked documents, where N
(`tasks.eval_doc_count`) is set by the lawyer — trading thoroughness against cost/latency. The reranker
guarantees those N are the most relevant of the whole pool.

**Provider abstraction.** Each external dependency (LLM, Perplexity, CELLAR, reranker) sits behind an
interface; a factory returns a **mock** (default) or **real** impl by `PROVIDER_MODE`. The selected
provider + any external job id is persisted on `agent_runs` for traceability.

**Reranking.** Research + uploads produce many candidates; the reranker orders them so the lawyer-chosen
top-N going into evaluation are the highest-signal. MVP ships a **deterministic** scorer
(lexical/recency/source-authority); a learned reranker (Cohere) is a drop-in via `RERANK_MODE`.

## 7. Async Orchestration (Celery + Redis)

- **Queues:** one per agent stage (`plan`, `research`, `doc`, `rerank`, `eval`, `synth`) so each scales
  and rate-limits independently (e.g. cap concurrent Perplexity/CELLAR calls).
- **Chaining + fan-out:** the Coordinator dispatches web + doc agents in parallel (a Celery group),
  fans in, then chains rerank → evaluate → synthesize. Each task reads its inputs from Postgres by
  `task_id` rather than passing large payloads through the broker.
- **Long LLM/research calls:** submit → store any external id → self-reschedule with backoff to poll,
  so a worker slot isn't blocked for a multi-second/minute call.
- **Reliability:** idempotency key per agent_run; exponential backoff with jitter; retryable vs fatal
  classification; `soft_time_limit` + a beat watchdog that fails runs stuck `running` past SLA.
- **Hackathon shortcut:** Phase 0 may run Celery **eager/inline** (synchronous) for a simpler demo;
  the queue topology above is the production target and the code path is identical.

## 8. Storage & CDN

Private S3 bucket. Presigned PUT for source-document uploads (large bodies skip the API); signed GET for
downloading generated outputs. Lifecycle expiry for intermediate artifacts.

## 9. Auth

Supabase Auth (GoTrue) issues JWTs. FastAPI verifies the access token against the project JWKS
(asymmetric keys, no shared secret); `sub` → `user_id`. Direct client reads (task lists, candidates)
guarded by RLS; all writes that spawn agent runs go through the API.

## 10. Billing & Credits

**Out of scope for MVP** — the product is free during the hackathon. If usage-metered billing is added
later: Stripe Checkout + webhooks → an append-only credit ledger; each agent run debits credits by
model/stage; reserve on enqueue, refund on failure. The `agent_runs.cost` column already records
realized per-run cost to make this calibration possible. (Note: `eval_doc_count` is the main user-facing
cost lever.)

## 11. API Design (FastAPI)

Auth required except webhooks/health. JSON; cursor pagination on lists.

```text
POST   /tasks                     create a task (brief + type + eval_doc_count) → enqueue planning
GET    /tasks                     list user's tasks
GET    /tasks/{id}                detail incl. plan, per-agent run status
POST   /tasks/{id}/documents      register an uploaded document
POST   /uploads/presign           presigned S3 PUT for a source document
GET    /tasks/{id}/candidates     ranked evidence pool (rank + eval scores)
GET    /tasks/{id}/output         the synthesised argument (latest version)
GET    /healthz
```

## 12. Frontend (Next.js + Tailwind)

Auth via Supabase JS; RLS reads for lists. Key screens:

- **Task console** — create a task (pick type, write brief, set **how many documents to evaluate (N)**,
  upload source documents), watch agent progress through the stages.
- **Evidence / ranking view** — the candidate pool ordered by reranker relevance, showing which top-N
  were evaluated and their relevance/risk/uncertainty scores.
- **Argument viewer** — the synthesised argument (markdown), with version history and citations back to
  the evaluated evidence.

Authed routes under `app/(app)/`. All API calls through `lib/apiClient.ts`. Document uploads go direct
to S3 via presigned URLs.

## 13. Observability, Security, Rate Limiting

Structured JSON logs correlated by `task_id` / `agent_run_id`; per-agent success/latency metrics and
queue depth; `request_id` propagated API → worker → run rows. Per-user Redis token-bucket limits and
global per-vendor concurrency caps (esp. Perplexity / CELLAR / LLM). Secrets in Secrets Manager; S3
private + signed URLs; RLS on all user data. **Legal-data care:** uploaded documents and outputs are
sensitive — encrypt at rest, scope access strictly by `user_id`/org, and never send client documents to
a provider in mock mode.

## 14. Cost Model

Marginal cost ≈ LLM tokens (Planner/Coordinator/eval on Opus, agents on Sonnet) + Perplexity calls +
CELLAR queries + storage. The dominant lever is `eval_doc_count` (how many docs the evaluator processes).
Tracked per stage on `agent_runs.cost`; this is the input to any future metered pricing (§10).

## 15. Open Questions / To Confirm Later

1. **Product name** — TBD (working title "Legal Drafting Copilot").
2. **Reranker** — deterministic scorer vs learned (Cohere) for MVP? Default: deterministic, swappable
   via `RERANK_MODE`.
3. **Async vs inline for the demo** — run Celery eager for the hackathon, or stand up real workers?
   Affects only ops, not the code path.
4. **CELLAR integration** — exact access path (SPARQL endpoint, REST, or a prepared corpus) and which
   document classes/metadata the web agent queries.
5. **Knowledge graph (Neo4j)** — the whiteboard noted Neo4j under the web agent; the settled process
   describes web + CELLAR + uploads directly. Is a Neo4j graph layer in scope (e.g. to structure CELLAR
   metadata / precedent relationships), or dropped for MVP?
6. **Document-graph review** — the whiteboard's "nodes requiring lawyer review" (clause-level flagging).
   In scope as part of the doc agent, or deferred to Phase 2 with the evaluator output standing in?
7. **Evaluator output shape** — beyond scoring the top-N, does the lawyer get an interactive
   accept/reject pass over evaluated documents before synthesis?
8. **Multi-tenancy** — single user (hackathon) vs org/team workspaces.
