"use client";

import { useCallback, useEffect, useState } from "react";
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
import { attentionPhrase, priorityBand } from "@/lib/plain";
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
            {/* Left: queue + lanes */}
            <div className="space-y-6 lg:col-span-5">
              <section>
                <SectionHeader
                  title="Needs your review"
                  caption="Your most pressing items first — the riskier and less certain the work, the higher it sits."
                  count={data.queue.length}
                />
                {data.queue.length === 0 ? (
                  <EmptyNote text="Nothing needs your review. Approve a plan to send work out." />
                ) : (
                  <ul className="space-y-2.5">
                    {data.queue.map((card) => (
                      <QueueRow
                        key={card.task.id}
                        card={card}
                        active={selected === card.task.id}
                        onClick={() => setSelected(card.task.id)}
                      />
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <SectionHeader
                  title="Cleared automatically"
                  caption="Low-risk work, cleared and recorded. A random few are pulled back for a spot-check, like a financial audit."
                  count={data.auto_clear_lane.length}
                />
                {data.auto_clear_lane.length === 0 ? (
                  <EmptyNote text="No auto-cleared items." />
                ) : (
                  <ul className="space-y-2">
                    {data.auto_clear_lane.map((card) => (
                      <li key={card.task.id}>
                        <Panel className="flex items-center justify-between gap-3 px-4 py-3">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2">
                              <SeverityBadge severity={card.task.severity} />
                              <span className="truncate text-sm font-medium text-ink">
                                {card.task.title}
                              </span>
                            </div>
                            <div className="mt-0.5 text-[11px] text-muted">
                              Low risk — cleared and recorded
                            </div>
                          </div>
                          {card.risk?.sampled ? (
                            <span
                              className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800 ring-1 ring-inset ring-amber-200"
                              title="Pulled into your queue for a spot-check, like a financial audit"
                            >
                              spot-check
                            </span>
                          ) : (
                            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">
                              cleared
                            </span>
                          )}
                        </Panel>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <SectionHeader
                  title="Escalations"
                  caption="Work that fell back to a human — a partner reject or a fail-safe pipeline failure. Awaiting a partner-approved redo; never auto-reassigned into the machine."
                  count={data.escalated.length}
                />
                {data.escalated.length === 0 ? (
                  <EmptyNote text="No escalations — nothing fell back to a human." />
                ) : (
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
                )}
              </section>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <MiniSection
                  title="With a person"
                  caption="Tasks assigned to an associate — waiting in their inbox."
                  cards={data.awaiting_human}
                  emptyText="Nothing with a person right now."
                />
                <MiniSection
                  title="You've decided"
                  caption="Work you've already signed off, amended, or sent back."
                  cards={data.decided}
                  emptyText="No decisions yet."
                  onSelect={setSelected}
                  selected={selected}
                />
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
  const prio = priorityBand(risk?.priority);
  const prioCls =
    prio.band === "high"
      ? "bg-red-50 text-red-700 ring-red-200"
      : prio.band === "medium"
        ? "bg-amber-50 text-amber-700 ring-amber-200"
        : "bg-slate-100 text-slate-600 ring-slate-200";
  return (
    <li>
      <button
        onClick={onClick}
        className={`w-full rounded-xl border bg-paper p-4 text-left shadow-sm transition-colors ${
          active ? "border-brand ring-1 ring-brand" : "border-line hover:border-slate-300"
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${prioCls}`}
          >
            {prio.label}
          </span>
          <div className="flex items-center gap-2">
            <SeverityBadge severity={task.severity} />
            {risk?.sampled ? (
              <span
                className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800 ring-1 ring-inset ring-amber-200"
                title="Low-risk item pulled for a spot-check, like a financial audit"
              >
                spot-check
              </span>
            ) : null}
          </div>
        </div>

        <div className="mt-2 text-sm font-semibold text-ink">{task.title}</div>

        {top_flag ? (
          <div className="mt-2 flex items-start gap-2">
            <HardSoftChip hard={top_flag.hard} />
            <span className="text-xs text-ink-soft">{top_flag.title}</span>
          </div>
        ) : (
          <div className="mt-2 text-xs text-muted">Nothing flagged.</div>
        )}

        <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full ${
              prio.band === "high"
                ? "bg-red-500"
                : prio.band === "medium"
                  ? "bg-amber-500"
                  : "bg-slate-400"
            }`}
            style={{ width: `${Math.round((risk?.priority ?? 0) * 100)}%` }}
          />
        </div>

        <div className="mt-2 text-[11px] text-muted">
          {attentionPhrase(flag_count, !!top_flag?.hard)}
        </div>
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

function MiniSection({
  title,
  caption,
  cards,
  emptyText,
  onSelect,
  selected,
}: {
  title: string;
  caption: string;
  cards: Card[];
  emptyText: string;
  onSelect?: (id: string) => void;
  selected?: string | null;
}) {
  return (
    <section>
      <SectionHeader title={title} caption={caption} count={cards.length} small />
      {cards.length === 0 ? (
        <EmptyNote text={emptyText} />
      ) : (
        <ul className="space-y-2">
          {cards.map((card) => {
            const inner = (
              <Panel
                className={`px-3 py-2.5 ${
                  onSelect ? "cursor-pointer hover:border-slate-300" : ""
                } ${selected === card.task.id ? "border-brand ring-1 ring-brand" : ""}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-xs font-medium text-ink">{card.task.title}</span>
                  <StatusPill status={card.task.status} />
                </div>
              </Panel>
            );
            return (
              <li key={card.task.id}>
                {onSelect ? (
                  <button className="w-full text-left" onClick={() => onSelect(card.task.id)}>
                    {inner}
                  </button>
                ) : (
                  inner
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function SectionHeader({
  title,
  caption,
  count,
  small,
}: {
  title: string;
  caption: string;
  count: number;
  small?: boolean;
}) {
  return (
    <div className="mb-2.5">
      <div className="flex items-center gap-2">
        <h2 className={`font-semibold text-ink ${small ? "text-sm" : "text-base"}`}>{title}</h2>
        <span className="rounded-full bg-canvas px-2 py-0.5 text-[11px] font-medium text-muted ring-1 ring-inset ring-line">
          {count}
        </span>
      </div>
      <p className="mt-0.5 text-[11px] leading-snug text-muted">{caption}</p>
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
