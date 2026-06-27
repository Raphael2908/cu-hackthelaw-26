"use client";

import { type ReactNode, useCallback, useEffect, useState } from "react";
import { decideTask, getAssociates, getTaskDetail, postMessage, reassignTask } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { Associate, Flag, FlagSourceRef, FlagWorkRef, TaskDetail } from "@/lib/types";
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
import { MarkdownEditor } from "./MarkdownEditor";
import { Markdown } from "./Markdown";

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
  // The source drawer opens either a flag (both sides) or a plain corpus doc (an attachment).
  const [source, setSource] = useState<{
    sourceRef: FlagSourceRef;
    workRef?: FlagWorkRef | null;
  } | null>(null);
  const [role, setRole] = useState<Role>("partner");

  const [action, setAction] = useState<Action | null>(null);
  const [note, setNote] = useState("");
  const [amendment, setAmendment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [reply, setReply] = useState("");
  const [replying, setReplying] = useState(false);

  // Reassign — a partner-only delegation action, separate from sign-off.
  const [reassigning, setReassigning] = useState(false);
  const [raType, setRaType] = useState<"human" | "ai" | "hybrid">("human");
  const [raAssignee, setRaAssignee] = useState<string>("");
  const [raNote, setRaNote] = useState("");
  const [raBusy, setRaBusy] = useState(false);
  const [associates, setAssociates] = useState<Associate[] | null>(null);

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
    setReassigning(false);
    setRaType("human");
    setRaAssignee("");
    setRaNote("");
  }, [load, taskId]);

  // Lazily load the associate registry the first time the partner opens the reassign panel.
  const openReassign = async () => {
    setAction(null);
    setReassigning(true);
    if (associates === null) {
      try {
        setAssociates(await getAssociates());
      } catch {
        setAssociates([]);
      }
    }
  };

  const doReassign = async () => {
    setRaBusy(true);
    setError(null);
    try {
      await reassignTask(taskId, {
        assignee_type: raType,
        // AI work has no associate; a human/hybrid reassign may leave it unassigned (empty → omit).
        assignee_id: raType === "ai" || !raAssignee ? undefined : raAssignee,
        note: raNote,
      });
      setReassigning(false);
      setRaNote("");
      setRaAssignee("");
      await load();
      onDecided();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not reassign the task.");
    } finally {
      setRaBusy(false);
    }
  };

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

  const { task, submission, flags, risk, messages, attachments } = detail;
  const decided = task.status === "signed_off" || task.status === "escalated";
  const awaitingClar = task.status === "awaiting_clarification";
  const returned = task.status === "returned";
  const reviewable = !decided && !awaitingClar && !returned;
  const isPartner = role === "partner";
  const hasThread = (messages?.length ?? 0) > 0;

  return (
    <div>
      {/* Step 1 — who produced it and how far it has travelled (header + chain of custody, merged) */}
      <Step n={1} title="Who did it & where it stands">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <SeverityBadge severity={task.severity} />
          <AssigneeTag type={task.assignee_type} />
          <StatusPill status={task.status} />
        </div>
        <h2 className="text-base font-semibold text-ink">{task.title}</h2>
        <p className="mt-1 text-sm text-muted">{task.description}</p>
        <div className="mt-3">
          <TaskTrace bare task={task} auditHref={`/cases/${task.case_id}/audit?task=${task.id}`} />
        </div>
      </Step>

      {/* Step 2 — the worker's output */}
      <Step
        n={2}
        title="What was produced"
        hint={
          submission
            ? `by ${submission.produced_by === "ai" ? "the AI worker" : `a ${submission.produced_by} worker`}`
            : undefined
        }
      >
        {submission ? (
          <div>
            <Markdown content={submission.summary} />

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
          </div>
        ) : (
          <p className="text-sm text-muted">No work has been submitted for this task yet.</p>
        )}

        {/* Documents the associate attached to their work — each openable in the source drawer. */}
        {attachments.length > 0 ? (
          <div className="mt-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">
              Associate&apos;s attachments ({attachments.length})
            </div>
            <ul className="mt-1.5 space-y-1.5">
              {attachments.map((a) => (
                <li
                  key={a.id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-line bg-canvas px-3 py-1.5"
                >
                  <span className="flex min-w-0 items-center gap-1.5 text-sm text-ink-soft">
                    <span aria-hidden>📄</span>
                    <span className="truncate">{a.title}</span>
                  </span>
                  <Button
                    variant="secondary"
                    onClick={() => setSource({ sourceRef: { corpus_document_id: a.id } })}
                    className="!py-1 !text-[11px]"
                  >
                    View →
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Step>

      {/* Step 3 — the three checks (the steer) and the flags (the concrete things to verify), merged.
          Each signal stays individually visible with its number; never collapsed into a verdict. */}
      <Step
        n={3}
        title="What to check"
        hint="Three independent checks point you where to look — none is a verdict."
      >
        {risk ? (
          <div className="space-y-3">
            <p className="text-xs text-muted">
              Overall:{" "}
              <span className={`font-semibold ${TONE_TEXT[overallReading(risk.uncertainty).tone]}`}>
                {overallReading(risk.uncertainty).text}
              </span>
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

            <div className="flex items-center justify-between rounded-lg border border-line bg-canvas px-3 py-2 text-xs">
              <span className="text-muted">Where this sits on your list</span>
              <span className="font-semibold text-ink">{priorityBand(risk.priority).label}</span>
            </div>

            {risk.has_hard_flag ? (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs font-medium text-red-700">
                A must-check issue was found — shown no matter how low-risk the task.
              </div>
            ) : null}
          </div>
        ) : null}

        {/* The concrete things to verify, each linking to its source */}
        <div className={risk ? "mt-4 border-t border-line pt-4" : ""}>
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted">
            Things to verify ({flags.length})
          </div>
          {flags.length === 0 ? (
            <div className="rounded-lg border border-line bg-canvas px-4 py-3 text-sm text-muted">
              Nothing flagged. (Work done by a person isn&apos;t graded by the automated checks.)
            </div>
          ) : (
            <div className="space-y-3">
              {flags.map((flag) => (
                <FlagCard
                  key={flag.id}
                  flag={flag}
                  onView={() => setSource({ sourceRef: flag.source_ref, workRef: flag.work_ref })}
                />
              ))}
            </div>
          )}
        </div>
      </Step>

      {/* Conversation with the associate — contextual, aligned under the step spine */}
      {hasThread || awaitingClar || returned ? (
        <div className="ml-10 pb-6">
          <div className="rounded-xl border border-line bg-canvas p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">Conversation with the associate</h3>
              {awaitingClar ? (
                <span className="rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-semibold text-violet-700 ring-1 ring-inset ring-violet-200">
                  message awaiting your reply
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
                  Reply to the associate&apos;s question or concern
                </div>
                <MarkdownEditor
                  value={reply}
                  onChange={setReply}
                  rows={2}
                  placeholder="Type your reply — this sends the task back to the associate…"
                />
                <Button onClick={sendReply} disabled={replying || !reply.trim()}>
                  {replying ? "Sending…" : "Send reply & return to associate"}
                </Button>
              </div>
            ) : awaitingClar && !isPartner ? (
              <div className="mt-3 rounded-lg border border-line bg-white px-4 py-2.5 text-xs text-muted">
                Waiting on the partner to answer. Switch to Partner in the header to reply.
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Step 4 — the decision: the focal endpoint of the review path */}
      <Step n={4} title="Your decision" focal last>
        <div className="rounded-xl border-2 border-brand/30 bg-paper p-4 shadow-sm">
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
              The associate has raised a question or concern (above). Reply to hand the task back —
              you&apos;ll sign off once they resubmit.
            </p>
          ) : !isPartner ? (
            <div className="rounded-lg border border-line bg-canvas px-4 py-3 text-sm text-muted">
              Sign-off is partner-only. Switch to Partner in the header to approve, amend, or reject.
            </div>
          ) : (
            <>
              <p className="mb-3 text-xs text-muted">
                The points above are things to check, not verdicts. Approve or amend to sign off;{" "}
                <span className="font-medium text-ink-soft">
                  reject sends it back to the associate
                </span>{" "}
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
                  <MarkdownEditor
                    value={note}
                    onChange={setNote}
                    rows={2}
                    placeholder={
                      action === "reject"
                        ? "What should the associate fix? (sent to them with the task)…"
                        : "Note (recorded with your decision)…"
                    }
                  />
                  {action === "amend" ? (
                    <MarkdownEditor
                      value={amendment}
                      onChange={setAmendment}
                      rows={3}
                      placeholder="Amendment text…"
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

          {/* Reassign — partner-only delegation, separate from sign-off. Available until the work
              is accepted (signed off). Re-dispatches under the partner's name; never automatic. */}
          {isPartner && task.status !== "signed_off" ? (
            <div className="mt-4 border-t border-line pt-3">
              {!reassigning ? (
                <button
                  onClick={openReassign}
                  className="text-xs font-semibold text-brand hover:underline"
                >
                  Reassign this work…
                </button>
              ) : (
                <div className="space-y-2.5 rounded-lg border border-line bg-canvas p-3">
                  <p className="text-xs text-muted">
                    Move this work to a person or the AI. It re-dispatches under your name and is
                    recorded in the audit log — never reassigned automatically.
                  </p>
                  <div className="flex flex-wrap items-center gap-3">
                    <label className="flex items-center gap-1.5 text-xs font-medium text-ink-soft">
                      To
                      <select
                        value={raType}
                        onChange={(e) => {
                          setRaType(e.target.value as "human" | "ai" | "hybrid");
                          if (e.target.value === "ai") setRaAssignee("");
                        }}
                        className="rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
                      >
                        <option value="human">A person (human)</option>
                        <option value="hybrid">Hybrid (AI first pass → person)</option>
                        <option value="ai">The AI</option>
                      </select>
                    </label>
                    {raType !== "ai" ? (
                      <label className="flex items-center gap-1.5 text-xs font-medium text-ink-soft">
                        Associate
                        <select
                          value={raAssignee}
                          onChange={(e) => setRaAssignee(e.target.value)}
                          className="max-w-[16rem] truncate rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
                        >
                          <option value="">Unassigned (any associate)</option>
                          {(associates ?? []).map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.name} — {a.practice_area} ({a.current_load}/{a.capacity})
                            </option>
                          ))}
                        </select>
                      </label>
                    ) : null}
                  </div>
                  <textarea
                    value={raNote}
                    onChange={(e) => setRaNote(e.target.value)}
                    rows={2}
                    placeholder="Why are you reassigning? (recorded in the audit log)…"
                    className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
                  />
                  <div className="flex items-center gap-2">
                    <Button onClick={doReassign} disabled={raBusy}>
                      {raBusy ? "Reassigning…" : "Confirm reassign"}
                    </Button>
                    <Button variant="ghost" onClick={() => setReassigning(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ) : null}

          {error ? (
            <div className="mt-3">
              <ErrorNote message={error} />
            </div>
          ) : null}
        </div>
      </Step>

      <SourceDrawer
        sourceRef={source?.sourceRef ?? null}
        workRef={source?.workRef ?? null}
        onClose={() => setSource(null)}
      />
    </div>
  );
}

// One step of the item review path. A numbered badge plus a connecting spine give the panels a clear
// reading order (continuity) so the partner follows produce → check → decide instead of facing six
// rival cards. Steps 1–3 are light; the focal step (the decision) is emphasised; `last` ends the spine.
function Step({
  n,
  title,
  hint,
  focal,
  last,
  children,
}: {
  n: number;
  title: string;
  hint?: string;
  focal?: boolean;
  last?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
            focal ? "bg-brand text-white" : "bg-brand-soft text-brand"
          }`}
        >
          {n}
        </div>
        {!last ? <div className="mt-1 w-px flex-1 bg-line" /> : null}
      </div>
      <div className={`min-w-0 flex-1 ${last ? "" : "pb-6"}`}>
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {hint ? <p className="mt-0.5 text-[11px] text-muted">{hint}</p> : null}
        <div className="mt-2.5">{children}</div>
      </div>
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
