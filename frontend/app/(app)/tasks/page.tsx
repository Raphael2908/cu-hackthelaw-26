"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Task } from "@/lib/types";

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [evalDocCount, setEvalDocCount] = useState(5);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setTasks(await api.listTasks());
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createTask({ title, brief, eval_doc_count: evalDocCount });
      setTitle("");
      setBrief("");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <header>
        <h1 className="text-2xl font-semibold">Tasks</h1>
        <p className="text-neutral-600">
          Describe a legal task; the copilot plans, researches, ranks, evaluates the top-N
          documents, and synthesises an argument.
        </p>
      </header>

      <form onSubmit={create} className="flex flex-col gap-3 rounded-lg border p-4">
        <input
          required
          placeholder="Title (e.g. Acme / Beta M&A first-draft plan)"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="rounded-md border border-neutral-300 px-3 py-2"
        />
        <textarea
          required
          placeholder="Brief — what argument do you need drafted?"
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          rows={4}
          className="rounded-md border border-neutral-300 px-3 py-2"
        />
        <label className="flex items-center gap-2 text-sm text-neutral-700">
          Documents to evaluate (N):
          <input
            type="number"
            min={1}
            max={50}
            value={evalDocCount}
            onChange={(e) => setEvalDocCount(Number(e.target.value))}
            className="w-20 rounded-md border border-neutral-300 px-2 py-1"
          />
        </label>
        <button
          disabled={busy}
          className="self-start rounded-md bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {busy ? "Creating…" : "Create task"}
        </button>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>

      <ul className="flex flex-col gap-2">
        {tasks.map((t) => (
          <li key={t.id} className="flex items-center justify-between rounded-md border p-3">
            <div>
              <p className="font-medium">{t.title}</p>
              <p className="text-sm text-neutral-500">N={t.eval_doc_count}</p>
            </div>
            <span className="rounded-full bg-neutral-100 px-3 py-1 text-sm">{t.status}</span>
          </li>
        ))}
        {tasks.length === 0 && <p className="text-neutral-500">No tasks yet.</p>}
      </ul>
    </div>
  );
}
