"use client";

import { Fragment, type ReactNode } from "react";

// A deliberately tiny markdown renderer — no heavy dependency. Handles headings, bullet + numbered
// lists, bold (**…**), italic (*…*), inline code (`…`), links ([text](url)), and paragraphs. Enough
// for the generated debrief and the human-authored notes/submissions from the markdown editor.

function inline(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Order matters: bold (**) is tried before italic (*) so it wins at a double star.
  const regex = /(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      nodes.push(
        <strong key={`${keyBase}-b-${i}`} className="font-semibold text-ink">
          {tok.slice(2, -2)}
        </strong>
      );
    } else if (tok.startsWith("`")) {
      nodes.push(
        <code
          key={`${keyBase}-c-${i}`}
          className="rounded bg-canvas px-1 py-0.5 font-mono text-[0.85em] text-brand"
        >
          {tok.slice(1, -1)}
        </code>
      );
    } else if (tok.startsWith("[")) {
      const sep = tok.indexOf("](");
      const label = tok.slice(1, sep);
      const href = tok.slice(sep + 2, -1);
      nodes.push(
        <a
          key={`${keyBase}-a-${i}`}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-brand underline decoration-brand/40 underline-offset-2 hover:decoration-brand"
        >
          {label}
        </a>
      );
    } else {
      nodes.push(
        <em key={`${keyBase}-i-${i}`} className="italic">
          {tok.slice(1, -1)}
        </em>
      );
    }
    last = m.index + tok.length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

// Render inline markdown (bold, inline code) for a single string — reused by the debrief cards.
export function MarkdownInline({ text }: { text: string }) {
  return <>{inline(text, "mi")}</>;
}

export function Markdown({ content }: { content: string }) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  let ordered = false;
  let key = 0;

  const flushList = () => {
    if (list.length === 0) return;
    const items = [...list];
    const isOrdered = ordered;
    blocks.push(
      <ul key={`ul-${key++}`} className="my-3 space-y-2">
        {items.map((it, idx) => (
          <li key={idx} className="flex gap-2.5 text-sm leading-relaxed text-ink-soft">
            {isOrdered ? (
              <span className="mt-0.5 shrink-0 font-semibold text-brand/70">{idx + 1}.</span>
            ) : (
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand/60" aria-hidden />
            )}
            <span className="min-w-0">{inline(it, `li-${key}-${idx}`)}</span>
          </li>
        ))}
      </ul>
    );
    list = [];
    ordered = false;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^#{1,6}\s/.test(line)) {
      flushList();
      const level = (line.match(/^#+/)?.[0].length ?? 1);
      const txt = line.replace(/^#+\s/, "");
      if (level === 2) {
        // Section header: an eyebrow-style label with a hairline rule, for clear scanning.
        blocks.push(
          <div
            key={`h-${key++}`}
            className="mt-7 mb-3 flex items-center gap-3 border-t border-line pt-5 first:mt-0 first:border-0 first:pt-0"
          >
            <span className="h-4 w-1 rounded-full bg-brand" aria-hidden />
            <h2 className="text-sm font-semibold uppercase tracking-wide text-ink">
              {inline(txt, `h-${key}`)}
            </h2>
          </div>
        );
      } else {
        const cls =
          level === 1
            ? "mt-1 mb-3 text-xl font-bold text-ink"
            : "mt-4 mb-1.5 text-sm font-semibold text-ink";
        blocks.push(
          <Fragment key={`h-${key++}`}>
            <div className={cls}>{inline(txt, `h-${key}`)}</div>
          </Fragment>
        );
      }
    } else if (/^[-*]\s/.test(line)) {
      if (ordered) flushList();
      list.push(line.replace(/^[-*]\s/, ""));
    } else if (/^\d+\.\s/.test(line)) {
      if (!ordered && list.length > 0) flushList();
      ordered = true;
      list.push(line.replace(/^\d+\.\s/, ""));
    } else if (line.trim() === "") {
      flushList();
    } else {
      flushList();
      blocks.push(
        <p key={`p-${key++}`} className="my-2 text-sm leading-relaxed text-ink-soft">
          {inline(line, `p-${key}`)}
        </p>
      );
    }
  }
  flushList();

  return <div>{blocks}</div>;
}
