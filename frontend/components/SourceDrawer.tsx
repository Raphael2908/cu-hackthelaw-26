"use client";

import { useEffect, useState } from "react";
import { getCorpusDoc } from "@/lib/api";
import { ApiError } from "@/lib/apiClient";
import type { CorpusDoc, FlagSourceRef, FlagWorkRef } from "@/lib/types";
import { Spinner } from "./ui";

// One-click source verification. Either resolves a corpus document (and highlights the cited
// clause/standard key) or — for a fabricated citation — states plainly that no such source exists.
export function SourceDrawer({
  sourceRef,
  workRef,
  onClose,
}: {
  sourceRef: FlagSourceRef | null;
  workRef?: FlagWorkRef | null;
  onClose: () => void;
}) {
  const [doc, setDoc] = useState<CorpusDoc | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const docId = sourceRef?.corpus_document_id;
  const fabricated = sourceRef?.exists === false;

  useEffect(() => {
    setDoc(null);
    setError(null);
    if (!sourceRef || !docId || fabricated) return;
    setLoading(true);
    getCorpusDoc(docId)
      .then(setDoc)
      .catch((e) => setError(e instanceof ApiError ? e.detail : "Could not load source."))
      .finally(() => setLoading(false));
  }, [sourceRef, docId, fabricated]);

  if (!sourceRef) return null;

  const locator = sourceRef.clause_ref || sourceRef.standard_key;
  const clauseText =
    doc?.clauses && locator && doc.clauses[locator] ? doc.clauses[locator] : null;
  // The quoting side — only render it when there's something to show.
  const work =
    workRef && (workRef.statement || workRef.clause_ref || workRef.claim) ? workRef : null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} aria-hidden />
      <aside className="relative flex h-full w-full max-w-xl flex-col bg-paper shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted">
              Source verification
            </div>
            <h2 className="mt-0.5 text-base font-semibold text-ink">
              {fabricated
                ? "Cited source"
                : doc?.title ?? sourceRef.celex ?? sourceRef.corpus_document_id ?? "Source"}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-muted hover:bg-canvas hover:text-ink"
          >
            Close ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {/* The quoting side: the passage in the submitted work that cited this source. */}
          {work ? (
            <div className="mb-5 rounded-lg border border-sky-200 bg-sky-50/60 p-4">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-sky-700">
                In the submitted work
              </div>
              {work.clause_ref ? (
                <div className="mt-1 text-xs font-semibold text-ink">Clause {work.clause_ref}</div>
              ) : null}
              {work.statement ? (
                <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">
                  {work.statement}
                </p>
              ) : null}
              {work.claim ? (
                <p className="mt-2 text-xs text-sky-900">
                  <span className="font-semibold">Claims this source says:</span> &ldquo;
                  {work.claim}&rdquo;
                </p>
              ) : null}
            </div>
          ) : null}

          {work ? (
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
              In the source
            </div>
          ) : null}

          {fabricated ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-5">
              <div className="text-sm font-semibold text-red-800">
                No such source exists in the corpus — citation cannot be verified.
              </div>
              <p className="mt-2 text-sm text-red-700">
                The output cited{" "}
                <span className="font-mono font-semibold">{sourceRef.celex ?? "this source"}</span>,
                which is not present in the firm&apos;s corpus. A citation to a non-existent
                authority is a hard flag, surfaced regardless of severity.
              </p>
            </div>
          ) : loading ? (
            <Spinner label="Opening source…" />
          ) : error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : doc ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                <span className="rounded-md bg-canvas px-2 py-1 font-medium capitalize ring-1 ring-inset ring-line">
                  {doc.kind.replace(/_/g, " ")}
                </span>
                {doc.celex ? (
                  <span className="rounded-md bg-canvas px-2 py-1 font-mono ring-1 ring-inset ring-line">
                    {doc.celex}
                  </span>
                ) : null}
                {doc.source_url ? (
                  <a
                    href={doc.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-brand underline-offset-2 hover:underline"
                  >
                    open original ↗
                  </a>
                ) : null}
              </div>

              {clauseText ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                  <div className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">
                    Cited locator · {locator}
                  </div>
                  <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-amber-900">
                    {clauseText}
                  </p>
                </div>
              ) : locator ? (
                <div className="rounded-lg border border-line bg-canvas px-4 py-2.5 text-xs text-muted">
                  Cited locator <span className="font-semibold text-ink">{locator}</span> — review
                  the full text below.
                </div>
              ) : null}

              <div>
                <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
                  Full source text
                </div>
                <p className="whitespace-pre-wrap rounded-lg border border-line bg-canvas p-4 text-sm leading-relaxed text-ink-soft">
                  {doc.text}
                </p>
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted">No source reference attached to this flag.</div>
          )}
        </div>

        <div className="border-t border-line bg-canvas px-6 py-3 text-[11px] leading-snug text-muted">
          The flag is an observation about a checkable source. You verify it here — the system never
          renders a verdict.
        </div>
      </aside>
    </div>
  );
}
