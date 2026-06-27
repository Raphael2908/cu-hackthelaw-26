"use client";

import { useCallback, useEffect, useState } from "react";
import { attachTaskDocuments, getInbox, postMessage, submitTask } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { InboxItem } from "@/lib/types";
import { getRole, subscribeRole, type Role } from "@/lib/role";
import {
  AssigneeTag,
  Button,
  ErrorNote,
  Panel,
  SeverityBadge,
  Spinner,
  StatusPill,
} from "@/components/ui";
import { MessageThread } from "@/components/MessageThread";
import { MarkdownEditor } from "@/components/MarkdownEditor";

export default function InboxPage() {
  const [items, setItems] = useState<InboxItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [role, setRole] = useState<Role>("partner");

  useEffect(() => {
    setRole(getRole());
    return subscribeRole(() => setRole(getRole()));
  }, []);

  const load = useCallback(() => {
    getInbox()
      .then(setItems)
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Failed to load inbox."));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <div className="mb-2 flex items-center gap-2">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">My inbox</h1>
        <AssigneeTag type="human" />
      </div>
      <p className="mb-6 max-w-2xl text-sm text-muted">
        Tasks assigned to you, awaiting submission. On hybrid tasks the AI runs a first pass, but you
        own and submit the result.
      </p>

      {role !== "associate" ? (
        <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-800">
          You&apos;re viewing the associate&apos;s workspace as <strong>Partner</strong>. Use the{" "}
          <strong>Partner / Associate</strong> toggle (top right) to switch views — submitting work is
          the associate&apos;s job.
        </div>
      ) : null}

      {error ? (
        <div className="mb-4">
          <ErrorNote message={error} />
        </div>
      ) : null}

      {items === null ? (
        <Spinner label="Loading inbox…" />
      ) : items.length === 0 ? (
        <Panel className="p-8 text-center text-sm text-muted">
          Inbox is empty. Approve a plan with human/hybrid tasks to populate it.
        </Panel>
      ) : (
        <ul className="space-y-5">
          {items.map((item) => (
            <InboxCard key={item.task.id} item={item} onSubmitted={load} />
          ))}
        </ul>
      )}
    </div>
  );
}

function InboxCard({ item, onSubmitted }: { item: InboxItem; onSubmitted: () => void }) {
  const { task, target_document, ai_first_pass, messages, attachments } = item;
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [asking, setAsking] = useState(false);
  const [question, setQuestion] = useState("");
  const [askingBusy, setAskingBusy] = useState(false);
  const [attaching, setAttaching] = useState(false);

  const returned = task.status === "returned";
  const waiting = task.status === "awaiting_clarification";
  const canWork = task.status === "dispatched" || task.status === "in_progress" || returned;
  const hasThread = (messages?.length ?? 0) > 0;

  const submit = async () => {
    if (!summary.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await submitTask(task.id, { summary, findings: [] });
      setSummary("");
      onSubmitted();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Submission failed.");
    } finally {
      setBusy(false);
    }
  };

  const onAttach = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    e.target.value = ""; // allow re-selecting the same file
    if (!files.length) return;
    setAttaching(true);
    setError(null);
    try {
      await attachTaskDocuments(task.id, files);
      onSubmitted(); // refresh so the new attachment shows
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Could not attach the file(s).");
    } finally {
      setAttaching(false);
    }
  };

  const ask = async () => {
    if (!question.trim()) return;
    setAskingBusy(true);
    setError(null);
    try {
      await postMessage(task.id, { body: question });
      setQuestion("");
      setAsking(false);
      onSubmitted();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not send your message.");
    } finally {
      setAskingBusy(false);
    }
  };

  return (
    <li>
      <Panel className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="mb-1.5 flex flex-wrap items-center gap-2">
              <SeverityBadge severity={task.severity} />
              <AssigneeTag type={task.assignee_type} />
              <StatusPill status={task.status} />
            </div>
            <h2 className="text-base font-semibold text-ink">{task.title}</h2>
            <p className="mt-0.5 text-sm text-muted">{task.description}</p>
          </div>
        </div>

        {/* Who does what — orient the associate before they read the blocks below. */}
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-line bg-canvas px-3 py-2 text-xs text-ink-soft">
          {task.assignee_type === "hybrid" ? (
            <>
              <OriginTag origin="ai" />
              <span>
                AI drafted a first pass — you verify, amend, and own the final submission.
              </span>
            </>
          ) : (
            <>
              <OriginTag origin="you" />
              <span>
                This task is yours — no AI pass. (Automated checks don&apos;t grade human work.)
              </span>
            </>
          )}
        </div>

        {/* The partner sent it back — make the reason impossible to miss. */}
        {returned ? (
          <div className="mt-3 rounded-lg border border-orange-200 bg-orange-50 px-4 py-3 text-sm text-orange-800">
            The partner sent this back for rework. Read their note in the conversation below, revise
            your submission, and resubmit.
          </div>
        ) : null}

        <div className="mt-3 rounded-lg border border-line bg-canvas p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Brief slice
          </div>
          <p className="mt-0.5 text-sm text-ink-soft">{task.input_brief_slice}</p>
        </div>

        {task.assignee_type === "hybrid" && task.ai_instruction ? (
          <div className="mt-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3">
            <div className="flex items-center gap-2">
              <OriginTag origin="ai" />
              <div className="text-[11px] font-semibold uppercase tracking-wide text-indigo-700">
                AI instruction
              </div>
            </div>
            <p className="mt-0.5 text-sm text-indigo-900">{task.ai_instruction}</p>
          </div>
        ) : null}

        {task.assignee_type === "hybrid" && task.human_instruction ? (
          <div className="mt-3 rounded-lg border border-sky-200 bg-sky-50 p-3">
            <div className="flex items-center gap-2">
              <OriginTag origin="you" />
              <div className="text-[11px] font-semibold uppercase tracking-wide text-sky-700">
                Your part
              </div>
            </div>
            <p className="mt-0.5 text-sm text-sky-900">{task.human_instruction}</p>
          </div>
        ) : null}

        {ai_first_pass ? (
          <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50/60 p-3">
            <div className="flex items-center gap-2">
              <OriginTag origin="ai" />
              <div className="text-[11px] font-semibold uppercase tracking-wide text-violet-700">
                AI first-pass review (you remain the owner)
              </div>
            </div>
            <p className="mt-1.5 text-[11px] leading-snug text-violet-700">
              A draft of checkable claims for you to verify and amend — not finished work, and never
              a verdict. You own the final submission.
            </p>
            <p className="mt-1 text-sm text-ink-soft">{ai_first_pass.summary}</p>
            {ai_first_pass.findings.length > 0 ? (
              <ul className="mt-2 space-y-1.5">
                {ai_first_pass.findings.map((f) => (
                  <li key={f.id} className="rounded-md bg-white px-2.5 py-1.5 ring-1 ring-inset ring-line">
                    <span className="text-xs font-semibold text-ink">{f.clause_ref}</span>
                    <span className="ml-1.5 text-xs text-ink-soft">{f.statement}</span>
                    {f.citation ? (
                      <span className="ml-1 font-mono text-[11px] text-muted">
                        ({f.citation.celex})
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}

        <details className="mt-3 rounded-lg border border-line bg-canvas">
          <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-brand">
            View target document — {target_document?.title ?? task.target_document_id}
          </summary>
          <p className="whitespace-pre-wrap border-t border-line px-3 py-2.5 text-sm leading-relaxed text-ink-soft">
            {target_document?.text ?? "Document text unavailable."}
          </p>
        </details>

        {/* Conversation with the partner */}
        {hasThread ? (
          <div className="mt-4 rounded-lg border border-line bg-canvas p-3.5">
            <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
              Conversation with the partner
            </div>
            <MessageThread messages={messages} />
          </div>
        ) : null}

        {/* Action area */}
        <div className="mt-4 border-t border-line pt-4">
          {waiting ? (
            <div className="rounded-lg border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-800">
              Your message is with the partner. The task will return here with their reply.
            </div>
          ) : (
            <>
              <div className="mb-1 flex items-center gap-2">
                <OriginTag origin="you" />
                <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                  {returned ? "Revise & resubmit" : "Your submission"}
                </div>
              </div>
              <MarkdownEditor
                value={summary}
                onChange={setSummary}
                rows={3}
                placeholder="Summarise your review and conclusion…"
              />

              {/* Supporting documents the associate attaches to their work — case+task-tagged. */}
              <div className="mt-2">
                <div className="flex flex-wrap items-center gap-2">
                  <label
                    className={`cursor-pointer rounded-lg px-2.5 py-1.5 text-xs font-semibold text-brand ring-1 ring-inset ring-line hover:bg-brand-soft ${
                      attaching || !canWork ? "pointer-events-none opacity-50" : ""
                    }`}
                  >
                    {attaching ? "Attaching…" : "📎 Attach files"}
                    <input
                      type="file"
                      multiple
                      accept=".pdf,.docx,.pptx,.txt,.md,.markdown"
                      onChange={onAttach}
                      disabled={attaching || !canWork}
                      className="hidden"
                    />
                  </label>
                  <span className="text-[11px] text-muted">
                    {attachments.length > 0
                      ? `${attachments.length} attached`
                      : "PDF, DOCX, PowerPoint, or text — supporting documents for your work."}
                  </span>
                </div>
                {attachments.length > 0 ? (
                  <ul className="mt-1.5 space-y-1">
                    {attachments.map((a) => (
                      <li key={a.id} className="flex items-center gap-1.5 text-xs text-ink-soft">
                        <span aria-hidden>📄</span>
                        <span className="truncate">{a.title}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>

              {error ? (
                <div className="mt-2">
                  <ErrorNote message={error} />
                </div>
              ) : null}
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Button onClick={submit} disabled={busy || !canWork || !summary.trim()}>
                  {busy ? "Submitting…" : returned ? "Resubmit work" : "Submit work"}
                </Button>
                {!asking ? (
                  <Button variant="secondary" onClick={() => setAsking(true)} disabled={!canWork}>
                    Message the partner
                  </Button>
                ) : null}
              </div>

              {asking ? (
                <div className="mt-3 space-y-2 rounded-lg border border-violet-200 bg-violet-50/50 p-3">
                  <div className="text-xs font-medium text-violet-800">
                    Raise a question or concern — this hands the task to them until they reply.
                  </div>
                  <MarkdownEditor
                    value={question}
                    onChange={setQuestion}
                    rows={2}
                    placeholder="Ask a question or raise a concern…"
                  />
                  <div className="flex items-center gap-2">
                    <Button onClick={ask} disabled={askingBusy || !question.trim()}>
                      {askingBusy ? "Sending…" : "Send to partner"}
                    </Button>
                    <Button variant="ghost" onClick={() => setAsking(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </Panel>
    </li>
  );
}

// Quiet "who produced this" marker — makes the AI-vs-human boundary visual, not
// just a colour. Reuses the rounded chip styling shared with AssigneeTag.
function OriginTag({ origin }: { origin: "ai" | "you" }) {
  const map = {
    ai: "bg-violet-50 text-violet-700 ring-violet-200",
    you: "bg-sky-50 text-sky-700 ring-sky-200",
  } as const;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ring-1 ring-inset ${map[origin]}`}
    >
      {origin === "ai" ? "AI" : "You"}
    </span>
  );
}
