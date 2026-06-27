"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getTrackRecord, listProcessMaps } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { ProcessMap, SignalType, TrackRecord, TrackRecordSection } from "@/lib/types";
import { AssigneeTag, ErrorNote, HardSoftChip, Panel, SignalTypeTag, Spinner } from "@/components/ui";

const SIGNAL_ORDER: SignalType[] = [
  "citation_support",
  "precedent_deviation",
  "multi_run_disagreement",
];

export default function TrackRecordPage() {
  const [maps, setMaps] = useState<ProcessMap[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [record, setRecord] = useState<TrackRecord | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProcessMaps()
      .then((m) => {
        setMaps(m);
        setSelected((cur) => cur || m[0]?.id || "");
      })
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Failed to load process maps."));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setRecord(null);
    setExpanded(null);
    getTrackRecord(selected)
      .then(setRecord)
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Failed to load track record."));
  }, [selected]);

  const sections = record ? Object.entries(record.by_section) : [];

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Agentic track record</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          How AI has actually performed on each section of a process map. A clean record graduates a
          section to AI by default; an adverse one pulls it back to a human owner. These are
          outcomes, never verdicts — the partner always decides.
        </p>
      </div>

      {error ? (
        <div className="mb-5">
          <ErrorNote message={error} />
        </div>
      ) : null}

      <Panel className="mb-6 p-4">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-ink-soft">Process map</span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink"
          >
            {maps.map((m) => (
              <option key={m.id} value={m.id}>
                {m.title}
              </option>
            ))}
          </select>
        </label>
      </Panel>

      {record === null ? (
        <Panel className="p-5">
          <Spinner label="Loading track record…" />
        </Panel>
      ) : (
        <>
          <Panel className="mb-6 overflow-hidden">
            <div className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
              By section
            </div>
            {sections.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted">
                Clean slate — no completed AI work on this process map yet. The planner proposes
                delegation by task nature; you decide where to insert AI.
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-muted">
                    <th className="px-4 py-2 font-medium">Section</th>
                    <th className="px-4 py-2 font-medium">Completed</th>
                    <th className="px-4 py-2 font-medium">Clean</th>
                    <th className="px-4 py-2 font-medium">Amended</th>
                    <th className="px-4 py-2 font-medium">Escalated</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sections.map(([key, s]) => {
                    const open = expanded === key;
                    return (
                      <SectionRows
                        key={key}
                        sectionKey={key}
                        section={s}
                        open={open}
                        onToggle={() => setExpanded(open ? null : key)}
                      />
                    );
                  })}
                </tbody>
              </table>
            )}
          </Panel>

          <Panel className="overflow-hidden">
            <div className="border-b border-line px-4 py-3 text-sm font-semibold text-ink">
              Completed agentic tasks ({record.log.length})
            </div>
            {record.log.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted">No completed AI/hybrid tasks.</div>
            ) : (
              <ul>
                {record.log.map((item) => (
                  <li
                    key={item.task_id}
                    className="flex items-center gap-3 border-b border-line px-4 py-3 last:border-0"
                  >
                    <AssigneeTag type={item.assignee_type} />
                    <span className="min-w-0 flex-1 truncate text-sm text-ink">{item.title}</span>
                    <span className="text-[11px] text-muted">{item.status}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${
                        item.outcome === "clean"
                          ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                          : "bg-rose-50 text-rose-700 ring-rose-200"
                      }`}
                    >
                      {item.outcome}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}

// A section row plus its expandable feedback detail (flags by signal, carry-forward notes, the
// matters it ran in). Clicking the row toggles the detail.
function SectionRows({
  sectionKey,
  section: s,
  open,
  onToggle,
}: {
  sectionKey: string;
  section: TrackRecordSection;
  open: boolean;
  onToggle: () => void;
}) {
  const signals = SIGNAL_ORDER.filter((sig) => s.flags_by_signal?.[sig]?.count);
  return (
    <>
      <tr
        className="cursor-pointer border-b border-line last:border-0 hover:bg-canvas"
        onClick={onToggle}
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-1.5 font-medium text-ink">
            <span className={`text-[10px] text-muted transition-transform ${open ? "rotate-90" : ""}`}>
              ▶
            </span>
            {s.label}
          </div>
          <div className="ml-4 mt-0.5 text-[11px] text-muted">{sectionKey.replace(/_/g, " ")}</div>
        </td>
        <td className="px-4 py-3 text-ink-soft">{s.completed}</td>
        <td className="px-4 py-3 text-ink-soft">{s.clean_successes}</td>
        <td className="px-4 py-3 text-ink-soft">{s.amended}</td>
        <td className="px-4 py-3 text-ink-soft">{s.escalated}</td>
        <td className="px-4 py-3">
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${
              s.clean
                ? "bg-violet-50 text-violet-700 ring-violet-200"
                : s.adverse > 0
                  ? "bg-rose-50 text-rose-700 ring-rose-200"
                  : "bg-slate-100 text-slate-500 ring-slate-200"
            }`}
          >
            {s.clean ? "graduated → AI" : s.adverse > 0 ? "pulled back" : "building"}
          </span>
        </td>
      </tr>
      {open ? (
        <tr className="border-b border-line bg-canvas/50 last:border-0">
          <td colSpan={6} className="space-y-4 px-4 py-4">
            {/* Flags raised, by checker signal (hard/soft visible). */}
            <div>
              <div className="text-[11px] font-medium uppercase tracking-wide text-muted">
                Flags raised
              </div>
              {signals.length === 0 ? (
                <p className="mt-1 text-[13px] text-muted">
                  None — the AI work cleared without flags here.
                </p>
              ) : (
                <div className="mt-1.5 flex flex-wrap gap-2">
                  {signals.map((sig) => {
                    const f = s.flags_by_signal[sig];
                    return (
                      <span
                        key={sig}
                        className="inline-flex items-center gap-1.5 rounded-md bg-white px-2 py-1 text-[12px] text-ink ring-1 ring-inset ring-line"
                      >
                        <SignalTypeTag type={sig} />
                        <span className="tabular-nums">{f.count}</span>
                        {f.hard ? <HardSoftChip hard /> : null}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Carry forward — the partner's own amend/reject words. */}
            {s.lessons.length > 0 ? (
              <div>
                <div className="text-[11px] font-medium uppercase tracking-wide text-muted">
                  Carry forward
                </div>
                <ul className="mt-1.5 space-y-1.5">
                  {s.lessons.map((l, i) => (
                    <li
                      key={i}
                      className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[13px] text-amber-900"
                    >
                      <span className="font-medium uppercase tracking-wide text-amber-700">
                        {l.action === "reject" ? "Rejected" : "Amended"}
                      </span>{" "}
                      {l.text}
                      <Link
                        href={`/cases/${l.case_id}/cockpit`}
                        className="ml-1 whitespace-nowrap font-medium text-brand hover:underline"
                      >
                        · {l.case_title} →
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {/* Drill-down: the matters this section ran in. */}
            {s.cases.length > 0 ? (
              <p className="text-[12px] text-muted">
                Run in:{" "}
                {s.cases.map((c, i) => (
                  <span key={c.case_id}>
                    {i > 0 ? " · " : ""}
                    <Link
                      href={`/cases/${c.case_id}/cockpit`}
                      className="text-brand hover:underline"
                    >
                      {c.title}
                    </Link>
                  </span>
                ))}
              </p>
            ) : null}
          </td>
        </tr>
      ) : null}
    </>
  );
}
