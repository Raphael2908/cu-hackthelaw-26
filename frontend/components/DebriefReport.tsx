"use client";

import { useState } from "react";
import type { DebriefContent, DebriefFlag, DebriefIssue } from "@/lib/types";
import { HardSoftChip, SeverityBadge, SignalTypeTag, StatusPill, Button } from "./ui";
import { MarkdownInline } from "./Markdown";
import { SourceDrawer } from "./SourceDrawer";

// The debrief reads as an issue-centric memo, not a dump of the data-model tables. Each
// needs-attention task is ONE composed card (its flags + the partner's decision joined), ordered
// worst-first by the backend. Routine cleared work collapses to a count. Recomposition + ordering
// only — flags stay checkable flags, the decision stays the partner's own; never a verdict.
export function DebriefReport({ report }: { report: DebriefContent }) {
  // The drawer wants a Flag-shaped object; the debrief flag carries the refs it needs.
  const [source, setSource] = useState<DebriefFlag | null>(null);

  return (
    <div className="space-y-8">
      <Section title="Needs-attention items" count={report.issues.length}>
        {report.issues.length === 0 ? (
          <p className="text-sm text-muted">Nothing needed your attention — every task cleared.</p>
        ) : (
          <ul className="space-y-3">
            {report.issues.map((issue, i) => (
              <li key={i}>
                <IssueCard issue={issue} onViewSource={setSource} />
              </li>
            ))}
          </ul>
        )}
      </Section>

      {report.cleared.length > 0 ? (
        <Section>
          <details className="group rounded-xl border border-line bg-paper shadow-sm">
            <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 [&::-webkit-details-marker]:hidden">
              <span className="text-sm font-semibold text-ink">Cleared without flags</span>
              <span className="rounded-full bg-canvas px-2 py-0.5 text-[11px] font-medium text-muted ring-1 ring-inset ring-line">
                {report.cleared.length}
              </span>
              <svg
                className="ml-auto h-4 w-4 text-muted transition-transform group-open:rotate-180"
                viewBox="0 0 20 20"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
              >
                <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </summary>
            <ul className="space-y-1.5 border-t border-line px-4 py-3">
              {report.cleared.map((c, i) => (
                <li key={i} className="flex items-center gap-2 text-sm">
                  <SeverityBadge severity={c.severity} />
                  <span className="truncate text-ink">{c.task_title}</span>
                </li>
              ))}
            </ul>
          </details>
        </Section>
      ) : null}

      {report.carry_forward.length > 0 ? (
        <Section title="Carry forward" count={report.carry_forward.length}>
          <ul className="space-y-2">
            {report.carry_forward.map((note, i) => (
              <li key={i} className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/50 p-3.5">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-amber-300 bg-amber-50 text-[11px] text-amber-700">
                  ☐
                </span>
                <p className="text-sm leading-relaxed text-ink-soft">{note}</p>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      <SourceDrawer
        sourceRef={source?.source_ref ?? null}
        workRef={source?.work_ref ?? null}
        onClose={() => setSource(null)}
      />
    </div>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title?: string;
  count?: number;
  children: React.ReactNode;
}) {
  return (
    <section>
      {title ? (
        <div className="mb-3 flex items-center gap-3">
          <span className="h-4 w-1 rounded-full bg-brand" aria-hidden />
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink">{title}</h2>
          {count !== undefined ? (
            <span className="rounded-full bg-canvas px-2 py-0.5 text-[11px] font-medium text-muted ring-1 ring-inset ring-line">
              {count}
            </span>
          ) : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

const DECISION_TONE: Record<string, { label: string; cls: string }> = {
  approve: { label: "Signed off", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  amend: { label: "Amended", cls: "bg-amber-50 text-amber-700 ring-amber-200" },
  reject: { label: "Rejected", cls: "bg-red-50 text-red-700 ring-red-200" },
};

// One issue, fully composed: the task, its flags (each reachable in one click), and the partner's
// own decision — together, so the reader never re-joins the tables.
function IssueCard({
  issue,
  onViewSource,
}: {
  issue: DebriefIssue;
  onViewSource: (f: DebriefFlag) => void;
}) {
  const hasHard = issue.flags.some((f) => f.hard);
  const dec = issue.decision ? DECISION_TONE[issue.decision.action] : null;
  return (
    <div
      className={`rounded-xl border p-4 shadow-sm ${
        hasHard ? "border-red-200 bg-red-50/30" : "border-line bg-paper"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={issue.severity} />
        <StatusPill status={issue.status} />
        <span className="text-sm font-semibold text-ink">{issue.task_title}</span>
      </div>

      {issue.flags.length > 0 ? (
        <div className="mt-3 space-y-2">
          {issue.flags.map((f, i) => (
            <div
              key={i}
              className={`rounded-lg border p-3 ${
                f.hard ? "border-red-200 bg-red-50/40" : "border-amber-200 bg-amber-50/40"
              }`}
            >
              <div className="mb-1 flex flex-wrap items-center gap-1.5">
                <SignalTypeTag type={f.signal_type} />
                <HardSoftChip hard={f.hard} />
              </div>
              <div className="text-sm font-medium text-ink">{f.title}</div>
              {f.description ? (
                <p className="mt-0.5 text-xs text-ink-soft">
                  <MarkdownInline text={f.description} />
                </p>
              ) : null}
              {f.source_ref ? (
                <div className="mt-2">
                  <Button
                    variant="secondary"
                    onClick={() => onViewSource(f)}
                    className="!py-1 !text-[11px]"
                  >
                    View source →
                  </Button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {issue.decision ? (
        <div className="mt-3 border-t border-line pt-3">
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${
                dec?.cls ?? "bg-canvas text-muted ring-line"
              }`}
            >
              {dec?.label ?? issue.decision.action}
            </span>
            <span className="text-[11px] text-muted">your decision</span>
          </div>
          {issue.decision.note ? (
            <p className="mt-1.5 text-sm text-ink-soft">
              <MarkdownInline text={issue.decision.note} />
            </p>
          ) : null}
          {issue.decision.amendment ? (
            <div className="mt-1.5 rounded-md bg-canvas px-2.5 py-1.5 text-xs text-ink-soft ring-1 ring-inset ring-line">
              <span className="font-semibold text-ink">Amendment:</span>{" "}
              <MarkdownInline text={issue.decision.amendment} />
            </div>
          ) : null}
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted">No decision recorded.</p>
      )}
    </div>
  );
}
