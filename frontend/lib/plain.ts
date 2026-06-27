// Plain-language readings of the risk signals, for a senior partner with limited time.
// IMPORTANT: these are READINGS, not verdicts. They translate a measured signal into a sentence the
// partner can act on; they never say "pass"/"fail". The underlying number stays visible next to each
// reading (architecture.md §7.2 — every signal individually inspectable, none load-bearing alone).

export type Tone = "good" | "warn" | "bad" | "neutral";

export const TONE_TEXT: Record<Tone, string> = {
  good: "text-emerald-600",
  warn: "text-amber-600",
  bad: "text-red-600",
  neutral: "text-ink",
};

export type Reading = { text: string; tone: Tone };

export function priorityBand(p?: number | null): {
  label: string;
  band: "high" | "medium" | "low";
} {
  const v = p ?? 0;
  if (v >= 0.66) return { label: "High priority", band: "high" };
  if (v >= 0.33) return { label: "Medium priority", band: "medium" };
  return { label: "Low priority", band: "low" };
}

// Share of cited claims whose source actually supports them (1 = all check out).
export function citationReading(rate?: number | null): Reading {
  if (rate === null || rate === undefined) return { text: "No citations to verify", tone: "neutral" };
  if (rate >= 0.999) return { text: "Every citation checks out", tone: "good" };
  if (rate >= 0.5) return { text: "A citation doesn't fully back the claim", tone: "warn" };
  return { text: "Citations don't support the claims", tone: "bad" };
}

// Distance from the firm's own standard wording (higher = further away).
export function deviationReading(score?: number | null): Reading {
  const v = score ?? 0;
  if (v < 0.3) return { text: "Closely follows your firm standard", tone: "good" };
  if (v < 0.6) return { text: "Some departure from your firm standard", tone: "warn" };
  return { text: "Departs notably from your firm standard", tone: "warn" };
}

// Divergence when the review is run more than once (higher = less consistent).
export function disagreementReading(score?: number | null): Reading {
  const v = score ?? 0;
  if (v < 0.3) return { text: "The repeated reviews agreed", tone: "good" };
  if (v < 0.6) return { text: "The repeated reviews mostly agreed", tone: "warn" };
  return { text: "The repeated reviews disagreed", tone: "warn" };
}

// One-line overall reading of how much checking this needs (never an approval).
export function overallReading(uncertainty?: number | null): Reading {
  const v = uncertainty ?? 0;
  if (v >= 0.6) return { text: "Needs a close look", tone: "bad" };
  if (v >= 0.3) return { text: "Worth a careful check", tone: "warn" };
  return { text: "Looks routine — your call", tone: "good" };
}

// Short phrase for a queue row summarising what's flagged.
export function attentionPhrase(flagCount: number, hard: boolean): string {
  if (flagCount === 0) return "Nothing flagged";
  const base = `${flagCount} point${flagCount === 1 ? "" : "s"} to check`;
  return hard ? `${base} · 1 must-check` : base;
}
