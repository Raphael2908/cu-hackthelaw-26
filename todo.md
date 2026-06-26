# Legal Drafting Copilot — Product TODO

Prioritized **product** feature backlog, newest priorities first. Design source of truth stays
`architecture.md`; running log is `current_progress.md`.

---

## 0. First real end-to-end argument (mock → real LLM)

**Why now.** The scaffold runs the full pipeline on mock providers; the product has no value until a real
brief produces a real, cited argument. This is the core loop.

**What.** Wire `app/providers/real/llm.py` (Anthropic) and run the Planner → … → Synthesiser chain with
a real model. Keep Perplexity/CELLAR on mock until LLM works, then turn them on one at a time.

**Build sketch.** Implement the real provider behind the existing `LLMProvider` interface; no
orchestration changes (that's the point of the abstraction). Add a real Anthropic key to `.env`, flip
`PROVIDER_MODE=real`.

**Open questions.** Prompt design per agent; how the Planner's `plan.md` constrains downstream agents.

---

## 1. Lawyer-controlled evidence triage (the differentiator)

**What.** Surface the reranked candidate pool and the evaluated top-N to the lawyer, with relevance /
risk / uncertainty per document, before/after synthesis. Let the lawyer adjust **N** and re-run.

**Why it fits the architecture.** `candidates` already stores `rank` + `eval_*`; this is a read view plus
a re-run of the `evaluate → synthesize` tail, not a pipeline rewrite.

**Build sketch.** `GET /tasks/{id}/candidates` (exists) → evidence/ranking screen; a "re-evaluate with
N=…" action that re-enqueues from the evaluate stage.

**Status.** Not started.  **Depends on.** Item 0.

---

## 2. Real document ingestion (doc agent)

**What.** Parse lawyer-uploaded PDFs/DOCX into passages the doc agent can rank and cite.

**Build sketch.** A parsing step in the doc agent before it emits `candidates(origin=upload)`; store
extracted text. Consider clause/paragraph segmentation to enable the Phase-2 document-graph review.

**Status.** Not started.

---

## Deferred — CELLAR + Perplexity real integrations

Stubbed behind interfaces. Pick up once the real LLM loop works; CELLAR access path (SPARQL/REST/prepared
corpus) is an open question (architecture.md §15.4).

## Deferred — Neo4j knowledge graph

On the whiteboard but cut from the settled MVP flow. Trigger to revisit: when CELLAR metadata /
precedent relationships need structured querying beyond flat retrieval.

---

## Tech debt
- Real providers in `app/providers/real/` are stubs that raise — wire them before flipping `PROVIDER_MODE=real`.
- Document parsing is mocked; uploads are stored but not yet read.

## Notes
- Explicitly **dropped** this round: billing/credits (free MVP), Neo4j graph layer, clause-level
  document-graph review (Phase 2).
