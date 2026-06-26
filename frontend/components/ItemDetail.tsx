"use client";

import { useCallback, useEffect, useState } from "react";
import { decideTask, getTaskDetail } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { Flag, FlagSourceRef, TaskDetail } from "@/lib/types";
import { getRole, subscribeRole, type Role } from "@/lib/role";
import {
  AssigneeTag,
  Button,
  ErrorNote,
  HardSoftChip,
  Panel,
  SeverityBadge,
  SignalStat,
  SignalTypeTag,
  Spinner,
  StatusPill,
  pct,
} from "./ui";
import { SourceDrawer } from "./SourceDrawer";

type Action = "approve" | "amend" | "reject";

export function ItemDetail({
  taskId,
  onDecided,
}: {
  taskId: string;
  onDecided: () => void;
}) {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<FlagSourceRef | null>(null);
  const [role, setRole] = useState<Role>("partner");

  const [action, setAction] = useState<Action | null>(null);
  const [note, setNote] = useState("");
  const [amendment, setAmendment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setRole(getRole());
    return subscribeRole(() => setRole(getRole()));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDetail(await getTaskDetail(taskId));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Failed to load item.");
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    load();
    setAction(null);
    setNote("");
    setAmendment("");
  }, [load, taskId]);

  const decide = async () => {
    if (!action) return;
    setSubmitting(true);
    setError(null);
    try {
      await decideTask(taskId, {
        action,
        note,
        amendment: action === "amend" ? amendment : undefined,
      });
      setAction(null);
      setNote("");
      setAmendment("");
      await load();
      onDecided();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not record the decision.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Panel className="p-5">
        <Spinner label="Opening item…" />
      </Panel>
    );
  }
  if (error && !detail) {
    return (
      <Panel className="p-5">
        <ErrorNote message={error} />
      </Panel>
    );
  }
  if (!detail) return null;

  const { task, submission, flags, risk } = detail;
  const decided = task.status === "signed_off" || task.status === "escalated";
  const isPartner = role === "partner";

  return (
    <div className="space-y-4">
      <Panel className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="mb-1.5 flex items-center gap-2">
              <SeverityBadge severity={task.severity} />
              <AssigneeTag type={task.assignee_type} />
              <StatusPill status={task.status} />
            </div>
            <h2 className="text-base font-semibold text-ink">{task.title}</h2>
            <p className="mt-1 text-sm text-muted">{task.description}</p>
          </div>
        </div>
      </Panel>

      {/* Three independent signals — never collapsed into one verdict */}
      {risk ? (
        <Panel className="p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">Uncertainty signals</h3>
            <span className="text-[11px] text-muted">
              Three independent checks. None is a pass/fail.
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <SignalStat
              label="Citation support"
              value={pct(risk.citation_support_rate)}
              hint="claims whose cited source supports them"
              tone={risk.citation_support_rate >= 0.999 ? "good" : "bad"}
            />
            <SignalStat
              label="Precedent deviation"
              value={pct(risk.deviation_score)}
              hint="distance from the firm standard"
              tone={risk.deviation_score >= 0.5 ? "warn" : "neutral"}
            />
            <SignalStat
              label="Multi-run disagreement"
              value={pct(risk.disagreement_score)}
              hint="divergence across repeated runs"
              tone={risk.disagreement_score >= 0.5 ? "warn" : "neutral"}
            />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <SignalStat
              label="Composite uncertainty"
              value={pct(risk.uncertainty)}
              hint="weighted blend — tunable, not load-bearing alone"
            />
            <SignalStat
              label="Queue priority"
              value={pct(risk.priority)}
              hint={`f(severity, uncertainty) · lane: ${risk.lane}`}
            />
          </div>
          {risk.has_hard_flag ? (
            <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700">
              Hard flag present — surfaced regardless of severity.
            </div>
          ) : null}
        </Panel>
      ) : null}

      {/* Worker submission */}
      {submission ? (
        <Panel className="p-5">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">Worker submission</h3>
            <span className="text-[11px] text-muted">produced by {submission.produced_by}</span>
          </div>
          <p className="text-sm text-ink-soft">{submission.summary}</p>

          {submission.findings.length > 0 ? (
            <div className="mt-4 space-y-2">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                Findings
              </div>
              {submission.findings.map((f) => (
                <div key={f.id} className="rounded-lg border border-line bg-canvas p-3">
                  <div className="text-xs font-semibold text-ink">{f.clause_ref}</div>
                  <p className="mt-0.5 text-sm text-ink-soft">{f.statement}</p>
                  {f.citation ? (
                    <div className="mt-1.5 font-mono text-[11px] text-muted">
                      cites {f.citation.celex} — “{f.citation.claim}”
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}

          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <MetaList title="Clauses relied on" items={submission.clauses_relied_on} />
            <MetaList title="Audit sources" items={submission.audit_sources} mono />
          </div>
        </Panel>
      ) : (
        <Panel className="p-5 text-sm text-muted">
          No submission yet for this task.
        </Panel>
      )}

      {/* Flag panel */}
      <Panel className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ink">
            Flags ({flags.length})
          </h3>
          <span className="text-[11px] text-muted">Each is a checkable observation.</span>
        </div>
        {flags.length === 0 ? (
          <div className="rounded-lg border border-line bg-canvas px-4 py-3 text-sm text-muted">
            No flags raised. (Human work product is not graded by the checker.)
          </div>
        ) : (
          <div className="space-y-3">
            {flags.map((flag) => (
              <FlagCard key={flag.id} flag={flag} onView={() => setSource(flag.source_ref)} />
            ))}
          </div>
        )}
      </Panel>

      {/* Decision controls — partner only */}
      <Panel className="p-5">
        <div className="mb-1 flex items-center gap-2">
          <h3 className="text-sm font-semibold text-ink">Your decision</h3>
        </div>
        <p className="mb-3 text-xs text-muted">
          The flags are observations. You are the decider — nothing here is auto-approved.
        </p>

        {decided ? (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            Decision recorded — task is{" "}
            <span className="font-semibold">{task.status.replace(/_/g, " ")}</span>. This is written
            to the signed, hash-chained accountability log.
          </div>
        ) : !isPartner ? (
          <div className="rounded-lg border border-line bg-canvas px-4 py-3 text-sm text-muted">
            Sign-off is partner-only. Switch to Partner in the header to approve, amend, or reject.
          </div>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              <Button
                variant={action === "approve" ? "approve" : "secondary"}
                onClick={() => setAction("approve")}
              >
                Approve
              </Button>
              <Button
                variant={action === "amend" ? "primary" : "secondary"}
                onClick={() => setAction("amend")}
              >
                Amend
              </Button>
              <Button
                variant={action === "reject" ? "danger" : "secondary"}
                onClick={() => setAction("reject")}
              >
                Reject
              </Button>
            </div>

            {action ? (
              <div className="mt-3 space-y-2">
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  placeholder="Note (recorded with your decision)…"
                  className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
                />
                {action === "amend" ? (
                  <textarea
                    value={amendment}
                    onChange={(e) => setAmendment(e.target.value)}
                    rows={3}
                    placeholder="Amendment text…"
                    className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
                  />
                ) : null}
                <div className="flex items-center gap-2">
                  <Button onClick={decide} disabled={submitting}>
                    {submitting ? "Recording…" : `Confirm ${action}`}
                  </Button>
                  <Button variant="ghost" onClick={() => setAction(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : null}
          </>
        )}
        {error ? (
          <div className="mt-3">
            <ErrorNote message={error} />
          </div>
        ) : null}
      </Panel>

      <SourceDrawer sourceRef={source} onClose={() => setSource(null)} />
    </div>
  );
}

function FlagCard({ flag, onView }: { flag: Flag; onView: () => void }) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        flag.hard ? "border-red-200 bg-red-50/40" : "border-amber-200 bg-amber-50/40"
      }`}
    >
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <SignalTypeTag type={flag.signal_type} />
        <HardSoftChip hard={flag.hard} />
      </div>
      <div className="text-sm font-semibold text-ink">{flag.title}</div>
      <p className="mt-0.5 text-sm text-ink-soft">{flag.description}</p>
      <div className="mt-2.5">
        <Button variant="secondary" onClick={onView} className="!py-1.5 !text-xs">
          View source →
        </Button>
      </div>
    </div>
  );
}

function MetaList({
  title,
  items,
  mono,
}: {
  title: string;
  items: string[];
  mono?: boolean;
}) {
  return (
    <div className="rounded-lg border border-line bg-canvas p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</div>
      {items.length === 0 ? (
        <div className="mt-1 text-xs text-muted">—</div>
      ) : (
        <ul className="mt-1.5 flex flex-wrap gap-1.5">
          {items.map((it) => (
            <li
              key={it}
              className={`rounded-md bg-white px-2 py-0.5 text-[11px] text-ink-soft ring-1 ring-inset ring-line ${
                mono ? "font-mono" : ""
              }`}
            >
              {it}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
