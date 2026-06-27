"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { getAudit, getCase, getPlan } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { AuditEvent, AuditView, Case } from "@/lib/types";
import { Spinner } from "@/components/ui";
import { CaseSubNav } from "@/components/CaseSubNav";

// The audit trail is read by a senior partner, not an engineer. Every event is rendered as a plain
// sentence ("who did what"), in time order. Hashes, sequence numbers and raw payloads are real and
// kept — but tucked inside an optional "technical details" disclosure so they never get in the way.
// We still keep the two kinds of record distinct (architecture.md §11): each entry is tagged either
// a "Decision record" (the signed legal trail) or a "Quality flag" (attention only, never a verdict).

type Filter = "all" | "decisions" | "flags";

export default function AuditPage() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [data, setData] = useState<AuditView | null>(null);
  const [taskTitles, setTaskTitles] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  // Filters. Seeded from the URL so the cockpit can deep-link to one task's trail.
  const [show, setShow] = useState<Filter>("all");
  const [actor, setActor] = useState<string>("all");
  const [task, setTask] = useState<string | null>(null);

  useEffect(() => {
    setTask(search.get("task"));
    const a = search.get("actor");
    if (a) setActor(a);
  }, [search]);

  useEffect(() => {
    Promise.all([getCase(id), getAudit(id)])
      .then(([c, a]) => {
        setCaseData(c);
        setData(a);
      })
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Failed to load audit."));
    getPlan(id)
      .then((p) => setTaskTitles(Object.fromEntries(p.tasks.map((t) => [t.id, t.title]))))
      .catch(() => {});
  }, [id]);

  // Merge both record streams into a single chronological story (partners think in time, not in
  // two parallel columns). The per-entry tag preserves which kind each event is.
  const all = useMemo(() => {
    if (!data) return [];
    const tagged = [
      ...data.accountability.map((e) => ({ e, kind: "decision" as const })),
      ...data.supervision.map((e) => ({ e, kind: "flag" as const })),
    ];
    return tagged.sort((a, b) => a.e.seq - b.e.seq);
  }, [data]);

  const actors = useMemo(() => {
    const set = new Set<string>();
    all.forEach(({ e }) => set.add(e.actor));
    return [...set].sort();
  }, [all]);

  const visible = all.filter(({ e, kind }) => {
    if (show === "decisions" && kind !== "decision") return false;
    if (show === "flags" && kind !== "flag") return false;
    if (actor !== "all" && e.actor !== actor) return false;
    if (task && e.task_id !== task) return false;
    return true;
  });

  const filtering = show !== "all" || actor !== "all" || !!task;
  const clearFilters = () => {
    setShow("all");
    setActor("all");
    setTask(null);
  };

  return (
    <div>
      <CaseSubNav caseId={id} title={caseData?.title} />
      <div className="mx-auto max-w-3xl px-6 py-6">
        {error ? (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {!data ? (
          <Spinner label="Loading the trail…" />
        ) : (
          <>
            <div className="mb-4">
              <h1 className="text-xl font-semibold tracking-tight text-ink">
                What happened on this matter
              </h1>
              <p className="mt-1 text-sm text-muted">
                Every step on this case, in order — who did what, and when. Nothing here can be edited
                after the fact.
              </p>
            </div>

            {/* Trust, in plain language. The hash detail is available but tucked away. */}
            <div
              className={`mb-5 rounded-xl border p-4 ${
                data.chain_valid ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-lg">{data.chain_valid ? "🔒" : "⚠"}</span>
                <div className="text-sm font-semibold text-ink">
                  {data.chain_valid
                    ? "Complete and tamper-proof record"
                    : "Warning — this record may have been altered"}
                </div>
              </div>
              <details className="mt-2 pl-9 text-xs text-ink-soft">
                <summary className="cursor-pointer text-brand hover:underline">
                  How do we know?
                </summary>
                <p className="mt-1.5 leading-relaxed">
                  Each entry is sealed with a fingerprint that includes the previous entry&apos;s
                  fingerprint, forming an unbroken chain. If anyone changed, removed, or reordered a
                  past entry, the chain would no longer match — and this banner would turn red. We
                  re-checked the whole chain just now and it{" "}
                  {data.chain_valid ? "matches" : "does NOT match"}.
                </p>
              </details>
            </div>

            {/* Friendly filter bar */}
            <div className="mb-5 flex flex-wrap items-center gap-3">
              <div className="inline-flex rounded-lg bg-canvas p-0.5 ring-1 ring-inset ring-line">
                {(
                  [
                    ["all", "Everything"],
                    ["decisions", "Decisions"],
                    ["flags", "Flags"],
                  ] as [Filter, string][]
                ).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setShow(key)}
                    className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
                      show === key ? "bg-brand text-white shadow-sm" : "text-muted hover:text-ink"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <label className="flex items-center gap-2 text-xs font-medium text-ink-soft">
                Who
                <select
                  value={actor}
                  onChange={(e) => setActor(e.target.value)}
                  className="rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
                >
                  <option value="all">Everyone</option>
                  {actors.map((a) => (
                    <option key={a} value={a}>
                      {humanizeActor(a)}
                    </option>
                  ))}
                </select>
              </label>

              {task ? (
                <span className="inline-flex items-center gap-2 rounded-full bg-brand-soft px-3 py-1 text-xs font-medium text-brand">
                  Following: {taskTitles[task] ?? `task ${task.slice(0, 8)}`}
                </span>
              ) : null}

              {filtering ? (
                <button
                  onClick={clearFilters}
                  className="ml-auto rounded-lg px-2.5 py-1.5 text-xs font-semibold text-brand ring-1 ring-inset ring-line hover:bg-brand-soft"
                >
                  Show everything ✕
                </button>
              ) : null}
            </div>

            {visible.length === 0 ? (
              <div className="rounded-xl border border-dashed border-line bg-canvas px-4 py-10 text-center text-sm text-muted">
                Nothing to show with these filters.{" "}
                <button onClick={clearFilters} className="font-semibold text-brand hover:underline">
                  Show everything
                </button>
                .
              </div>
            ) : (
              <ol className="relative space-y-1">
                {visible.map(({ e, kind }) => (
                  <Entry
                    key={e.id}
                    ev={e}
                    kind={kind}
                    taskTitle={e.task_id ? taskTitles[e.task_id] : undefined}
                    onActor={() => setActor(e.actor)}
                    onTask={() => e.task_id && setTask(e.task_id)}
                  />
                ))}
              </ol>
            )}

            <p className="mt-6 text-center text-xs text-muted">
              Showing {visible.length} of {all.length} step{all.length === 1 ? "" : "s"}.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function Entry({
  ev,
  kind,
  taskTitle,
  onActor,
  onTask,
}: {
  ev: AuditEvent;
  kind: "decision" | "flag";
  taskTitle?: string;
  onActor: () => void;
  onTask: () => void;
}) {
  const d = describe(ev, taskTitle);
  return (
    <li className="flex gap-3">
      {/* Glyph + connecting line */}
      <div className="flex flex-col items-center">
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold ${d.glyphCls}`}
        >
          {d.glyph}
        </span>
        <span className="my-1 w-px flex-1 bg-line" />
      </div>

      <div className="min-w-0 flex-1 pb-4">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-sm font-semibold text-ink">{d.sentence}</span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset ${
              kind === "decision"
                ? "bg-brand-soft text-brand ring-brand/20"
                : "bg-amber-50 text-amber-700 ring-amber-200"
            }`}
            title={
              kind === "decision"
                ? "Part of the signed legal record"
                : "A point flagged for your attention — never a verdict"
            }
          >
            {kind === "decision" ? "Decision record" : "Quality flag"}
          </span>
        </div>

        <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-muted">
          <span>{fmt(ev.created_at)}</span>
          <span>·</span>
          <button onClick={onActor} className="hover:text-brand" title="Show only this person/agent">
            {humanizeActor(ev.actor)}
          </button>
          {ev.task_id && taskTitle ? (
            <>
              <span>·</span>
              <button onClick={onTask} className="hover:text-brand" title="Follow this task">
                {taskTitle}
              </button>
            </>
          ) : null}
        </div>

        {/* Power-user detail, hidden by default (H8 minimalism, H10 help on demand). */}
        <details className="mt-1.5 text-[11px]">
          <summary className="cursor-pointer list-none text-muted hover:text-ink">
            <span className="underline-offset-2 hover:underline">Technical details</span>
          </summary>
          <dl className="mt-1.5 grid grid-cols-1 gap-1 rounded-lg border border-line bg-canvas p-2.5">
            <Row k="Event type" v={ev.type} />
            <Row k="Actor (raw)" v={ev.actor} />
            <Row k="Sequence #" v={String(ev.seq)} />
            <Row k="Fingerprint" v={ev.hash} mono />
            {Object.entries(ev.payload || {}).map(([k, v]) => (
              <Row key={k} k={k} v={fmtVal(v)} />
            ))}
          </dl>
        </details>
      </div>
    </li>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted">{k}</dt>
      <dd className={`truncate text-right font-medium text-ink-soft ${mono ? "font-mono" : ""}`}>
        {v}
      </dd>
    </div>
  );
}

// --- Plain-language translation of each event type ------------------------------------------------

type Described = { glyph: string; glyphCls: string; sentence: string };

function describe(ev: AuditEvent, taskTitle?: string): Described {
  const p = ev.payload || {};
  const who = humanizeActor(ev.actor);
  const onTask = taskTitle ? ` on “${taskTitle}”` : "";

  switch (ev.type) {
    case "plan_proposed": {
      const n = (p.n_tasks as number) ?? 0;
      return mk("📋", "slate", `A plan was drafted — ${n} task${n === 1 ? "" : "s"} proposed for your approval.`);
    }
    case "plan_approved":
      return mk("✓", "emerald", `${who} approved the plan and released the work.`);
    case "task_dispatched": {
      const at = p.assignee_type as string;
      const to =
        at === "ai" ? "the AI worker" : at === "hybrid" ? "a human associate (AI-assisted)" : "a human associate";
      return mk("→", "brand", `Work was sent to ${to}${onTask}.`);
    }
    case "submission_received":
      return mk("↓", "slate", `${who} submitted their work${onTask}.`);
    case "auto_cleared": {
      const u = typeof p.uncertainty === "number" ? ` (uncertainty ${Math.round(p.uncertainty * 100)}%)` : "";
      return mk("✓", "slate", `A low-risk item cleared automatically and was logged${u}${onTask}.`);
    }
    case "flag_raised": {
      const hard = p.hard === true;
      const title = (p.title as string) || "a point to check";
      return mk(
        "⚑",
        hard ? "red" : "amber",
        `Quality check raised ${hard ? "a must-check flag" : "a flag"}: ${title}.`
      );
    }
    case "decision_recorded": {
      const action = p.action as string;
      const note = (p.note as string)?.trim();
      const verb =
        action === "approve"
          ? "signed off on"
          : action === "amend"
            ? "amended"
            : "rejected and sent back";
      const glyph = action === "approve" ? "✓" : action === "amend" ? "✎" : "↩";
      const cls = action === "approve" ? "emerald" : action === "amend" ? "amber" : "red";
      return mk(glyph, cls, `${who} ${verb} the work${onTask}${note ? ` — “${note}”` : "."}`);
    }
    case "clarification_requested":
      return mk("?", "amber", `${who} asked the partner a question${onTask}.`);
    case "clarification_answered":
      return mk("↩", "brand", `${who} answered the associate's question${onTask}.`);
    case "task_reassigned":
      return mk("⟳", "brand", `${who} reassigned the task${onTask}.`);
    case "debrief_generated":
      return mk("📋", "slate", `A closing summary of the case was generated.`);
    default:
      return mk("•", "slate", `${who}: ${ev.type.replace(/_/g, " ")}${onTask}.`);
  }
}

function mk(glyph: string, tone: "emerald" | "amber" | "red" | "brand" | "slate", sentence: string): Described {
  const glyphCls = {
    emerald: "bg-emerald-100 text-emerald-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-red-100 text-red-700",
    brand: "bg-brand-soft text-brand",
    slate: "bg-slate-100 text-slate-500",
  }[tone];
  return { glyph, glyphCls, sentence };
}

function humanizeActor(actor: string): string {
  if (actor.startsWith("worker:")) return "The AI worker";
  if (actor.startsWith("associate:")) {
    const name = actor.slice("associate:".length).split("@")[0];
    return `Associate ${cap(name)}`;
  }
  if (actor === "checker") return "Automated quality check";
  if (actor === "coordinator" || actor === "system") return "The system";
  if (actor.includes("@")) {
    const name = actor.split("@")[0];
    return name === "partner" ? "You (partner)" : `${cap(name)} (partner)`;
  }
  return cap(actor);
}

function cap(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}

function fmt(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
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
