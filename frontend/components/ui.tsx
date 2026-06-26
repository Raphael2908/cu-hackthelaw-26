"use client";

import type { ReactNode } from "react";
import type { Severity, SignalType, TaskStatus } from "@/lib/types";

// --- Severity badge: high=red, medium=amber, low=slate ---
export function SeverityBadge({ severity }: { severity: Severity }) {
  const map: Record<Severity, string> = {
    high: "bg-red-50 text-red-700 ring-red-200",
    medium: "bg-amber-50 text-amber-700 ring-amber-200",
    low: "bg-slate-100 text-slate-600 ring-slate-200",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1 ring-inset ${map[severity]}`}
    >
      {severity}
    </span>
  );
}

// --- Hard / soft flag chip. Hard = always-surfaced (red); soft = attention (amber). ---
export function HardSoftChip({ hard }: { hard: boolean }) {
  return hard ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-600 px-2 py-0.5 text-[11px] font-semibold text-white">
      HARD FLAG
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800 ring-1 ring-inset ring-amber-200">
      soft signal
    </span>
  );
}

export const SIGNAL_LABEL: Record<SignalType, string> = {
  citation_support: "Citation support",
  precedent_deviation: "Precedent deviation",
  multi_run_disagreement: "Multi-run disagreement",
};

export function SignalTypeTag({ type }: { type: SignalType }) {
  return (
    <span className="inline-flex items-center rounded-md bg-brand-soft px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-brand">
      {SIGNAL_LABEL[type]}
    </span>
  );
}

const STATUS_STYLES: Partial<Record<TaskStatus, string>> = {
  in_review: "bg-amber-50 text-amber-700 ring-amber-200",
  cleared: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  signed_off: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  escalated: "bg-red-50 text-red-700 ring-red-200",
  dispatched: "bg-slate-100 text-slate-600 ring-slate-200",
  in_progress: "bg-slate-100 text-slate-600 ring-slate-200",
  proposed: "bg-slate-100 text-slate-600 ring-slate-200",
  approved: "bg-blue-50 text-blue-700 ring-blue-200",
};

export function StatusPill({ status }: { status: TaskStatus }) {
  const cls = STATUS_STYLES[status] ?? "bg-slate-100 text-slate-600 ring-slate-200";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function AssigneeTag({ type }: { type: "human" | "ai" | "hybrid" }) {
  const map = {
    ai: "bg-violet-50 text-violet-700 ring-violet-200",
    human: "bg-sky-50 text-sky-700 ring-sky-200",
    hybrid: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  } as const;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${map[type]}`}
    >
      {type}
    </span>
  );
}

// --- Card container ---
export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-line bg-paper shadow-sm ${className}`}
    >
      {children}
    </div>
  );
}

// --- A labelled stat (used for the three independent signals). ---
export function SignalStat({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  const toneCls = {
    neutral: "text-ink",
    good: "text-emerald-600",
    warn: "text-amber-600",
    bad: "text-red-600",
  }[tone];
  return (
    <div className="rounded-lg border border-line bg-canvas px-3 py-2.5">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${toneCls}`}>{value}</div>
      {hint ? <div className="mt-0.5 text-[11px] leading-tight text-muted">{hint}</div> : null}
    </div>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
  title,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary" | "danger" | "ghost" | "approve";
  type?: "button" | "submit";
  title?: string;
  className?: string;
}) {
  const variants = {
    primary: "bg-brand text-white hover:bg-[#16304f] disabled:bg-slate-300",
    approve: "bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-slate-300",
    secondary:
      "bg-white text-ink ring-1 ring-inset ring-line hover:bg-canvas disabled:text-slate-400",
    danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-slate-300",
    ghost: "bg-transparent text-brand hover:bg-brand-soft disabled:text-slate-400",
  }[variant];
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${variants} ${className}`}
    >
      {children}
    </button>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 py-10 text-sm text-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand" />
      {label}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {message}
    </div>
  );
}

export function pct(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${Math.round(n * 100)}%`;
}
