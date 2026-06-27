"use client";

import { type ReactNode, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getCase, getCockpit } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { Card, Case, Cockpit } from "@/lib/types";
import {
  HardSoftChip,
  Panel,
  SeverityBadge,
  Spinner,
  StatusPill,
} from "@/components/ui";
import { priorityBand } from "@/lib/plain";
import { CaseSubNav } from "@/components/CaseSubNav";
import { ItemDetail } from "@/components/ItemDetail";

export default function CockpitPage() {
  const { id } = useParams<{ id: string }>();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [data, setData] = useState<Cockpit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, ck] = await Promise.all([getCase(id), getCockpit(id)]);
      setCaseData(c);
      setData(ck);
      setSelected((cur) => cur ?? ck.queue[0]?.task.id ?? null);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Failed to load cockpit.");
    }
  }, [id]);

  useEffect(() => {
    load();
    // Tasks dispatch asynchronously, so poll while the cockpit is open to surface work as each
    // AI/hybrid pipeline finishes in the background (and as associates submit human tasks).
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

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
          <Spinner label="Loading cockpit…" />
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left: one focal review lane, with secondary lanes collapsed beneath it. */}
            <div className="space-y-5 lg:col-span-5">
              {/* Actionable, distinct from the review lane: an associate is blocked on the partner. */}
              {data.needs_reply.length > 0 ? (
                <section className="rounded-xl border border-violet-200 bg-violet-50/50 p-3">
                  <SectionHeader
                    title="Questions & concerns from associates"
                    caption="Reply to send the task back so they can finish."
                    count={data.needs_reply.length}
                  />
                  <ul className="space-y-2">
                    {data.needs_reply.map((card) => (
                      <QuestionRow
                        key={card.task.id}
                        card={card}
                        active={selected === card.task.id}
                        onClick={() => setSelected(card.task.id)}
                      />
                    ))}
                  </ul>
                </section>
              ) : null}

              {/* The figure: what the partner is here to do. */}
              <section>
                <SectionHeader
                  title="Needs your review"
                  count={data.queue.length}
                  prominent
                />
                {data.queue.length === 0 ? (
                  <EmptyNote text="Nothing needs your review. Approve a plan to send work out." />
                ) : (
                  <ReviewQueue cards={data.queue} selected={selected} onSelect={setSelected} />
                )}
              </section>

              {/* Urgent: work that fell back to a human — needs a partner-approved redo, not buried. */}
              {data.escalated.length > 0 ? (
                <section className="rounded-xl border border-rose-200 bg-rose-50/50 p-3">
                  <SectionHeader
                    title="Escalations"
                    caption="Work that fell back to a human — a partner reject or a fail-safe pipeline failure. Awaiting a partner-approved redo; never auto-reassigned into the machine."
                    count={data.escalated.length}
                  />
                  <ul className="space-y-2">
                    {data.escalated.map((card) => (
                      <EscalatedRow
                        key={card.task.id}
                        card={card}
                        active={selected === card.task.id}
                        onClick={() => setSelected(card.task.id)}
                      />
                    ))}
                  </ul>
                </section>
              ) : null}

              {/* The ground: handled or in-flight work, tucked away until the partner wants it. */}
              <div className="space-y-2.5">
                <CollapsibleLane
                  title="Cleared automatically"
                  count={data.auto_clear_lane.length}
                >
                  {data.auto_clear_lane.length === 0 ? (
                    <LaneEmpty text="No auto-cleared items." />
                  ) : (
                    <ul className="space-y-1.5">
                      {data.auto_clear_lane.map((card) => (
                        <li
                          key={card.task.id}
                          className="flex items-center justify-between gap-3 px-1 py-1"
                        >
                          <div className="flex min-w-0 items-center gap-2">
                            <SeverityBadge severity={card.task.severity} />
                            <span className="truncate text-sm text-ink">{card.task.title}</span>
                          </div>
                          {card.risk?.sampled ? <SpotCheckTag /> : <ClearedTag />}
                        </li>
                      ))}
                    </ul>
                  )}
                </CollapsibleLane>

                <CollapsibleLane
                  title="With a person"
                  count={data.awaiting_human.length}
                >
                  {data.awaiting_human.length === 0 ? (
                    <LaneEmpty text="Nothing with a person right now." />
                  ) : (
                    <ul className="space-y-1.5">
                      {data.awaiting_human.map((card) => (
                        <li
                          key={card.task.id}
                          className="flex items-center justify-between gap-2 px-1 py-1"
                        >
                          <span className="truncate text-sm text-ink">{card.task.title}</span>
                          <StatusPill status={card.task.status} />
                        </li>
                      ))}
                    </ul>
                  )}
                </CollapsibleLane>

                <CollapsibleLane
                  title="You've decided"
                  count={data.decided.length}
                >
                  {data.decided.length === 0 ? (
                    <LaneEmpty text="No decisions yet." />
                  ) : (
                    <ul className="space-y-1.5">
                      {data.decided.map((card) => (
                        <li key={card.task.id}>
                          <button
                            onClick={() => setSelected(card.task.id)}
                            className={`flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-canvas ${
                              selected === card.task.id ? "bg-brand-soft" : ""
                            }`}
                          >
                            <span className="truncate text-sm text-ink">{card.task.title}</span>
                            <StatusPill status={card.task.status} />
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </CollapsibleLane>
              </div>
            </div>

            {/* Right: item detail */}
            <div className="lg:col-span-7">
              {selected ? (
                <ItemDetail taskId={selected} onDecided={load} />
              ) : (
                <Panel className="flex h-64 items-center justify-center p-6 text-center text-sm text-muted">
                  Pick an item on the left to see what was done and decide.
                </Panel>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// The review lane, grouped into High / Medium / Low bands. Priority is conveyed by the grouping
// itself (proximity + similarity), so each card no longer needs its own priority pill or bar.
const BANDS = [
  { band: "high", label: "High priority", dot: "bg-red-500", text: "text-red-700" },
  { band: "medium", label: "Medium priority", dot: "bg-amber-500", text: "text-amber-700" },
  { band: "low", label: "Low priority", dot: "bg-slate-400", text: "text-slate-600" },
] as const;

function ReviewQueue({
  cards,
  selected,
  onSelect,
}: {
  cards: Card[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="space-y-4">
      {BANDS.map(({ band, label, dot, text }) => {
        const group = cards.filter((c) => priorityBand(c.risk?.priority).band === band);
        if (group.length === 0) return null;
        return (
          <div key={band}>
            <div className="mb-1.5 flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${dot}`} />
              <span className={`text-[11px] font-semibold uppercase tracking-wide ${text}`}>
                {label}
              </span>
              <span className="text-[11px] font-medium text-muted">{group.length}</span>
            </div>
            <ul className="space-y-2">
              {group.map((card) => (
                <QueueRow
                  key={card.task.id}
                  card={card}
                  active={selected === card.task.id}
                  onClick={() => onSelect(card.task.id)}
                />
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

// Slimmed to three things: title, one line of what to check, and severity / must-check when present.
function QueueRow({
  card,
  active,
  onClick,
}: {
  card: Card;
  active: boolean;
  onClick: () => void;
}) {
  const { task, risk, top_flag, flag_count } = card;
  const extra = flag_count > 1 ? ` · +${flag_count - 1} more to check` : "";
  return (
    <li>
      <button
        onClick={onClick}
        className={`w-full rounded-xl border bg-paper p-3.5 text-left shadow-sm transition-colors ${
          active ? "border-brand ring-1 ring-brand" : "border-line hover:border-slate-300"
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <span className="text-sm font-semibold text-ink">{task.title}</span>
          <div className="flex shrink-0 items-center gap-1.5">
            {risk?.sampled ? <SpotCheckTag /> : null}
            <SeverityBadge severity={task.severity} />
          </div>
        </div>

        {top_flag ? (
          <div className="mt-2 flex items-start gap-2">
            <HardSoftChip hard={top_flag.hard} />
            <span className="text-xs text-ink-soft">
              {top_flag.title}
              {extra}
            </span>
          </div>
        ) : (
          <div className="mt-2 text-xs text-muted">Nothing flagged</div>
        )}
      </button>
    </li>
  );
}

function EscalatedRow({
  card,
  active,
  onClick,
}: {
  card: Card;
  active: boolean;
  onClick: () => void;
}) {
  const { task } = card;
  return (
    <li>
      <button
        onClick={onClick}
        className={`w-full rounded-xl border bg-rose-50/60 p-3.5 text-left shadow-sm transition-colors ${
          active ? "border-rose-400 ring-1 ring-rose-300" : "border-rose-200 hover:border-rose-300"
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <SeverityBadge severity={task.severity} />
            <span className="truncate text-sm font-medium text-ink">{task.title}</span>
          </div>
          <span className="shrink-0 rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-semibold text-rose-800 ring-1 ring-inset ring-rose-200">
            escalated
          </span>
        </div>
        <div className="mt-1 text-[11px] text-rose-700/90">
          Returned to a human — awaiting a partner-approved redo.
        </div>
      </button>
    </li>
  );
}

function QuestionRow({
  card,
  active,
  onClick,
}: {
  card: Card;
  active: boolean;
  onClick: () => void;
}) {
  const last =
    card.messages?.filter((m) => m.kind === "question").slice(-1)[0] ??
    card.messages?.slice(-1)[0];
  return (
    <li>
      <button
        onClick={onClick}
        className={`w-full rounded-xl border bg-paper p-4 text-left shadow-sm transition-colors ${
          active ? "border-brand ring-1 ring-brand" : "border-violet-200 hover:border-violet-300"
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-semibold text-violet-700 ring-1 ring-inset ring-violet-200">
            Message
          </span>
          <SeverityBadge severity={card.task.severity} />
        </div>
        <div className="mt-2 text-sm font-semibold text-ink">{card.task.title}</div>
        {last ? (
          <p className="mt-1 line-clamp-2 text-xs italic text-ink-soft">“{last.body}”</p>
        ) : null}
      </button>
    </li>
  );
}

// A secondary lane, collapsed by default to a single summary row (title + count). The partner sees
// it exists and how much sits there; the contents stay out of the way until they expand it.
function CollapsibleLane({
  title,
  caption,
  count,
  children,
}: {
  title: string;
  caption?: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <details className="group rounded-xl border border-line bg-paper shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-ink">{title}</span>
            <span className="rounded-full bg-canvas px-2 py-0.5 text-[11px] font-medium text-muted ring-1 ring-inset ring-line">
              {count}
            </span>
          </div>
          {caption ? (
            <p className="mt-0.5 text-[11px] leading-snug text-muted">{caption}</p>
          ) : null}
        </div>
        <svg
          className="h-4 w-4 shrink-0 text-muted transition-transform group-open:rotate-180"
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
        >
          <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </summary>
      <div className="border-t border-line px-3 py-2.5">{children}</div>
    </details>
  );
}

function LaneEmpty({ text }: { text: string }) {
  return <div className="px-1 py-1 text-xs text-muted">{text}</div>;
}

function SpotCheckTag() {
  return (
    <span
      className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800 ring-1 ring-inset ring-amber-200"
      title="Low-risk item pulled for a spot-check, like a financial audit"
    >
      spot-check
    </span>
  );
}

function ClearedTag() {
  return (
    <span className="shrink-0 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">
      cleared
    </span>
  );
}

function SectionHeader({
  title,
  caption,
  count,
  prominent,
}: {
  title: string;
  caption?: string;
  count: number;
  prominent?: boolean;
}) {
  return (
    <div className="mb-2.5">
      <div className="flex items-center gap-2">
        <h2 className={`font-semibold text-ink ${prominent ? "text-lg" : "text-sm"}`}>{title}</h2>
        <span className="rounded-full bg-canvas px-2 py-0.5 text-[11px] font-medium text-muted ring-1 ring-inset ring-line">
          {count}
        </span>
      </div>
      {caption ? <p className="mt-0.5 text-[11px] leading-snug text-muted">{caption}</p> : null}
    </div>
  );
}

function EmptyNote({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-canvas px-4 py-3 text-xs text-muted">
      {text}
    </div>
  );
}
