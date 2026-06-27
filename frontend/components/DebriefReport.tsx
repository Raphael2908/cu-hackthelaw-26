"use client";

import type { ReactNode } from "react";
import type { AssigneeType, Severity, SignalType, TaskStatus } from "@/lib/types";
import {
  AssigneeTag,
  HardSoftChip,
  SeverityBadge,
  SignalTypeTag,
  StatusPill,
} from "./ui";
import { Markdown, MarkdownInline } from "./Markdown";

// Renders the generated debrief as a set of review-friendly cards instead of a wall of bullets.
// The mock debrief has a known shape (Tasks / Flags raised / Partner decisions / Carry forward), so
// we parse each item into a card with the right badges. Anything we can't parse — including free-form
// real-model output — falls back to a plain card or to the normal Markdown renderer.

type Section = { title: string; count: number | null; items: string[]; prose: string[] };

export function DebriefReport({ content }: { content: string }) {
  const sections = parseSections(content);
  if (sections.length === 0) return <Markdown content={content} />;

  return (
    <div className="space-y-8">
      {sections.map((s, i) => (
        <section key={i}>
          {s.title ? (
            <div className="mb-3 flex items-center gap-3">
              <span className="h-4 w-1 rounded-full bg-brand" aria-hidden />
              <h2 className="text-sm font-semibold uppercase tracking-wide text-ink">{s.title}</h2>
              {s.count !== null ? (
                <span className="rounded-full bg-canvas px-2 py-0.5 text-[11px] font-medium text-muted ring-1 ring-inset ring-line">
                  {s.count}
                </span>
              ) : null}
            </div>
          ) : null}

          {s.prose.length > 0 ? <Markdown content={s.prose.join("\n")} /> : null}

          {s.items.length > 0 ? (
            <ul className="space-y-2.5">
              {s.items.map((it, idx) => (
                <li key={idx}>{renderCard(s, it)}</li>
              ))}
            </ul>
          ) : null}

          {s.items.length === 0 && s.prose.length === 0 ? (
            <p className="text-sm text-muted">None.</p>
          ) : null}
        </section>
      ))}
    </div>
  );
}

function renderCard(section: Section, item: string): ReactNode {
  switch (kindOf(section.title)) {
    case "tasks":
      return <TaskCard item={item} />;
    case "flags":
      return <FlagCard item={item} />;
    case "decisions":
      return <DecisionCard item={item} />;
    case "carry":
      return <CarryCard item={item} />;
    default:
      return <PlainCard item={item} />;
  }
}

// --- Cards ---------------------------------------------------------------------------------------

const CARD = "rounded-xl border border-line bg-paper p-4 shadow-sm";

function TaskCard({ item }: { item: string }) {
  // `**<title>** — <assignee>, severity <sev>, status <status>`
  const m = item.match(/^\*\*(.+?)\*\*\s*[—-]\s*(.*)$/);
  const title = m?.[1] ?? null;
  const rest = m?.[2] ?? item;
  const assignee = pick(rest, /\b(human|ai|hybrid)\b/) as AssigneeType | null;
  const severity = pick(rest, /severity\s+(low|medium|high)/) as Severity | null;
  const status = pick(rest, /status\s+([a-z_]+)/) as TaskStatus | null;

  if (!title) return <PlainCard item={item} />;
  return (
    <div className={CARD}>
      <div className="text-sm font-semibold text-ink">{title}</div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {assignee ? <AssigneeTag type={assignee} /> : null}
        {severity ? <SeverityBadge severity={severity} /> : null}
        {status ? <StatusPill status={status} /> : null}
      </div>
    </div>
  );
}

function FlagCard({ item }: { item: string }) {
  // `[<signal_type>] (hard) <title>`
  const m = item.match(/^\[([a-z_]+)\]\s*(\(hard\))?\s*(.*)$/);
  const sig = m?.[1] && isSignal(m[1]) ? (m[1] as SignalType) : null;
  const hard = !!m?.[2];
  const text = m?.[3] ?? item;

  return (
    <div className={`${CARD} ${hard ? "border-red-200 bg-red-50/40" : "border-amber-200 bg-amber-50/40"}`}>
      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
        {sig ? <SignalTypeTag type={sig} /> : null}
        <HardSoftChip hard={hard} />
      </div>
      <div className="text-sm font-medium text-ink">
        <MarkdownInline text={text} />
      </div>
    </div>
  );
}

function DecisionCard({ item }: { item: string }) {
  // `**<action>** on task <id>: <note> — amendment: <amend>`
  const m = item.match(/^\*\*(\w+)\*\*\s*on task\s*(\S+):\s*(.*)$/);
  const action = (m?.[1] ?? "").toLowerCase();
  const taskId = m?.[2] ?? null;
  const note = m?.[3]?.trim() ?? null;

  if (!m) return <PlainCard item={item} />;

  const tone =
    action === "approve"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
      : action === "reject"
        ? "bg-red-50 text-red-700 ring-red-200"
        : "bg-amber-50 text-amber-700 ring-amber-200";
  const verb = action === "approve" ? "Signed off" : action === "reject" ? "Rejected" : "Amended";

  return (
    <div className={CARD}>
      <div className="flex items-center gap-2">
        <span
          className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${tone}`}
        >
          {verb}
        </span>
        {taskId ? (
          <span className="font-mono text-[11px] text-muted">task {taskId.slice(0, 8)}</span>
        ) : null}
      </div>
      {note ? (
        <p className="mt-2 text-sm text-ink-soft">
          <MarkdownInline text={note} />
        </p>
      ) : (
        <p className="mt-2 text-sm text-muted">No note recorded.</p>
      )}
    </div>
  );
}

function CarryCard({ item }: { item: string }) {
  return (
    <div className={`${CARD} flex items-start gap-3`}>
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border border-amber-300 bg-amber-50 text-[11px] text-amber-700">
        ☐
      </span>
      <p className="text-sm leading-relaxed text-ink-soft">
        <MarkdownInline text={item} />
      </p>
    </div>
  );
}

function PlainCard({ item }: { item: string }) {
  return (
    <div className={CARD}>
      <p className="text-sm leading-relaxed text-ink-soft">
        <MarkdownInline text={item} />
      </p>
    </div>
  );
}

// --- Parsing -------------------------------------------------------------------------------------

function parseSections(body: string): Section[] {
  const lines = body.replace(/\r\n/g, "\n").split("\n");
  const sections: Section[] = [];
  let cur: Section | null = null;

  for (const raw of lines) {
    const line = raw.trimEnd();
    const h = line.match(/^##\s+(.*)$/);
    if (h) {
      const full = h[1].trim();
      const cm = full.match(/^(.*?)\s*\((\d+)\)\s*$/);
      cur = {
        title: cm ? cm[1].trim() : full,
        count: cm ? Number(cm[2]) : null,
        items: [],
        prose: [],
      };
      sections.push(cur);
      continue;
    }
    if (!cur) {
      if (line.trim() === "") continue;
      cur = { title: "", count: null, items: [], prose: [] };
      sections.push(cur);
    }
    const b = line.match(/^[-*]\s+(.*)$/);
    if (b) cur.items.push(b[1].trim());
    else if (line.trim() !== "") cur.prose.push(line);
  }
  return sections;
}

function kindOf(title: string): "tasks" | "flags" | "decisions" | "carry" | "generic" {
  const t = title.toLowerCase();
  if (t.includes("task")) return "tasks";
  if (t.includes("flag")) return "flags";
  if (t.includes("decision")) return "decisions";
  if (t.includes("carry")) return "carry";
  return "generic";
}

function pick(text: string, re: RegExp): string | null {
  const m = text.match(re);
  return m ? m[1] : null;
}

function isSignal(s: string): s is SignalType {
  return (
    s === "citation_support" || s === "precedent_deviation" || s === "multi_run_disagreement"
  );
}
