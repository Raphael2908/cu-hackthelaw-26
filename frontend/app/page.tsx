"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  createCase,
  createPlan,
  createProcessMap,
  getCockpit,
  listCases,
  listProcessMaps,
  uploadCaseDocuments,
} from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { Case, Cockpit, ProcessMap, ProcessMapSection, Severity } from "@/lib/types";
import { Button, ErrorNote, Panel, Spinner } from "@/components/ui";

// Derive a stable task_type key from a free-text section label.
const slug = (s: string) =>
  s.toLowerCase().trim().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "section";

const SEVERITIES: Severity[] = ["low", "medium", "high", "extreme"];

// At-a-glance state for one case (walkthrough gap G1 — see DESIGN.md). Lets the partner tell which
// case needs them from the list, without opening each cockpit (H1 visibility).
type CaseSummary = {
  inReview: number;
  hardFlags: number;
  awaitingHuman: number;
  decided: number;
  cleared: number;
};

function summarise(ck: Cockpit): CaseSummary {
  return {
    inReview: ck.queue.length,
    hardFlags: ck.queue.filter((c) => c.risk?.has_hard_flag || c.top_flag?.hard).length,
    awaitingHuman: ck.awaiting_human.length,
    decided: ck.decided.length,
    cleared: ck.auto_clear_lane.length,
  };
}

const DEMO = {
  title: "Project Atlas — supplier agreement review",
  brief_text: "Supplier processes customer personal data including via US affiliates.",
  goal: "Review the Project Atlas agreement against the firm standard before signing.",
  instructions: "Keep the liability and governing-law review human-led; the client is risk-averse.",
};

export default function CasesPage() {
  const router = useRouter();
  const [cases, setCases] = useState<Case[] | null>(null);
  const [summaries, setSummaries] = useState<Record<string, CaseSummary>>({});
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [goal, setGoal] = useState("");
  const [instructions, setInstructions] = useState("");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);

  const [maps, setMaps] = useState<ProcessMap[]>([]);
  const [processDocId, setProcessDocId] = useState<string>("");
  const [addingMap, setAddingMap] = useState(false);
  const [newMapTitle, setNewMapTitle] = useState("");
  const [newMapSections, setNewMapSections] = useState("");

  const load = () =>
    listCases()
      .then((c) => setCases([...c].reverse()))
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Failed to load cases."));

  const loadMaps = () =>
    listProcessMaps()
      .then((m) => {
        setMaps(m);
        setProcessDocId((cur) => cur || m[0]?.id || "");
      })
      .catch(() => {});

  useEffect(() => {
    load();
    loadMaps();
  }, []);

  const onAddMap = async () => {
    const task_types: Record<string, ProcessMapSection> = {};
    newMapSections
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean)
      .forEach((label) => {
        task_types[slug(label)] = { label, severity: "medium" };
      });
    if (!newMapTitle.trim() || Object.keys(task_types).length === 0) return;
    setBusy("map");
    setError(null);
    try {
      const created = await createProcessMap({ title: newMapTitle, task_types });
      setNewMapTitle("");
      setNewMapSections("");
      setAddingMap(false);
      await loadMaps();
      setProcessDocId(created.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not add the process map.");
    } finally {
      setBusy(null);
    }
  };

  // Pull each case's cockpit summary in parallel; degrade silently per-case (a case with no plan
  // yet simply shows no status line rather than blocking the list).
  useEffect(() => {
    if (!cases) return;
    let cancelled = false;
    Promise.allSettled(cases.map((c) => getCockpit(c.id))).then((results) => {
      if (cancelled) return;
      const next: Record<string, CaseSummary> = {};
      results.forEach((r, i) => {
        if (r.status === "fulfilled") next[cases[i].id] = summarise(r.value);
      });
      setSummaries(next);
    });
    return () => {
      cancelled = true;
    };
  }, [cases]);

  const onCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy("create");
    setError(null);
    try {
      const created = await createCase({
        title,
        brief_text: brief,
        goal,
        severity,
        instructions,
        process_doc_id: processDocId || undefined,
      });
      // Attach any uploaded documents up front so the planner scopes tasks over them when the
      // partner generates the plan.
      if (files.length) {
        setBusy("upload");
        await uploadCaseDocuments(created.id, files);
      }
      setTitle("");
      setBrief("");
      setGoal("");
      setInstructions("");
      setSeverity("medium");
      setFiles([]);
      // Plan generation is a separate, explicit step — route to the plan page where the partner
      // generates and reviews the proposed tasks before anything is dispatched.
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
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Cases</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted">
            Delegate legal review to human and AI workers under your approval, then supervise the
            completed output. Agents surface checkable claims — they never render a verdict, and
            nothing is auto-approved.
          </p>
        </div>
        <Button onClick={() => setShowNew(true)} className="shrink-0">
          + New case
        </Button>
      </div>

      {error ? (
        <div className="mb-5">
          <ErrorNote message={error} />
        </div>
      ) : null}

      {/* List — full width; the new-case form opens in an on-demand modal (below). */}
      <div>
          {cases === null ? (
            <Panel className="p-5">
              <Spinner label="Loading cases…" />
            </Panel>
          ) : cases.length === 0 ? (
            <Panel className="p-8 text-center text-sm text-muted">
              No cases yet. Click <span className="font-medium text-ink">+ New case</span> to create
              one.
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
                        <StatusLine summary={summaries[c.id]} />
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

      {showNew ? (
        <Modal onClose={() => setShowNew(false)} labelledBy="new-case-title">
          <Panel className="max-h-[85vh] overflow-y-auto">
            <form onSubmit={onCreate} className="space-y-4 p-5">
              <div className="flex items-center justify-between">
                <h2 id="new-case-title" className="text-sm font-semibold text-ink">
                  New case
                </h2>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setTitle(DEMO.title);
                      setBrief(DEMO.brief_text);
                      setGoal(DEMO.goal);
                      setInstructions(DEMO.instructions);
                    }}
                    className="!px-2 !py-1 !text-xs"
                  >
                    Demo case
                  </Button>
                  <button
                    type="button"
                    onClick={() => setShowNew(false)}
                    aria-label="Close"
                    className="rounded-md px-2 py-1 text-sm text-muted hover:bg-canvas hover:text-ink"
                  >
                    ✕
                  </button>
                </div>
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
              <Field label="Instructions for the planner (optional)">
                <textarea
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  rows={2}
                  placeholder="e.g. keep liability review human-led; focus on the data-transfer clauses…"
                  className="input resize-none"
                />
                <span className="mt-1 block text-[11px] leading-snug text-muted">
                  Your direction for how to approach the work. The planner proposes; you still
                  approve.
                </span>
              </Field>
              <Field label="Severity">
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value as Severity)}
                  className="input"
                >
                  {SEVERITIES.map((s) => (
                    <option key={s} value={s}>
                      {s[0].toUpperCase() + s.slice(1)}
                    </option>
                  ))}
                </select>
                <span className="mt-1 block text-[11px] leading-snug text-muted">
                  Your up-front risk call — higher severity keeps more work in the review queue.
                </span>
              </Field>
              <Field label="Process map (optional)">
                <select
                  value={processDocId}
                  onChange={(e) => setProcessDocId(e.target.value)}
                  className="input"
                >
                  {maps.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.title}
                    </option>
                  ))}
                </select>
                <span className="mt-1 block text-[11px] leading-snug text-muted">
                  How the firm runs this kind of matter. A reused map lets the planner propose AI
                  where it has a clean track record; a fresh map is a clean slate — you decide where
                  AI goes.{" "}
                  <button
                    type="button"
                    onClick={() => setAddingMap((v) => !v)}
                    className="font-medium text-brand hover:underline"
                  >
                    {addingMap ? "Cancel" : "＋ Add map"}
                  </button>
                </span>
                {addingMap ? (
                  <div className="mt-2 space-y-2 rounded-lg bg-brand-soft/40 p-3 ring-1 ring-inset ring-line">
                    <input
                      value={newMapTitle}
                      onChange={(e) => setNewMapTitle(e.target.value)}
                      placeholder="Map title (e.g. Standard licensing review)"
                      className="input"
                    />
                    <textarea
                      value={newMapSections}
                      onChange={(e) => setNewMapSections(e.target.value)}
                      rows={3}
                      placeholder="One section per line (e.g. Review of the licence grant)"
                      className="input resize-none"
                    />
                    <Button
                      type="button"
                      onClick={onAddMap}
                      disabled={busy === "map" || !newMapTitle.trim() || !newMapSections.trim()}
                      className="w-full !py-1.5 !text-xs"
                    >
                      {busy === "map" ? "Adding…" : "Add process map"}
                    </Button>
                  </div>
                ) : null}
              </Field>
              <Field label="Documents (optional)">
                <input
                  type="file"
                  multiple
                  accept=".pdf,.docx,.pptx,.txt,.md,.markdown"
                  onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
                  className="input"
                />
                {files.length ? (
                  <ul className="mt-2 space-y-1">
                    {files.map((f) => (
                      <li key={f.name} className="truncate text-[11px] text-ink-soft">
                        {f.name} · {(f.size / 1024).toFixed(0)} KB
                      </li>
                    ))}
                  </ul>
                ) : (
                  <span className="mt-1 block text-[11px] leading-snug text-muted">
                    PDF, DOCX, PowerPoint, or text.
                  </span>
                )}
              </Field>

              <Button type="submit" disabled={!!busy || !title.trim()} className="w-full">
                {busy === "upload"
                  ? "Uploading documents…"
                  : busy === "create"
                    ? "Creating case…"
                    : "Create case"}
              </Button>
              <p className="text-[11px] leading-snug text-muted">
                Nothing is dispatched until you approve the plan.
              </p>
            </form>
          </Panel>
        </Modal>
      ) : null}

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

// A foreground modal in the product's own visual language (the children supply the Panel). Dims the
// list behind it, closes on Esc / backdrop-click, traps Tab focus, and restores focus to the trigger.
function Modal({
  onClose,
  labelledBy,
  children,
}: {
  onClose: () => void;
  labelledBy?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const restoreTo = document.activeElement as HTMLElement | null;
    const focusables = () =>
      Array.from(
        ref.current?.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'
        ) ?? []
      );
    focusables()[0]?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "Tab") {
        const f = focusables();
        if (f.length === 0) return;
        const first = f[0];
        const last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      restoreTo?.focus();
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-8"
      role="dialog"
      aria-modal="true"
      aria-labelledby={labelledBy}
    >
      <div className="fixed inset-0 bg-ink/30" onClick={onClose} aria-hidden />
      <div ref={ref} className="relative z-10 w-full max-w-lg">
        {children}
      </div>
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

// At-a-glance case state. Pills only appear when their count is non-zero, so the card stays quiet
// until something actually needs the partner (H1 visibility, H8 minimalism).
function StatusLine({ summary }: { summary?: CaseSummary }) {
  if (!summary) return null;
  const { inReview, hardFlags, awaitingHuman, decided, cleared } = summary;
  const pills: { key: string; label: string; cls: string }[] = [];
  if (hardFlags > 0)
    pills.push({
      key: "hard",
      label: `${hardFlags} hard flag${hardFlags === 1 ? "" : "s"}`,
      cls: "bg-red-50 text-red-700 ring-red-200",
    });
  if (inReview > 0)
    pills.push({
      key: "review",
      label: `${inReview} in review`,
      cls: "bg-amber-50 text-amber-700 ring-amber-200",
    });
  if (awaitingHuman > 0)
    pills.push({
      key: "human",
      label: `${awaitingHuman} awaiting human`,
      cls: "bg-sky-50 text-sky-700 ring-sky-200",
    });
  if (decided > 0)
    pills.push({
      key: "decided",
      label: `${decided} decided`,
      cls: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    });
  if (cleared > 0)
    pills.push({
      key: "cleared",
      label: `${cleared} auto-cleared`,
      cls: "bg-slate-100 text-slate-600 ring-slate-200",
    });

  if (pills.length === 0)
    return <p className="mt-2 text-[11px] text-muted">No work dispatched yet.</p>;

  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
      {pills.map((p) => (
        <span
          key={p.key}
          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${p.cls}`}
        >
          {p.label}
        </span>
      ))}
    </div>
  );
}
