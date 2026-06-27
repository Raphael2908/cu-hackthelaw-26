"use client";

import Link from "next/link";
import type { Task, TaskStatus } from "@/lib/types";
import { AssigneeTag } from "./ui";

// Chain of custody for one task (cognitive-walkthrough gap G2 — see DESIGN.md).
// A partner tracing delegated work needs to see, at a glance, WHO holds the work and HOW FAR it has
// travelled. We render the lifecycle as a stepper plus the assignee identity, and a deep link into
// the case audit trail pre-filtered to this task (H7 accelerator).

const MILESTONES: { key: string; label: string; hint: string }[] = [
  { key: "dispatched", label: "Dispatched", hint: "assigned & sent to the worker" },
  { key: "submitted", label: "Submitted", hint: "worker produced the output" },
  { key: "checked", label: "Checked", hint: "checker raised any flags" },
  { key: "in_review", label: "In review", hint: "in the partner's queue" },
  { key: "decided", label: "Decided", hint: "signed off, amended, or escalated" },
];

// How far along the lifecycle a given status has reached (index into MILESTONES; -1 = pre-dispatch).
function reachedIndex(status: TaskStatus): number {
  switch (status) {
    case "proposed":
    case "approved":
      return -1;
    case "dispatched":
    case "in_progress":
      return 0;
    case "submitted":
      return 1;
    case "returned": // sent back to the associate — sits between submit and review
    case "awaiting_clarification":
      return 1;
    case "checked":
      return 2;
    case "in_review":
      return 3;
    case "signed_off":
    case "escalated":
    case "cleared":
      return 4;
    default:
      return -1;
  }
}

export function TaskTrace({ task, auditHref }: { task: Task; auditHref: string }) {
  const reached = reachedIndex(task.status);

  return (
    <div className="rounded-xl border border-line bg-paper p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">Chain of custody</h3>
        <Link
          href={auditHref}
          className="text-xs font-semibold text-brand underline-offset-2 hover:underline"
        >
          View this task&apos;s full trail in Audit →
        </Link>
      </div>

      {/* Who holds the work */}
      <div className="mb-4 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>Owned by</span>
        <AssigneeTag type={task.assignee_type} />
        <span className="font-medium text-ink-soft">
          {task.assignee_id ?? (task.assignee_type === "ai" ? "AI worker" : "unassigned")}
        </span>
        {task.assignee_type === "hybrid" ? (
          <span className="text-[11px]">· human owns the result, AI assists</span>
        ) : null}
      </div>

      {/* Lifecycle stepper */}
      <ol className="flex items-start gap-1">
        {MILESTONES.map((m, i) => {
          const done = i < reached || (i === 4 && reached === 4);
          const current = i === reached && reached < 4;
          const state = done ? "done" : current ? "current" : "todo";
          return (
            <li key={m.key} className="flex flex-1 flex-col items-center text-center">
              <div className="flex w-full items-center">
                <span
                  className={`h-0.5 flex-1 ${i === 0 ? "bg-transparent" : i <= reached ? "bg-emerald-400" : "bg-line"}`}
                />
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                    state === "done"
                      ? "bg-emerald-500 text-white"
                      : state === "current"
                        ? "bg-brand text-white ring-4 ring-brand-soft"
                        : "bg-canvas text-muted ring-1 ring-inset ring-line"
                  }`}
                >
                  {state === "done" ? "✓" : i + 1}
                </span>
                <span
                  className={`h-0.5 flex-1 ${i === MILESTONES.length - 1 ? "bg-transparent" : i < reached ? "bg-emerald-400" : "bg-line"}`}
                />
              </div>
              <div
                className={`mt-1.5 text-[11px] font-semibold ${
                  state === "todo" ? "text-muted" : "text-ink"
                }`}
              >
                {m.label}
              </div>
              <div className="mt-0.5 text-[10px] leading-tight text-muted">{m.hint}</div>
            </li>
          );
        })}
      </ol>

      {reached === -1 ? (
        <p className="mt-3 text-[11px] text-muted">
          Not yet dispatched — this task is still part of an unapproved plan.
        </p>
      ) : null}
    </div>
  );
}
