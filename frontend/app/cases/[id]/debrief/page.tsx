"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { closeCase, getCase, getCockpit, getDebrief } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { Case, DebriefDoc, PendingSummary } from "@/lib/types";
import { Button, Panel, Spinner } from "@/components/ui";
import { CaseSubNav } from "@/components/CaseSubNav";
import { DebriefReport } from "@/components/DebriefReport";

export default function DebriefPage() {
  const { id } = useParams<{ id: string }>();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [debrief, setDebrief] = useState<DebriefDoc | null>(null);
  const [pending, setPending] = useState<PendingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCase = () => getCase(id).then(setCaseData).catch(() => {});
  // The cockpit view carries the complete pending count (across every status, not just the lanes),
  // so it's the readiness signal for whether the case can be closed.
  const loadPending = () =>
    getCockpit(id)
      .then((ck) => setPending(ck.pending))
      .catch(() => {});

  useEffect(() => {
    loadCase();
    loadPending();
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
      // The 409 carries the live pending breakdown; refresh it so the gate reflects reality.
      await loadPending();
    } finally {
      setClosing(false);
    }
  };

  const closed = caseData?.status === "closed";
  const report = debrief?.content ?? null;
  const generatedAt = debrief?.created_at ?? caseData?.closed_at;
  // Block close/regenerate until every task is resolved — a debrief from an in-flight record would
  // misrepresent the matter. The backend enforces this too (409); this just disables the button.
  const blocked = !closed && (pending?.total ?? 0) > 0;

  return (
    <div>
      <CaseSubNav caseId={id} title={caseData?.title} />
      <div className="mx-auto max-w-3xl px-6 py-8">
        {/* Action bar (hidden when printing) */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 print:hidden">
          <div>
            <h1 className="text-lg font-semibold text-ink">Case debrief</h1>
          </div>
          <div className="flex items-center gap-2">
            {debrief ? (
              <Button variant="secondary" onClick={() => window.print()}>
                Print / Save PDF
              </Button>
            ) : null}
            {!closed ? (
              <Button
                onClick={onClose}
                disabled={closing || blocked}
                title={blocked && pending ? pendingReason(pending) : undefined}
              >
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

        {blocked && pending ? (
          <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <span aria-hidden>⏳</span>
            <span>
              <span className="font-semibold">Not ready to close.</span> {pendingReason(pending)}
            </span>
          </div>
        ) : null}

        {error ? (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {loading ? (
          <Spinner label="Loading debrief…" />
        ) : debrief && report ? (
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

              {report.goal ? (
                <div className="mt-4 rounded-lg border border-line bg-paper px-4 py-3">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                    Goal
                  </div>
                  <p className="mt-0.5 text-sm leading-relaxed text-ink-soft">{report.goal}</p>
                </div>
              ) : null}

              {/* Synthesis line — the bottom line at a glance. Counts, never a verdict. */}
              <div className="mt-4 text-sm text-ink-soft">
                <Stat n={report.summary.tasks} /> tasks{" · "}
                <Stat n={report.summary.hard_flags} alert={report.summary.hard_flags > 0} /> hard
                flags{" · "}
                <Stat n={report.summary.rejected} alert={report.summary.rejected > 0} /> rejected
                {" · "}
                <Stat n={report.summary.carry_forward} warn={report.summary.carry_forward > 0} /> to
                carry forward
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted">
                {generatedAt ? <span>Generated {fmtDate(generatedAt)}</span> : null}
                <span>·</span>
                <span>Prepared for the supervising partner</span>
              </div>
            </header>

            {/* Body */}
            <div className="bg-canvas/40 px-8 py-7">
              <DebriefReport report={report} />
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
              <Button
                onClick={onClose}
                disabled={closing || blocked}
                title={blocked && pending ? pendingReason(pending) : undefined}
                className="mt-1"
              >
                {closing ? "Closing…" : "Close case & generate debrief"}
              </Button>
            ) : null}
          </Panel>
        )}
      </div>
    </div>
  );
}

// A friendly one-liner of what's still pending, built from the cockpit's complete pending breakdown.
function pendingReason(p: PendingSummary): string {
  const parts: string[] = [];
  if (p.awaiting_decision) parts.push(`${p.awaiting_decision} awaiting your decision`);
  if (p.with_associate) parts.push(`${p.with_associate} with an associate`);
  if (p.not_run) parts.push(`${p.not_run} not yet started`);
  const n = p.total;
  return `${n} task${n === 1 ? "" : "s"} still pending (${parts.join(
    ", "
  )}). Resolve them in the cockpit before closing.`;
}

// One bold count in the synthesis line. `alert`/`warn` tint a non-zero figure that warrants notice.
function Stat({ n, alert, warn }: { n: number; alert?: boolean; warn?: boolean }) {
  const cls = alert ? "text-red-700" : warn ? "text-amber-700" : "text-ink";
  return <span className={`font-semibold ${cls}`}>{n}</span>;
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
