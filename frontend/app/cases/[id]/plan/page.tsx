"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  approvePlan,
  getCase,
  getCorpus,
  getPlan,
  patchTask,
  type TaskPatchBody,
} from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { AssigneeType, Case, CorpusDoc, Plan, Severity, Task } from "@/lib/types";
import { getRole, subscribeRole, type Role } from "@/lib/role";
import { AssigneeTag, Button, ErrorNote, Panel, SeverityBadge, Spinner } from "@/components/ui";
import { CaseSubNav } from "@/components/CaseSubNav";

export default function PlanPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [role, setRole] = useState<Role>("partner");
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [corpus, setCorpus] = useState<CorpusDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    setRole(getRole());
    return subscribeRole(() => setRole(getRole()));
  }, []);

  const load = useCallback(async () => {
    try {
      const [c, p, corp] = await Promise.all([getCase(id), getPlan(id), getCorpus()]);
      setCaseData(c);
      setPlan(p.plan);
      setTasks([...p.tasks].sort((a, b) => a.order_index - b.order_index));
      setCorpus(corp);
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.status === 404
            ? "No plan for this case yet. Generate one from the Cases page."
            : e.detail
          : "Failed to load plan."
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const corpusById = useMemo(() => {
    const m = new Map<string, CorpusDoc>();
    corpus.forEach((d) => m.set(d.id, d));
    return m;
  }, [corpus]);

  const approved = plan?.status === "approved";
  const editable = !approved && role === "partner";

  const onPatch = async (task: Task, body: TaskPatchBody) => {
    setSavingId(task.id);
    setError(null);
    try {
      const updated = await patchTask(task.id, body);
      setTasks((ts) => ts.map((t) => (t.id === task.id ? updated : t)));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not save the edit.");
    } finally {
      setSavingId(null);
    }
  };

  const onApprove = async () => {
    if (!plan) return;
    setApproving(true);
    setError(null);
    try {
      await approvePlan(plan.id);
      router.push(`/cases/${id}/cockpit`);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Approval failed.");
      setApproving(false);
    }
  };

  return (
    <div>
      <CaseSubNav caseId={id} title={caseData?.title} />
      <div className="mx-auto max-w-7xl px-6 py-6">
        {loading ? (
          <Spinner label="Loading plan…" />
        ) : (
          <>
            {/* Proposal banner */}
            <div
              className={`mb-5 flex flex-wrap items-center justify-between gap-4 rounded-xl border p-4 ${
                approved
                  ? "border-emerald-200 bg-emerald-50"
                  : "border-amber-200 bg-amber-50"
              }`}
            >
              <div className="flex items-start gap-3">
                <span className="mt-0.5 text-lg">{approved ? "✓" : "⚠"}</span>
                <div>
                  <div className="text-sm font-semibold text-ink">
                    {approved
                      ? "Plan approved — work has been dispatched."
                      : "This is a PROPOSAL. Nothing runs until you approve."}
                  </div>
                  <p className="mt-0.5 text-xs text-ink-soft">
                    {approved
                      ? `Approved by ${plan?.approved_by}. Editing is locked. Supervise the output in the cockpit.`
                      : "Edit assignees and severity below, then approve. Only on approval does the coordinator dispatch any task."}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {approved ? (
                  <Button onClick={() => router.push(`/cases/${id}/cockpit`)}>
                    Go to cockpit →
                  </Button>
                ) : (
                  <Button
                    variant="approve"
                    onClick={onApprove}
                    disabled={approving || role !== "partner"}
                    title={role !== "partner" ? "Only the partner can approve a plan" : undefined}
                  >
                    {approving ? "Approving…" : "Approve plan"}
                  </Button>
                )}
              </div>
            </div>

            {role !== "partner" && !approved ? (
              <div className="mb-4 rounded-lg border border-line bg-canvas px-4 py-2.5 text-xs text-muted">
                You are viewing as Associate. Editing and approval are partner-only — switch to
                Partner in the header to make changes.
              </div>
            ) : null}

            {error ? (
              <div className="mb-4">
                <ErrorNote message={error} />
              </div>
            ) : null}

            <Panel className="overflow-hidden">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-line bg-canvas text-left text-[11px] uppercase tracking-wide text-muted">
                    <th className="px-4 py-3 font-semibold">Task</th>
                    <th className="px-4 py-3 font-semibold">Type</th>
                    <th className="px-4 py-3 font-semibold">Assignee</th>
                    <th className="px-4 py-3 font-semibold">Severity</th>
                    <th className="px-4 py-3 font-semibold">Target document</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((t) => {
                    const doc = corpusById.get(t.target_document_id);
                    return (
                      <tr key={t.id} className="border-b border-line last:border-0 align-top">
                        <td className="px-4 py-3">
                          <div className="font-medium text-ink">{t.title}</div>
                          <div className="mt-0.5 max-w-md text-xs text-muted">{t.description}</div>
                          {t.ai_instruction ? (
                            <div className="mt-1.5 rounded-md bg-brand-soft px-2 py-1 text-[11px] text-brand">
                              AI instruction: {t.ai_instruction}
                            </div>
                          ) : null}
                        </td>
                        <td className="px-4 py-3 text-xs text-muted">
                          {t.task_type.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3">
                          {editable ? (
                            <select
                              value={t.assignee_type}
                              disabled={savingId === t.id}
                              onChange={(e) =>
                                onPatch(t, { assignee_type: e.target.value as AssigneeType })
                              }
                              className="select"
                            >
                              <option value="human">human</option>
                              <option value="ai">ai</option>
                              <option value="hybrid">hybrid</option>
                            </select>
                          ) : (
                            <AssigneeTag type={t.assignee_type} />
                          )}
                          {t.assignee_id ? (
                            <div className="mt-1 text-[11px] text-muted">{t.assignee_id}</div>
                          ) : null}
                        </td>
                        <td className="px-4 py-3">
                          {editable ? (
                            <select
                              value={t.severity}
                              disabled={savingId === t.id}
                              onChange={(e) =>
                                onPatch(t, { severity: e.target.value as Severity })
                              }
                              className="select"
                            >
                              <option value="low">low</option>
                              <option value="medium">medium</option>
                              <option value="high">high</option>
                            </select>
                          ) : (
                            <SeverityBadge severity={t.severity} />
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-xs font-medium text-ink">
                            {doc?.title ?? t.target_document_id}
                          </div>
                          {doc?.celex ? (
                            <div className="mt-0.5 font-mono text-[11px] text-muted">
                              {doc.celex}
                            </div>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Panel>

            <p className="mt-3 text-xs text-muted">
              Severity is a deliberate policy choice set up front from the process document — not an
              AI inference. You can override it here before approving.
            </p>
          </>
        )}
      </div>

      <style>{`
        .select {
          border-radius: 0.5rem;
          border: 1px solid var(--color-line);
          background: #fff;
          padding: 0.3rem 0.5rem;
          font-size: 0.8rem;
          color: var(--color-ink);
        }
        .select:focus { outline: none; border-color: var(--color-brand); box-shadow: 0 0 0 3px var(--color-brand-soft); }
      `}</style>
    </div>
  );
}
