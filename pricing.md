# Supervision Cockpit — Pricing & Margin Model

> Derives per-case pricing from **real vendor cost** (Anthropic Claude) so every billable case clears a
> target uplift. The billable **unit is a case** — one supervision run through the worker → checker →
> ranker → cockpit pipeline. Rates as of **June 2026**; re-run the check whenever a vendor rate changes.
>
> **Markup vs margin:** the rule below applies a **70% markup** (`price = cost × 1.70`), per the agreed
> commercial assumption. Note this is *markup*, not *gross margin* — a 70% markup yields ~41% gross
> margin. If a 70% *margin* is wanted instead, use `price = cost ÷ 0.30` (≈ cost × 3.33); see §2.

## 1. Marginal vendor cost per case

The dominant cost is LLM inference; everything else (SQLite, audit log, app compute) is negligible.
Per-case token profile: **250k input / 40k output**. Pricing per 1M tokens:

| Model | Input rate | Output rate | Input cost (0.250M) | Output cost (0.040M) | **Cost / case** |
|---|---|---|---|---|---|
| **Opus 4.8** (default) | $5.00 | $25.00 | $1.25 | $1.00 | **$2.25** |
| Sonnet 4.6 | $3.00 | $15.00 | $0.75 | $0.60 | $1.35 |
| Haiku 4.5 | $1.00 | $5.00 | $0.25 | $0.20 | $0.45 |

**Total marginal cost per case (Opus 4.8):** ≈ **$2.25**.

> Cost scales with token volume. The 250k input reflects a full matter context fed through every
> pipeline stage (worker + checker passes + ranker). **Prompt caching** on the stable matter context
> would bill cache reads at ~0.1× and could cut input cost 50–80% — model separately before committing
> to a price floor.

## 2. From cost to price (the markup rule)

For markup `k`, list price = `cost × (1 + k)`. At `k = 0.70` (Opus 4.8):

```
price = cost × 1.70   →   $2.25 × 1.70 = $3.83 / case
```

This yields a gross margin of `(3.83 − 2.25) / 3.83` ≈ **41%**.

If a **70% gross margin** is the actual target instead, the rule is `price = cost ÷ (1 − m)`:

```
price = cost ÷ 0.30   →   $2.25 ÷ 0.30 = $7.50 / case   (margin 70%)
```

Per-model price under the **70% markup** rule:

| Model | Cost / case | List (× 1.70) | Margin at that list |
|---|---|---|---|
| **Opus 4.8** | $2.25 | **$3.83** | 41% |
| Sonnet 4.6 | $1.35 | $2.30 | 41% |
| Haiku 4.5 | $0.45 | $0.77 | 41% |

## 3. Monthly cost for a Clifford Chance–scale firm

The dominant lever is **cases/month**, not the per-case math. Clifford Chance has ~3,400–3,700
fee-earners. Treating a "case" as a discrete matter/workstream advanced in a month, the central
estimate is **~5,000 cases/month** (≈1.5 per fee-earner), range 2,000–10,000.

Billed at the **Opus 4.8 marked-up price ($3.83/case)**:

| Cases / month | Opus 4.8 | Sonnet 4.6 | Haiku 4.5 |
|---|---|---|---|
| 2,000 (low) | $7,650 | $4,590 | $1,530 |
| **5,000 (central)** | **$19,125** | $11,475 | $3,825 |
| 10,000 (high) | $38,250 | $22,950 | $7,650 |

**Headline (Opus 4.8, central):** ≈ **$19k / month** → ≈ **$230k / year**.

## 4. Subscription tiers (firm-sized)

| Plan | Price / mo | Cases / mo incl. | Overage / case | Fit |
|---|---|---|---|---|
| Team | $2,000 | 500 | $4.00 | Boutique / single practice group |
| Firm | $15,000 | 4,000 | $3.83 | Mid / large firm |
| Enterprise | $35,000 | 10,000 | $3.50 | Magic Circle scale (e.g. Clifford Chance) |

**Overage** bills per case at the marked-up rate. **Pilot pack** *(CAC line, optional)*: 100 cases for
$250, one per firm — treated as acquisition spend, not a profit centre.

## 5. Recalibrating

When a vendor rate changes: update the per-1M rates in §1, recompute cost/case, then re-apply the markup
rule. Persist realized per-case cost (token usage × rate) on the case record and compare modelled vs
actual; re-tune if they drift. Switching the default model (Opus → Sonnet) is the largest single lever
on cost — re-derive §3 if the pipeline's default changes.

## Sources

- Anthropic model pricing (per 1M tokens), June 2026: Opus 4.8 $5/$25, Sonnet 4.6 $3/$15,
  Haiku 4.5 $1/$5 — https://platform.claude.com/docs/en/about-claude/models/overview
- Clifford Chance headcount (~3,400–3,700 fee-earners) — firm public reporting.
