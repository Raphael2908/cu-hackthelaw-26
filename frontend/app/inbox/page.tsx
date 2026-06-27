"use client";

import { useCallback, useEffect, useState } from "react";
import { getInbox, submitTask } from "@/lib/api";
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
} from "@/components/ui";

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
  const { task, target_document, ai_first_pass } = item;
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = async () => {
    if (!summary.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await submitTask(task.id, { summary, findings: [] });
      setDone(true);
      onSubmitted();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Submission failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li>
      <Panel className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="mb-1.5 flex items-center gap-2">
              <SeverityBadge severity={task.severity} />
              <AssigneeTag type={task.assignee_type} />
            </div>
            <h2 className="text-base font-semibold text-ink">{task.title}</h2>
            <p className="mt-0.5 text-sm text-muted">{task.description}</p>
          </div>
        </div>

        <div className="mt-3 rounded-lg border border-line bg-canvas p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Brief slice
          </div>
          <p className="mt-0.5 text-sm text-ink-soft">{task.input_brief_slice}</p>
        </div>

        {task.assignee_type === "hybrid" && task.ai_instruction ? (
          <div className="mt-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-indigo-700">
              AI instruction
            </div>
            <p className="mt-0.5 text-sm text-indigo-900">{task.ai_instruction}</p>
          </div>
        ) : null}

        {ai_first_pass ? (
          <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50/60 p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-violet-700">
              AI first-pass review (you remain the owner)
            </div>
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

        {/* Submit */}
        <div className="mt-4 border-t border-line pt-4">
          {done ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              Submitted. The work is placed by its up-front severity — the checker never grades human
              product.
            </div>
          ) : (
            <>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
                Your submission
              </div>
              <textarea
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                rows={3}
                placeholder="Summarise your review and conclusion…"
                className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
              />
              {error ? (
                <div className="mt-2">
                  <ErrorNote message={error} />
                </div>
              ) : null}
              <div className="mt-2">
                <Button onClick={submit} disabled={busy || !summary.trim()}>
                  {busy ? "Submitting…" : "Submit work"}
                </Button>
              </div>
            </>
          )}
        </div>
      </Panel>
    </li>
  );
}
