"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getAudit, getCase } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { AuditEvent, AuditView, Case } from "@/lib/types";
import { Panel, Spinner } from "@/components/ui";
import { CaseSubNav } from "@/components/CaseSubNav";

export default function AuditPage() {
  const { id } = useParams<{ id: string }>();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [data, setData] = useState<AuditView | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getCase(id), getAudit(id)])
      .then(([c, a]) => {
        setCaseData(c);
        setData(a);
      })
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Failed to load audit."));
  }, [id]);

  return (
    <div>
      <CaseSubNav caseId={id} title={caseData?.title} />
      <div className="mx-auto max-w-7xl px-6 py-6">
        {error ? (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {!data ? (
          <Spinner label="Loading audit…" />
        ) : (
          <>
            {/* Chain validity banner */}
            <div
              className={`mb-5 flex items-center gap-3 rounded-xl border p-4 ${
                data.chain_valid
                  ? "border-emerald-200 bg-emerald-50"
                  : "border-red-200 bg-red-50"
              }`}
            >
              <span className="text-lg">{data.chain_valid ? "✓" : "⚠"}</span>
              <div>
                <div className="text-sm font-semibold text-ink">
                  {data.chain_valid
                    ? "Audit chain verified ✓"
                    : "Tamper warning — hash chain does not verify"}
                </div>
                <p className="mt-0.5 text-xs text-ink-soft">
                  Each event&apos;s hash covers the previous event&apos;s hash. Recomputing the chain
                  end-to-end {data.chain_valid ? "matches" : "does NOT match"} the stored hashes.
                </p>
              </div>
            </div>

            <div className="mb-4 rounded-lg border border-line bg-canvas px-4 py-3 text-xs leading-relaxed text-muted">
              Two streams, kept deliberately separate. <strong className="text-ink">Accountability</strong>{" "}
              is the defensible, signed record of who decided what — legal cover. <strong className="text-ink">Supervision</strong>{" "}
              is the actionable flag stream that routes a human&apos;s attention. Merged, you get a log
              with legal cover but no supervision, because nobody reads it.
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Stream
                title="Accountability"
                subtitle="Decisions, approvals, dispatch — signed & hash-chained."
                tone="brand"
                events={data.accountability}
              />
              <Stream
                title="Supervision"
                subtitle="Flags raised by the checker — attention routing."
                tone="amber"
                events={data.supervision}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Stream({
  title,
  subtitle,
  tone,
  events,
}: {
  title: string;
  subtitle: string;
  tone: "brand" | "amber";
  events: AuditEvent[];
}) {
  const dot = tone === "brand" ? "bg-brand" : "bg-amber-500";
  return (
    <section>
      <div className="mb-2.5 flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        <span className="rounded-full bg-canvas px-2 py-0.5 text-[11px] font-medium text-muted ring-1 ring-inset ring-line">
          {events.length}
        </span>
      </div>
      <p className="mb-3 text-[11px] text-muted">{subtitle}</p>

      {events.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line bg-canvas px-4 py-3 text-xs text-muted">
          No events in this stream yet.
        </div>
      ) : (
        <ol className="space-y-2.5">
          {events.map((ev) => (
            <li key={ev.id}>
              <Panel className="p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">
                    {ev.type.replace(/_/g, " ")}
                  </span>
                  <span className="text-[11px] text-muted">{fmt(ev.created_at)}</span>
                </div>
                <div className="mt-0.5 text-xs text-muted">
                  actor <span className="font-medium text-ink-soft">{ev.actor}</span>
                  {ev.task_id ? <span> · task {ev.task_id.slice(0, 8)}</span> : null}
                </div>
                {Object.keys(ev.payload || {}).length > 0 ? (
                  <dl className="mt-2 grid grid-cols-1 gap-1 rounded-lg bg-canvas p-2.5 text-[11px]">
                    {Object.entries(ev.payload).map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-3">
                        <dt className="text-muted">{k}</dt>
                        <dd className="truncate text-right font-medium text-ink-soft">
                          {fmtVal(v)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
                <div className="mt-2 flex items-center gap-1.5 font-mono text-[10px] text-muted">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5">#{ev.seq}</span>
                  <span title={ev.hash}>hash {ev.hash.slice(0, 12)}…</span>
                </div>
              </Panel>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function fmt(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

function fmtVal(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
