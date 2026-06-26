"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createCase, createPlan, listCases } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { Case } from "@/lib/types";
import { Button, ErrorNote, Panel, Spinner } from "@/components/ui";

const DEMO = {
  title: "Project Atlas — supplier agreement review",
  brief_text: "Supplier processes customer personal data including via US affiliates.",
  goal: "Review the Project Atlas agreement against the firm standard before signing.",
};

export default function CasesPage() {
  const router = useRouter();
  const [cases, setCases] = useState<Case[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const load = () =>
    listCases()
      .then((c) => setCases([...c].reverse()))
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Failed to load cases."));

  useEffect(() => {
    load();
  }, []);

  const onCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy("create");
    setError(null);
    try {
      const created = await createCase({ title, brief_text: brief, goal });
      setTitle("");
      setBrief("");
      setGoal("");
      await load();
      // Offer plan generation immediately by routing through it.
      setBusy("plan");
      await createPlan(created.id);
      router.push(`/cases/${created.id}/plan`);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not create the case.");
      setBusy(null);
    }
  };

  const generatePlan = async (caseId: string) => {
    setBusy(caseId);
    setError(null);
    try {
      await createPlan(caseId);
      router.push(`/cases/${caseId}/plan`);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not generate a plan.");
      setBusy(null);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">Cases</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          Delegate legal review to human and AI workers under your approval, then supervise the
          completed output. Agents surface checkable claims — they never render a verdict, and
          nothing is auto-approved.
        </p>
      </div>

      {error ? (
        <div className="mb-5">
          <ErrorNote message={error} />
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* New case */}
        <Panel className="lg:col-span-1">
          <form onSubmit={onCreate} className="space-y-4 p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink">New case</h2>
              <Button
                variant="ghost"
                onClick={() => {
                  setTitle(DEMO.title);
                  setBrief(DEMO.brief_text);
                  setGoal(DEMO.goal);
                }}
                className="!px-2 !py-1 !text-xs"
              >
                Demo case
              </Button>
            </div>

            <Field label="Title">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Matter title"
                className="input"
              />
            </Field>
            <Field label="Brief">
              <textarea
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                rows={3}
                placeholder="The factual brief…"
                className="input resize-none"
              />
            </Field>
            <Field label="Goal">
              <textarea
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                rows={2}
                placeholder="What outcome do you want?"
                className="input resize-none"
              />
            </Field>

            <Button type="submit" disabled={!!busy || !title.trim()} className="w-full">
              {busy === "create" || busy === "plan"
                ? "Creating & planning…"
                : "Create case & generate plan"}
            </Button>
            <p className="text-[11px] leading-snug text-muted">
              Creating a case runs the planner to propose tasks. Nothing is dispatched until you
              approve the plan.
            </p>
          </form>
        </Panel>

        {/* List */}
        <div className="lg:col-span-2">
          {cases === null ? (
            <Panel className="p-5">
              <Spinner label="Loading cases…" />
            </Panel>
          ) : cases.length === 0 ? (
            <Panel className="p-8 text-center text-sm text-muted">
              No cases yet. Create one with the form, or use the Demo case quick-fill.
            </Panel>
          ) : (
            <ul className="space-y-3">
              {cases.map((c) => (
                <li key={c.id}>
                  <Panel className="p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="truncate text-[15px] font-semibold text-ink">
                            {c.title}
                          </h3>
                          <span
                            className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${
                              c.status === "open"
                                ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
                                : "bg-slate-100 text-slate-500 ring-slate-200"
                            }`}
                          >
                            {c.status}
                          </span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-sm text-muted">{c.goal}</p>
                        <p className="mt-1 text-[11px] text-muted">
                          Created by {c.created_by}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <Link
                        href={`/cases/${c.id}/cockpit`}
                        className="rounded-lg bg-brand px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#16304f]"
                      >
                        Open cockpit
                      </Link>
                      <Link
                        href={`/cases/${c.id}/plan`}
                        className="rounded-lg px-3 py-1.5 text-xs font-semibold text-brand ring-1 ring-inset ring-line hover:bg-brand-soft"
                      >
                        Plan
                      </Link>
                      <Link
                        href={`/cases/${c.id}/audit`}
                        className="rounded-lg px-3 py-1.5 text-xs font-semibold text-brand ring-1 ring-inset ring-line hover:bg-brand-soft"
                      >
                        Audit
                      </Link>
                      <Link
                        href={`/cases/${c.id}/debrief`}
                        className="rounded-lg px-3 py-1.5 text-xs font-semibold text-brand ring-1 ring-inset ring-line hover:bg-brand-soft"
                      >
                        Debrief
                      </Link>
                      <button
                        onClick={() => generatePlan(c.id)}
                        disabled={busy === c.id}
                        className="ml-auto rounded-lg px-3 py-1.5 text-xs font-semibold text-muted hover:text-ink disabled:opacity-50"
                      >
                        {busy === c.id ? "Generating…" : "Generate plan ↺"}
                      </button>
                    </div>
                  </Panel>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <style>{`
        .input {
          width: 100%;
          border-radius: 0.5rem;
          border: 1px solid var(--color-line);
          background: #fff;
          padding: 0.55rem 0.7rem;
          font-size: 0.875rem;
          color: var(--color-ink);
          outline: none;
        }
        .input:focus { border-color: var(--color-brand); box-shadow: 0 0 0 3px var(--color-brand-soft); }
      `}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-soft">{label}</span>
      {children}
    </label>
  );
}
