"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { closeCase, getCase, getDebrief } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { Case, DebriefDoc } from "@/lib/types";
import { Button, Panel, Spinner } from "@/components/ui";
import { CaseSubNav } from "@/components/CaseSubNav";
import { DebriefReport } from "@/components/DebriefReport";

export default function DebriefPage() {
  const { id } = useParams<{ id: string }>();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [debrief, setDebrief] = useState<DebriefDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCase = () => getCase(id).then(setCaseData).catch(() => {});

  useEffect(() => {
    loadCase();
    getDebrief(id)
      .then(setDebrief)
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setDebrief(null);
        else setError(e instanceof ApiError ? e.detail : "Failed to load debrief.");
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const onClose = async () => {
    setClosing(true);
    setError(null);
    try {
      setDebrief(await closeCase(id));
      await loadCase();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not close the case.");
    } finally {
      setClosing(false);
    }
  };

  const closed = caseData?.status === "closed";
  const parsed = debrief ? splitDebrief(debrief.content) : null;
  const generatedAt = debrief?.created_at ?? caseData?.closed_at;

  return (
    <div>
      <CaseSubNav caseId={id} title={caseData?.title} />
      <div className="mx-auto max-w-3xl px-6 py-8">
        {/* Action bar (hidden when printing) */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 print:hidden">
          <div>
            <h1 className="text-lg font-semibold text-ink">Case debrief</h1>
            <p className="mt-0.5 text-xs text-muted">
              A summary drawn from the case record at close — tasks, flags, and your decisions.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {debrief ? (
              <Button variant="secondary" onClick={() => window.print()}>
                Print / Save PDF
              </Button>
            ) : null}
            {!closed ? (
              <Button onClick={onClose} disabled={closing}>
                {closing
                  ? "Closing…"
                  : debrief
                    ? "Regenerate"
                    : "Close case & generate debrief"}
              </Button>
            ) : (
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500 ring-1 ring-inset ring-slate-200">
                Case closed
              </span>
            )}
          </div>
        </div>

        {error ? (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {loading ? (
          <Spinner label="Loading debrief…" />
        ) : debrief && parsed ? (
          <Panel className="overflow-hidden">
            {/* Letterhead */}
            <header className="border-b border-line bg-canvas px-8 py-7">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.15em] text-brand">
                    Case debrief
                  </div>
                  <h2 className="mt-1.5 text-2xl font-bold leading-tight tracking-tight text-ink">
                    {caseData?.title ?? "Case"}
                  </h2>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${
                    closed
                      ? "bg-slate-100 text-slate-600 ring-slate-200"
                      : "bg-emerald-50 text-emerald-700 ring-emerald-200"
                  }`}
                >
                  {closed ? "Closed" : "Open"}
                </span>
              </div>

              {parsed.goal ? (
                <div className="mt-4 rounded-lg border border-line bg-paper px-4 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                    Goal
                  </div>
                  <p className="mt-0.5 text-sm leading-relaxed text-ink-soft">{parsed.goal}</p>
                </div>
              ) : null}

              <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted">
                {generatedAt ? <span>Generated {fmtDate(generatedAt)}</span> : null}
                <span>·</span>
                <span>Prepared for the supervising partner</span>
              </div>
            </header>

            {/* Body */}
            <div className="bg-canvas/40 px-8 py-7">
              <DebriefReport content={parsed.body} />
            </div>

            {/* Honesty footer — the debrief is a summary, not a sign-off. */}
            <footer className="border-t border-line bg-canvas px-8 py-4 text-[11px] leading-relaxed text-muted">
              This debrief is an automatically generated summary of the case record. It restates what
              was done, flagged, and decided — it is not itself a legal opinion or a sign-off. The
              signed decisions live in the audit trail.
            </footer>
          </Panel>
        ) : (
          <Panel className="flex flex-col items-center gap-3 px-8 py-14 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-soft text-xl text-brand">
              ▤
            </div>
            <div className="text-sm font-medium text-ink">No debrief yet</div>
            <p className="max-w-sm text-sm text-muted">
              Close the case to generate a summary of every task, flag, and decision from the record.
            </p>
            {!closed ? (
              <Button onClick={onClose} disabled={closing} className="mt-1">
                {closing ? "Closing…" : "Close case & generate debrief"}
              </Button>
            ) : null}
          </Panel>
        )}
      </div>
    </div>
  );
}

// Lift the title (H1) and Goal out of the markdown so they can headline the letterhead; the rest of
// the document renders normally. Robust to content that omits them (e.g. free-form real output).
function splitDebrief(raw: string): { goal: string | null; body: string } {
  const lines = raw.replace(/\r\n/g, "\n").split("\n");
  let goal: string | null = null;
  const kept: string[] = [];
  for (const line of lines) {
    if (/^#\s+/.test(line)) continue; // drop the top-level title; shown in the letterhead
    const g = line.match(/^\*\*Goal:\*\*\s*(.*)$/);
    if (g) {
      goal = g[1].trim();
      continue;
    }
    kept.push(line);
  }
  while (kept.length && kept[0].trim() === "") kept.shift();
  return { goal, body: kept.join("\n") };
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
