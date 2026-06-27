# Harvey Labs evaluation — tasks used and why

> Companion to `EU_TASKS.md` (the full EU catalogue) and the result files
> `batch_results.jsonl` (US cohort) + `eu_batch_1..5.jsonl` (EU cohort). Generated
> task metadata via the selection scripts in this folder; see "Reproduce" below.

This document records **which Harvey Labs tasks we run our supervision-cockpit pipeline
against, and the rationale**. Two cohorts so far: a 10-task **US/exploratory baseline**
and a 20-task **EU-pure** set.

---

## 1. Why these tasks — selection principles

Every task is filtered against what our system actually does. Our worker is an
**observation-only reviewer**: it reads a provided document bundle and surfaces *checkable
findings* against a standard — it never drafts new text, never does open-ended external
research, and never renders a verdict (architecture.md §14). The filters follow from that:

1. **Work type ∈ {`review`, `analyze`} only.** These are the modes that match an
   observation worker (review a document against a standard / identify issues in a
   document) and the only modes where our three supervision signals are meaningful (you can
   check citations and measure deviation on a review; you cannot on a freshly drafted
   clause). We exclude:
   - **`draft`** — generative authoring / redlines; our worker emits observations, not text.
   - **`research`** — needs external/web retrieval (our Perplexity path is roadmap-only).
   - **`""` (unlabeled)** — can't confirm they're review-shaped without inspecting each.
2. **Readable documents.** Our extractor handles `.docx/.pdf/.txt/.md/.eml`. US cohort
   required *fully* readable doc bundles; EU cohort relaxed to **≥50% readable** (some EU
   tasks ship `.xlsx`/`.pptx` we skip) so the worker still sees enough context.
3. **Tractable rubric size.** US: 6–42 criteria. EU: 6–60 (EU/GDPR rubrics run larger).
4. **Representative spread across practice areas**, picked round-robin so no single area
   dominates (and singleton areas still get represented).

All runs use **variant A** (the shipped worker, unchanged) and **severity = `high`**
(Harvey carries no severity; pinning it keeps Track A comparable — the consequence is that
Track B's auto-clear lane never triggers yet, which is expected and noted in the eval plan).

### The two cohorts
- **US/exploratory (10).** One review/analyze task from each of 10 distinct practice areas
  — a broad, shallow sweep to establish a cross-practice baseline and shake out bugs. (It
  did: surfaced and fixed the `max_tokens` truncation, the streaming requirement, invalid-
  JSON handling, and brittle `Finding`/`Deviation` construction.)
- **EU-pure (20).** Tasks with EU-law markers and **no US marker** (`eu_pure`), drawn from
  the EU catalogue. Rationale: our shipped citation model is CELEX/EUR-Lex-shaped, so EU
  (esp. GDPR) tasks are the slice where our worker's citations and the `citation_support` /
  `precedent_deviation` signals can fire faithfully. Run across 5 background sub-agents
  (4 tasks each). *Note: this cohort is variant A without the CELEX corpus seed yet — it
  measures EU work-quality apples-to-apples with the US baseline; full signal fidelity needs
  the GDPR/SCC seed (next step).*

### "Category" column
A task-nature label derived from the task (orthogonal to Harvey's `work_type`):
**Issue identification** · **Comparison vs reference/checklist** · **Review against
standard** · **Impact assessment** · **Obligation mapping** · **Triage / classification** ·
**Summarization**. It captures *what the rubric rewards*, which predicts fit: pure
issue-identification suits our worker best; comparison/checklist tasks are hardest (they
need structured cross-referencing the observation worker doesn't do).

---

## 2. US / exploratory cohort (10 tasks)

Work type: 4 `analyze`, 6 `review`. One per practice area. Results in `batch_results.jsonl`.

| # | task | area | category | work_type | crit |
|---|---|---|---|---|---|
| 1 | analyze-iss-antitrust-transaction-structure | antitrust-competition | Review/analyze | analyze | 40 |
| 2 | review-dispute-summary/scenario-01 | arbitration-international-dispute-resolution | Review against standard | review | 34 |
| 3 | identify-issues-in-borrower-financial-statements | banking-finance | Issue identification | analyze | 31 |
| 4 | identify-issues-in-counterparty-sale-objection | bankruptcy-restructuring | Issue identification | analyze | 28 |
| 5 | compare-closing-documents-against-closing-checklist | capital-markets | Comparison vs reference/checklist | review | 32 |
| 6 | identify-issues-in-dissident-proxy-statement | corporate-governance | Issue identification | analyze | 33 |
| 7 | compare-closing-docs | corporate-ma | Comparison vs reference/checklist | review | 33 |
| 8 | identify-issues-in-transfer-impact-assessment | data-privacy-cybersecurity | Issue identification | review | 33 |
| 9 | identify-issues-in-merger-agreement | emerging-companies-venture-capital | Issue identification | review | 33 |
| 10 | identify-issues-in-counterparty-motion-brief | employment-labor | Issue identification | review | 23 |

---

## 3. EU-pure cohort (20 tasks)

Work type: 10 `analyze`, 10 `review`. EU-pure (no US marker). Spread: data-privacy 7,
IP 6, corporate-governance 4, arbitration / banking / international-trade 1 each. Run via 5
sub-agents → `eu_batch_1..5.jsonl`.

| # | task | area | category | work_type | crit |
|---|---|---|---|---|---|
| 1 | identify-issues-in-counterpartys-document-production-requests | arbitration-international-dispute-resolution | Issue identification | review | 38 |
| 2 | identify-term-sheet-issues | banking-finance | Issue identification | review | 34 |
| 3 | assess-impact-of-eu-ai-act-on-company-ai-product-portfolio | corporate-governance | Impact assessment | analyze | 58 |
| 4 | assess-impact-of-new-gdpr-adequacy-decision-on-cross | corporate-governance | Impact assessment | analyze | 37 |
| 5 | map-eu-ai-act-transparency-obligations-to-existing-product-documentation | corporate-governance | Obligation mapping | analyze | 47 |
| 6 | triage-vendor-ai-contracts-for-compliance-with-eu-ai-liability-directive | corporate-governance | Triage / classification | analyze | 57 |
| 7 | compare-breach-notification-schedule-against-multi | data-privacy-cybersecurity | Comparison vs reference/checklist | analyze | 41 |
| 8 | compare-data-processing-agreement-against-internal-privacy-standards | data-privacy-cybersecurity | Comparison vs reference/checklist | review | 41 |
| 9 | compare-data-protection-remediation-plan-against-regulatory-undertaking-commitments | data-privacy-cybersecurity | Comparison vs reference/checklist | analyze | 41 |
| 10 | compare-privacy-notice-against-statutory-disclosure-requirements | data-privacy-cybersecurity | Comparison vs reference/checklist | analyze | 37 |
| 11 | review-incident-response-plan-against-regulatory-requirements-and-industry-standards | data-privacy-cybersecurity | Review against standard | review | 39 |
| 12 | summarize-new-gdpr-enforcement-guidance | data-privacy-cybersecurity | Summarization | analyze | 46 |
| 13 | triage-vendor-contracts-for-gdpr-cross | data-privacy-cybersecurity | Triage / classification | analyze | 47 |
| 14 | identify-issues-in-counterparty-data-processing-addendum | intellectual-property | Issue identification | review | 42 |
| 15 | identify-issues-in-vendor-cloud-infrastructure-proposal | intellectual-property | Issue identification | review | 44 |
| 16 | identify-technology-license-agreement-issues/scenario-01 | intellectual-property | Issue identification | review | 35 |
| 17 | identify-technology-license-agreement-issues/scenario-02 | intellectual-property | Issue identification | review | 35 |
| 18 | review-data-processing-agreement-against-company-data-protection-playbook | intellectual-property | Review against standard | review | 46 |
| 19 | review-master-services-agreement-for-regulatory-compliance | intellectual-property | Review against standard | review | 41 |
| 20 | compare-ownership-structure-against-sanctioned-parties-list | international-trade-sanctions | Comparison vs reference/checklist | analyze | 54 |

---

## 4. Caveats
- **Jurisdiction is a text proxy** over each `task.json` (instructions + criteria), so
  `eu_pure` under-counts and is heuristic — treat the EU/US split as a band.
- **Severity pinned `high`** → Track B (triage) is not yet exercised; needs severity
  variation + signal porting (see the eval plan).
- The EU cohort is **variant A, no CELEX seed** — work-quality only so far.

## 5. Reproduce
- EU catalogue: `uv run python -m harvey_eval.catalogue_eu` → `EU_TASKS.md` + `eu_tasks.json`.
- US 10 selection: `harvey-labs/_batch_tasks.json`. EU 20 selection: `harvey-labs/eu_group_1..5.json`.
- Run a cohort: `uv run python -m harvey_eval.batch --tasks-file <file> --severity high --tag <tag> --out <results.jsonl>`.
