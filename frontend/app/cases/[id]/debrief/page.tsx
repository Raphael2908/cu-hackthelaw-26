"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { closeCase, getCase, getDebrief } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { Case } from "@/lib/types";
import { Button, Panel, Spinner } from "@/components/ui";
import { CaseSubNav } from "@/components/CaseSubNav";
import { Markdown } from "@/components/Markdown";

export default function DebriefPage() {
  const { id } = useParams<{ id: string }>();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCase = () => getCase(id).then(setCaseData).catch(() => {});

  useEffect(() => {
    loadCase();
    getDebrief(id)
      .then((d) => setContent(d.content))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 404) setContent(null);
        else setError(e instanceof ApiError ? e.detail : "Failed to load debrief.");
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const onClose = async () => {
    setClosing(true);
    setError(null);
    try {
      const d = await closeCase(id);
      setContent(d.content);
      await loadCase();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : "Could not close the case.");
    } finally {
      setClosing(false);
    }
  };

  return (
    <div>
      <CaseSubNav caseId={id} title={caseData?.title} />
      <div className="mx-auto max-w-4xl px-6 py-6">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-ink">Case debrief</h1>
            <p className="mt-0.5 text-xs text-muted">
              A templated summary generated from the case record at close.
            </p>
          </div>
          {caseData?.status !== "closed" ? (
            <Button onClick={onClose} disabled={closing}>
              {closing ? "Closing…" : content ? "Regenerate debrief" : "Close case & generate debrief"}
            </Button>
          ) : (
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-500 ring-1 ring-inset ring-slate-200">
              case closed
            </span>
          )}
        </div>

        {error ? (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {loading ? (
          <Spinner label="Loading debrief…" />
        ) : content ? (
          <Panel className="p-7">
            <Markdown content={content} />
          </Panel>
        ) : (
          <Panel className="p-8 text-center text-sm text-muted">
            No debrief yet. Close the case to generate one from the record.
          </Panel>
        )}
      </div>
    </div>
  );
}
