"use client";

import { Fragment, type ReactNode } from "react";

// A deliberately tiny markdown renderer — no heavy dependency. Handles headings, bullet lists,
// bold (**…**) and inline code (`…`), and paragraphs. Enough for the generated debrief.

function inline(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g;
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
    } else {
      nodes.push(
        <code
          key={`${keyBase}-c-${i}`}
          className="rounded bg-canvas px-1 py-0.5 font-mono text-[0.85em] text-brand"
        >
          {tok.slice(1, -1)}
        </code>
      );
    }
    last = m.index + tok.length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function Markdown({ content }: { content: string }) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  let key = 0;

  const flushList = () => {
    if (list.length === 0) return;
    const items = [...list];
    blocks.push(
      <ul key={`ul-${key++}`} className="my-3 space-y-1.5 pl-5">
        {items.map((it, idx) => (
          <li key={idx} className="list-disc text-sm leading-relaxed text-ink-soft">
            {inline(it, `li-${key}-${idx}`)}
          </li>
        ))}
      </ul>
    );
    list = [];
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^#{1,6}\s/.test(line)) {
      flushList();
      const level = (line.match(/^#+/)?.[0].length ?? 1);
      const txt = line.replace(/^#+\s/, "");
      const cls =
        level === 1
          ? "mt-1 mb-3 text-xl font-bold text-ink"
          : level === 2
            ? "mt-5 mb-2 text-base font-semibold text-ink"
            : "mt-4 mb-1.5 text-sm font-semibold text-ink";
      blocks.push(
        <Fragment key={`h-${key++}`}>
          <div className={cls}>{inline(txt, `h-${key}`)}</div>
        </Fragment>
      );
    } else if (/^[-*]\s/.test(line)) {
      list.push(line.replace(/^[-*]\s/, ""));
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
