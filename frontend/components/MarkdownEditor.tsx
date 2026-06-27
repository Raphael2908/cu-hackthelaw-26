"use client";

import { useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/Markdown";

// A small GitHub-style comment box in the product's own light visual language (not the GitHub dark
// widget): a Write/Preview segmented toggle (same look as the audit filter + role toggles) and a
// light formatting toolbar whose buttons insert markdown around the current selection. Preview reuses
// the shared <Markdown> renderer, so what you format is exactly what's stored and shown back.
// This is a free-text editor for the human's own words — never an agent-generated verdict.

type Tab = "write" | "preview";

// Wrap the selection (or a placeholder) with an inline marker — bold / italic / code.
function wrapInline(value: string, start: number, end: number, marker: string, placeholder: string) {
  const sel = value.slice(start, end) || placeholder;
  const next = value.slice(0, start) + marker + sel + marker + value.slice(end);
  const selStart = start + marker.length;
  return { next, selStart, selEnd: selStart + sel.length };
}

// Insert a markdown link, leaving the "url" portion selected so it can be typed over.
function insertLink(value: string, start: number, end: number) {
  const sel = value.slice(start, end) || "text";
  const insert = `[${sel}](url)`;
  const next = value.slice(0, start) + insert + value.slice(end);
  const urlStart = start + sel.length + 3; // [sel](
  return { next, selStart: urlStart, selEnd: urlStart + 3 };
}

// Prefix every line spanned by the selection — headings and lists are line-level.
function prefixLines(
  value: string,
  start: number,
  end: number,
  makePrefix: (line: string, i: number) => string
) {
  const lineStart = value.lastIndexOf("\n", start - 1) + 1;
  let lineEnd = value.indexOf("\n", end);
  if (lineEnd === -1) lineEnd = value.length;
  const out = value
    .slice(lineStart, lineEnd)
    .split("\n")
    .map((ln, i) => makePrefix(ln, i))
    .join("\n");
  const next = value.slice(0, lineStart) + out + value.slice(lineEnd);
  return { next, selStart: lineStart, selEnd: lineStart + out.length };
}

type Edit = { next: string; selStart: number; selEnd: number };

const TOOLS: { label: string; title: string; cls?: string; apply: (v: string, s: number, e: number) => Edit }[] =
  [
    { label: "H", title: "Heading", cls: "font-bold", apply: (v, s, e) => prefixLines(v, s, e, (ln) => (ln.startsWith("## ") ? ln : `## ${ln}`)) },
    { label: "B", title: "Bold", cls: "font-bold", apply: (v, s, e) => wrapInline(v, s, e, "**", "bold text") },
    { label: "I", title: "Italic", cls: "italic", apply: (v, s, e) => wrapInline(v, s, e, "*", "italic text") },
    { label: "</>", title: "Inline code", cls: "font-mono text-[11px]", apply: (v, s, e) => wrapInline(v, s, e, "`", "code") },
    { label: "Link", title: "Link", apply: (v, s, e) => insertLink(v, s, e) },
    { label: "• List", title: "Bulleted list", apply: (v, s, e) => prefixLines(v, s, e, (ln) => `- ${ln}`) },
    { label: "1. List", title: "Numbered list", apply: (v, s, e) => prefixLines(v, s, e, (ln, i) => `${i + 1}. ${ln}`) },
  ];

export function MarkdownEditor({
  value,
  onChange,
  placeholder,
  rows = 3,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rows?: number;
  disabled?: boolean;
}) {
  const [tab, setTab] = useState<Tab>("write");
  const ref = useRef<HTMLTextAreaElement | null>(null);
  // Selection to restore after onChange re-renders the textarea with the new value.
  const pendingSel = useRef<{ start: number; end: number } | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (el && pendingSel.current) {
      el.focus();
      el.setSelectionRange(pendingSel.current.start, pendingSel.current.end);
      pendingSel.current = null;
    }
  }, [value]);

  const applyTool = (tool: (typeof TOOLS)[number]) => {
    const el = ref.current;
    if (!el) return;
    const { next, selStart, selEnd } = tool.apply(value, el.selectionStart, el.selectionEnd);
    pendingSel.current = { start: selStart, end: selEnd };
    onChange(next);
  };

  return (
    <div className="rounded-lg border border-line bg-white">
      {/* Toolbar: Write/Preview toggle (segmented control) + formatting buttons. */}
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-2 py-1.5">
        <div className="inline-flex rounded-lg bg-canvas p-0.5 ring-1 ring-inset ring-line">
          {(["write", "preview"] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`rounded-md px-2.5 py-1 text-xs font-semibold capitalize transition-colors ${
                tab === t ? "bg-brand text-white shadow-sm" : "text-muted hover:text-ink"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === "write" ? (
          <div className="flex flex-wrap items-center gap-0.5">
            {TOOLS.map((tool) => (
              <button
                key={tool.label}
                type="button"
                title={tool.title}
                disabled={disabled}
                onMouseDown={(e) => e.preventDefault() /* keep the textarea selection */}
                onClick={() => applyTool(tool)}
                className={`rounded px-1.5 py-1 text-xs text-muted hover:bg-canvas hover:text-ink disabled:opacity-40 ${tool.cls ?? ""}`}
              >
                {tool.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      {tab === "write" ? (
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={rows}
          disabled={disabled}
          placeholder={placeholder}
          className="block w-full resize-y rounded-b-lg bg-white px-3 py-2 text-sm outline-none placeholder:text-muted focus:ring-2 focus:ring-inset focus:ring-brand-soft disabled:bg-canvas"
        />
      ) : (
        <div className="min-h-[4.5rem] px-3 py-2">
          {value.trim() ? (
            <Markdown content={value} />
          ) : (
            <p className="text-sm italic text-muted">Nothing to preview yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
