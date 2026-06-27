"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  addPlanTask,
  approvePlan,
  createPlan,
  deleteTask,
  getAssociates,
  getCase,
  getCorpus,
  getPlan,
  patchTask,
  revisePlan,
  type TaskPatchBody,
} from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { AssigneeType, Associate, Case, CorpusDoc, Plan, Severity, Task } from "@/lib/types";
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
  const [associates, setAssociates] = useState<Associate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [revising, setRevising] = useState(false);
  const [revisions, setRevisions] = useState(0);

  useEffect(() => {
    setRole(getRole());
    return subscribeRole(() => setRole(getRole()));
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      // Case + corpus always load; a missing plan (404) is an expected state for a freshly created
      // case, not an error — leave `plan` null so the empty state offers generation.
      const [c, corp, assoc] = await Promise.all([getCase(id), getCorpus(), getAssociates()]);
      setCaseData(c);
      setCorpus(corp);
      setAssociates(assoc);
      try {
        const p = await getPlan(id);
        setPlan(p.plan);
        setTasks([...p.tasks].sort((a, b) => a.order_index - b.order_index));
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          setPlan(null);
          setTasks([]);
        } else {
          throw e;
        }
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Failed to load plan.");
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

  const associatesById = useMemo(() => {
    const m = new Map<string, Associate>();
    associates.forEach((a) => m.set(a.id, a));
    return m;
  }, [associates]);

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

  const onGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      await createPlan(id);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not generate a plan.");
    } finally {
      setGenerating(false);
    }
  };

  const onRevise = async () => {
    const note = feedback.trim();
    if (!note) return;
    setRevising(true);
    setError(null);
    try {
      const r = await revisePlan(id, note);
      setPlan(r.plan);
      setTasks([...r.tasks].sort((a, b) => a.order_index - b.order_index));
      setFeedback("");
      setRevisions((n) => n + 1);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not revise the plan.");
    } finally {
      setRevising(false);
    }
  };

  const onAddTask = async () => {
    setError(null);
    try {
      const t = await addPlanTask(id);
      setTasks((ts) => [...ts, t].sort((a, b) => a.order_index - b.order_index));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not add a task.");
    }
  };

  const onRemoveTask = async (task: Task) => {
    setSavingId(task.id);
    setError(null);
    try {
      await deleteTask(task.id);
      setTasks((ts) => ts.filter((t) => t.id !== task.id));
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not remove the task.");
    } finally {
      setSavingId(null);
    }
  };

  // Reorder by swapping order_index with the adjacent task (two PATCHes); the table sorts by it.
  const onMove = async (task: Task, dir: -1 | 1) => {
    const sorted = [...tasks].sort((a, b) => a.order_index - b.order_index);
    const idx = sorted.findIndex((t) => t.id === task.id);
    const neighbour = sorted[idx + dir];
    if (!neighbour) return;
    setSavingId(task.id);
    setError(null);
    try {
      const a = await patchTask(task.id, { order_index: neighbour.order_index });
      const b = await patchTask(neighbour.id, { order_index: task.order_index });
      setTasks((ts) =>
        ts
          .map((t) => (t.id === a.id ? a : t.id === b.id ? b : t))
          .sort((x, y) => x.order_index - y.order_index)
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not reorder the tasks.");
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
        ) : !plan ? (
          // No plan yet (e.g. a freshly created case). Generating one is an explicit partner
          // action — never auto-run on case creation.
          <Panel className="p-8 text-center">
            <div className="text-sm font-semibold text-ink">No plan for this case yet</div>
            <p className="mx-auto mt-1 max-w-md text-xs text-muted">
              The planner proposes tasks with an assignee type and severity for you to edit and
              approve. Generating a plan does not dispatch anything — nothing runs until you approve.
            </p>
            {role === "partner" ? (
              <Button className="mt-4" onClick={onGenerate} disabled={generating}>
                {generating ? "Generating plan…" : "Generate plan"}
              </Button>
            ) : (
              <p className="mt-3 text-xs text-muted">
                Switch to Partner in the header to generate a plan.
              </p>
            )}
            {error ? (
              <div className="mx-auto mt-4 max-w-md">
                <ErrorNote message={error} />
              </div>
            ) : null}
          </Panel>
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

            {/* Tell the planner what to change — re-proposes the plan; the partner still approves. */}
            {editable ? (
              <div className="mb-4 rounded-xl border border-line bg-canvas p-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-xs font-semibold text-ink">Shape the plan</div>
                  {revisions > 0 ? (
                    <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-medium text-brand">
                      Revised ×{revisions}
                    </span>
                  ) : null}
                </div>
                <p className="mt-0.5 text-[11px] text-muted">
                  Tell the planner what to change — e.g. &ldquo;make the liability review
                  human-led&rdquo;, &ldquo;add a task for the data-transfer clause&rdquo;, &ldquo;drop
                  the recital summary&rdquo;. It re-proposes; nothing runs until you approve.
                </p>
                <div className="mt-2 flex items-start gap-2">
                  <textarea
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    rows={2}
                    placeholder="What should the planner change?…"
                    className="flex-1 resize-none rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft"
                  />
                  <Button onClick={onRevise} disabled={revising || !feedback.trim()}>
                    {revising ? "Revising…" : "Send to planner"}
                  </Button>
                </div>
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
                    {editable ? (
                      <th className="px-4 py-3 text-right font-semibold">Edit</th>
                    ) : null}
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((t, i) => {
                    const doc = corpusById.get(t.target_document_id);
                    return (
                      <tr key={t.id} className="border-b border-line last:border-0 align-top">
                        <td className="max-w-md px-4 py-3">
                          {editable ? (
                            <EditableText
                              value={t.title}
                              onSave={(v) => onPatch(t, { title: v })}
                              disabled={savingId === t.id}
                              className="font-medium text-ink"
                              placeholder="Task title"
                            />
                          ) : (
                            <div className="font-medium text-ink">{t.title}</div>
                          )}
                          {editable ? (
                            <EditableText
                              value={t.description}
                              onSave={(v) => onPatch(t, { description: v })}
                              disabled={savingId === t.id}
                              rows={2}
                              className="mt-1 text-xs text-muted"
                              placeholder="Description"
                            />
                          ) : (
                            <div className="mt-0.5 text-xs text-muted">{t.description}</div>
                          )}

                          {/* Planner rationale — the partner verifies the reasoning; read-only. */}
                          {t.rationale ? (
                            <div className="mt-1.5 flex items-start gap-1.5 text-[11px] text-muted">
                              <span className="mt-px shrink-0 font-semibold uppercase tracking-wide text-slate-400">
                                Why
                              </span>
                              <span className="italic">{t.rationale}</span>
                            </div>
                          ) : null}

                          {/* The AI / associate split. Both halves editable on a hybrid task. */}
                          {t.assignee_type === "hybrid" ? (
                            <div className="mt-2 space-y-1.5">
                              <InstructionField
                                label="AI does"
                                tone="brand"
                                value={t.ai_instruction}
                                editable={editable}
                                saving={savingId === t.id}
                                onSave={(v) => onPatch(t, { ai_instruction: v })}
                                placeholder="What the AI does as a first pass…"
                              />
                              <InstructionField
                                label="Associate does"
                                tone="sky"
                                value={t.human_instruction}
                                editable={editable}
                                saving={savingId === t.id}
                                onSave={(v) => onPatch(t, { human_instruction: v })}
                                placeholder="What the associate owns and decides…"
                              />
                            </div>
                          ) : editable ? (
                            <InstructionField
                              label="AI instruction"
                              tone="brand"
                              value={t.ai_instruction}
                              editable
                              saving={savingId === t.id}
                              onSave={(v) => onPatch(t, { ai_instruction: v })}
                              placeholder="Optional AI instruction…"
                            />
                          ) : t.ai_instruction ? (
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

                          {/* Which associate owns the human/hybrid work — editable before approval.
                              AI-only tasks have no associate. */}
                          {t.assignee_type !== "ai" ? (
                            editable ? (
                              <label className="mt-1.5 block">
                                <span className="mb-0.5 block text-[10px] font-medium uppercase tracking-wide text-muted">
                                  Who&apos;s in charge
                                </span>
                                <select
                                  value={t.assignee_id ?? ""}
                                  disabled={savingId === t.id}
                                  onChange={(e) => onPatch(t, { assignee_id: e.target.value })}
                                  className="select max-w-[13rem]"
                                >
                                  <option value="">Unassigned (any associate)</option>
                                  {associates.map((a) => (
                                    <option key={a.id} value={a.id}>
                                      {a.name} — {a.practice_area} ({a.current_load}/{a.capacity})
                                    </option>
                                  ))}
                                </select>
                              </label>
                            ) : t.assignee_id ? (
                              <div className="mt-1 text-[11px] text-muted">
                                {associatesById.get(t.assignee_id)?.name ?? t.assignee_id}
                              </div>
                            ) : (
                              <div className="mt-1 text-[11px] text-muted">Unassigned</div>
                            )
                          ) : null}
                          {t.assignee_rationale ? (
                            <div className="mt-1 max-w-[15rem] text-[11px] leading-snug text-muted">
                              {t.assignee_rationale}
                            </div>
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
                        {editable ? (
                          <td className="px-4 py-3">
                            <div className="flex items-center justify-end gap-1">
                              <RowButton
                                label="Move up"
                                disabled={i === 0 || savingId === t.id}
                                onClick={() => onMove(t, -1)}
                              >
                                ↑
                              </RowButton>
                              <RowButton
                                label="Move down"
                                disabled={i === tasks.length - 1 || savingId === t.id}
                                onClick={() => onMove(t, 1)}
                              >
                                ↓
                              </RowButton>
                              <RowButton
                                label="Remove task"
                                danger
                                disabled={savingId === t.id || tasks.length <= 1}
                                onClick={() => onRemoveTask(t)}
                              >
                                ✕
                              </RowButton>
                            </div>
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {editable ? (
                <div className="border-t border-line px-4 py-3">
                  <Button variant="secondary" onClick={onAddTask} className="!py-1.5 !text-xs">
                    + Add task
                  </Button>
                </div>
              ) : null}
            </Panel>

            <p className="mt-3 text-xs text-muted">
              Severity is a policy choice from the process document — not an AI inference.
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

// A compact icon button for the per-row reorder/remove controls.
function RowButton({
  label,
  onClick,
  disabled,
  danger,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className={`flex h-7 w-7 items-center justify-center rounded-md text-sm ring-1 ring-inset ring-line transition-colors disabled:opacity-30 ${
        danger ? "text-red-600 hover:bg-red-50" : "text-muted hover:bg-canvas hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

// An inline-editable text field that commits on blur (one PATCH per edit, not per keystroke). Local
// state is kept in sync with the saved value so an external update re-syncs without clobbering a
// mid-edit field.
function EditableText({
  value,
  onSave,
  disabled,
  rows = 1,
  placeholder,
  className,
}: {
  value: string | null;
  onSave: (v: string) => void;
  disabled?: boolean;
  rows?: number;
  placeholder?: string;
  className?: string;
}) {
  const [v, setV] = useState(value ?? "");
  useEffect(() => setV(value ?? ""), [value]);
  const commit = () => {
    const next = v.trim();
    if (next !== (value ?? "")) onSave(next);
  };
  return (
    <textarea
      value={v}
      rows={rows}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => setV(e.target.value)}
      onBlur={commit}
      className={`w-full resize-none rounded-md border border-line bg-white px-2 py-1 leading-snug outline-none focus:border-brand focus:ring-2 focus:ring-brand-soft disabled:opacity-50 ${className ?? ""}`}
    />
  );
}

// One half of the AI/associate split: a labelled instruction, editable when the plan is still
// proposed, read-only otherwise.
function InstructionField({
  label,
  tone,
  value,
  editable,
  saving,
  onSave,
  placeholder,
}: {
  label: string;
  tone: "brand" | "sky";
  value: string | null;
  editable: boolean;
  saving: boolean;
  onSave: (v: string) => void;
  placeholder?: string;
}) {
  const toneCls =
    tone === "sky"
      ? "bg-sky-50 text-sky-700 ring-sky-200"
      : "bg-brand-soft text-brand ring-brand/20";
  return (
    <div>
      <span
        className={`mb-0.5 inline-block rounded-full px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset ${toneCls}`}
      >
        {label}
      </span>
      {editable ? (
        <EditableText
          value={value}
          onSave={onSave}
          disabled={saving}
          rows={2}
          placeholder={placeholder}
          className="text-[11px] text-ink-soft"
        />
      ) : (
        <div className="text-[11px] leading-snug text-ink-soft">{value || "—"}</div>
      )}
    </div>
  );
}
