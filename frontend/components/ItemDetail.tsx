"use client";

import { useCallback, useEffect, useState } from "react";
import { decideTask, getTaskDetail, postMessage } from "@/lib/api";
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
  SignalTypeTag,
  Spinner,
  StatusPill,
  pct,
} from "./ui";
import {
  citationReading,
  deviationReading,
  disagreementReading,
  overallReading,
  priorityBand,
  TONE_TEXT,
  type Reading,
} from "@/lib/plain";
import { SourceDrawer } from "./SourceDrawer";
import { TaskTrace } from "./TaskTrace";
import { MessageThread } from "./MessageThread";

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
  const [reply, setReply] = useState("");
  const [replying, setReplying] = useState(false);

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
    setReply("");
  }, [load, taskId]);

  const sendReply = async () => {
    if (!reply.trim()) return;
    setReplying(true);
    setError(null);
    try {
      await postMessage(taskId, { body: reply });
      setReply("");
      await load();
      onDecided();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not send the reply.");
    } finally {
      setReplying(false);
    }
  };

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

  const { task, submission, flags, risk, messages } = detail;
  const decided = task.status === "signed_off" || task.status === "escalated";
  const awaitingClar = task.status === "awaiting_clarification";
  const returned = task.status === "returned";
  const reviewable = !decided && !awaitingClar && !returned;
  const isPartner = role === "partner";
  const hasThread = (messages?.length ?? 0) > 0;

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

      {/* Chain of custody — who holds the work and how far it has travelled (walkthrough G2) */}
      <TaskTrace task={task} auditHref={`/cases/${task.case_id}/audit?task=${task.id}`} />

      {/* Three independent checks — each read in plain language, the number kept alongside.
          Never collapsed into a single pass/fail. */}
      {risk ? (
        <Panel className="p-5">
          <div className="mb-1 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">What the checks found</h3>
            <span className="text-[11px] text-muted">Three separate checks — none is a verdict.</span>
          </div>
          <p className="mb-3 text-xs text-muted">
            Overall:{" "}
            <span className={`font-semibold ${TONE_TEXT[overallReading(risk.uncertainty).tone]}`}>
              {overallReading(risk.uncertainty).text}
            </span>
            . This is a steer for where to look — you decide.
          </p>

          <div className="space-y-2">
            <CheckRow
              label="Citations"
              reading={citationReading(risk.citation_support_rate)}
              detail={`${pct(risk.citation_support_rate)} of cited sources support the claim`}
            />
            <CheckRow
              label="Firm standard"
              reading={deviationReading(risk.deviation_score)}
              detail={`${pct(risk.deviation_score)} distance from your firm's standard wording`}
            />
            <CheckRow
              label="Consistency"
              reading={disagreementReading(risk.disagreement_score)}
              detail={`${pct(risk.disagreement_score)} disagreement when the review was re-run`}
            />
          </div>

          <div className="mt-3 flex items-center justify-between rounded-lg border border-line bg-canvas px-3 py-2 text-xs">
            <span className="text-muted">Where this sits on your list</span>
            <span className="font-semibold text-ink">{priorityBand(risk.priority).label}</span>
          </div>

          {risk.has_hard_flag ? (
            <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700">
              A must-check issue was found — shown no matter how low-risk the task.
            </div>
          ) : null}
        </Panel>
      ) : null}

      {/* Worker submission */}
      {submission ? (
        <Panel className="p-5">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">The work that was produced</h3>
            <span className="text-[11px] text-muted">
              by {submission.produced_by === "ai" ? "the AI worker" : `a ${submission.produced_by} worker`}
            </span>
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
            <MetaList title="Clauses it relied on" items={submission.clauses_relied_on} />
            <MetaList title="Sources it used" items={submission.audit_sources} mono />
          </div>
        </Panel>
      ) : (
        <Panel className="p-5 text-sm text-muted">
          No work has been submitted for this task yet.
        </Panel>
      )}

      {/* Flag panel */}
      <Panel className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-ink">
            Points to check ({flags.length})
          </h3>
          <span className="text-[11px] text-muted">Things to verify — each links to its source.</span>
        </div>
        {flags.length === 0 ? (
          <div className="rounded-lg border border-line bg-canvas px-4 py-3 text-sm text-muted">
            Nothing flagged. (Work done by a person isn&apos;t graded by the automated checks.)
          </div>
        ) : (
          <div className="space-y-3">
            {flags.map((flag) => (
              <FlagCard key={flag.id} flag={flag} onView={() => setSource(flag.source_ref)} />
            ))}
          </div>
        )}
      </Panel>

      {/* Conversation with the associate — the ping-pong record */}
      {hasThread || awaitingClar || returned ? (
        <Panel className="p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">Conversation with the associate</h3>
            {awaitingClar ? (
              <span className="rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-semibold text-violet-700 ring-1 ring-inset ring-violet-200">
                question awaiting your reply
              </span>
            ) : returned ? (
              <span className="rounded-full bg-orange-50 px-2 py-0.5 text-[11px] font-semibold text-orange-700 ring-1 ring-inset ring-orange-200">
                with the associate
              </span>
            ) : null}
          </div>
          <MessageThread messages={messages} />

          {awaitingClar && isPartner ? (
            <div className="mt-4 space-y-2 border-t border-line pt-4">
              <div className="text-xs font-medium text-ink-soft">
                Answer the associate&apos;s question
              </div>
              <textarea
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                rows={2}
                placeholder="Type your answer — this sends the task back to the associate…"
                className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
              />
              <Button onClick={sendReply} disabled={replying || !reply.trim()}>
                {replying ? "Sending…" : "Send answer & return to associate"}
              </Button>
            </div>
          ) : awaitingClar && !isPartner ? (
            <div className="mt-3 rounded-lg border border-line bg-canvas px-4 py-2.5 text-xs text-muted">
              Waiting on the partner to answer. Switch to Partner in the header to reply.
            </div>
          ) : null}
        </Panel>
      ) : null}

      {/* Action panel — what the partner can do depends on where the task is */}
      <Panel className="p-5">
        <div className="mb-1 flex items-center gap-2">
          <h3 className="text-sm font-semibold text-ink">Your decision</h3>
        </div>

        {decided ? (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            Decision recorded — task is{" "}
            <span className="font-semibold">{task.status.replace(/_/g, " ")}</span>. This is written
            to the signed, hash-chained accountability log.
          </div>
        ) : returned ? (
          <div className="rounded-lg border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-orange-800">
            Sent back to the associate for rework. You&apos;ll see it here again — with your note in
            the thread above — once they resubmit.
          </div>
        ) : awaitingClar ? (
          <p className="text-xs text-muted">
            The associate has a question (above). Answer it to hand the task back — you&apos;ll
            sign off once they resubmit.
          </p>
        ) : !isPartner ? (
          <div className="rounded-lg border border-line bg-canvas px-4 py-3 text-sm text-muted">
            Sign-off is partner-only. Switch to Partner in the header to approve, amend, or reject.
          </div>
        ) : (
          <>
            <p className="mb-3 text-xs text-muted">
              The points above are things to check, not verdicts. Approve or amend to sign off;{" "}
              <span className="font-medium text-ink-soft">reject sends it back to the associate</span>{" "}
              for rework. Nothing is approved automatically.
            </p>
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
                Reject &amp; send back
              </Button>
            </div>

            {action ? (
              <div className="mt-3 space-y-2">
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  placeholder={
                    action === "reject"
                      ? "What should the associate fix? (sent to them with the task)…"
                      : "Note (recorded with your decision)…"
                  }
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
                    {submitting
                      ? "Recording…"
                      : action === "reject"
                        ? "Confirm & send back"
                        : `Confirm ${action}`}
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

// One check, read in plain language. The measured number stays visible underneath (secondary), so a
// partner who wants the figure has it without it leading. A coloured dot encodes good/attention.
function CheckRow({
  label,
  reading,
  detail,
}: {
  label: string;
  reading: Reading;
  detail: string;
}) {
  const dot = {
    good: "bg-emerald-500",
    warn: "bg-amber-500",
    bad: "bg-red-500",
    neutral: "bg-slate-400",
  }[reading.tone];
  return (
    <div className="flex items-start gap-3 rounded-lg border border-line bg-canvas px-3 py-2.5">
      <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${dot}`} />
      <div className="min-w-0">
        <div className="text-[11px] font-medium uppercase tracking-wide text-muted">{label}</div>
        <div className={`text-sm font-semibold ${TONE_TEXT[reading.tone]}`}>{reading.text}</div>
        <div className="mt-0.5 text-[11px] text-muted">{detail}</div>
      </div>
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
