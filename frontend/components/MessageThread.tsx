"use client";

import type { TaskMessage } from "@/lib/types";

// The partner<->associate conversation on one task. Partner messages align right (navy), associate
// messages align left (sky), so the back-and-forth reads like a chat. Each bubble names what kind of
// message it is (a return for rework, a question or concern, a reply).

const KIND_LABEL: Record<TaskMessage["kind"], string> = {
  return: "Sent back for rework",
  question: "Question or concern",
  answer: "Reply",
};

export function MessageThread({ messages }: { messages: TaskMessage[] }) {
  if (!messages || messages.length === 0) {
    return (
      <p className="text-xs text-muted">No messages yet on this task.</p>
    );
  }
  return (
    <ol className="space-y-3">
      {messages.map((m) => {
        const partner = m.author_role === "partner";
        return (
          <li key={m.id} className={`flex ${partner ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] ${partner ? "items-end text-right" : "items-start"}`}>
              <div className="mb-0.5 flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-muted">
                <span className="font-semibold">{partner ? "Partner" : "Associate"}</span>
                <span>· {KIND_LABEL[m.kind]}</span>
              </div>
              <div
                className={`inline-block rounded-2xl px-3.5 py-2 text-sm ${
                  partner
                    ? "rounded-tr-sm bg-brand text-white"
                    : "rounded-tl-sm bg-sky-50 text-ink ring-1 ring-inset ring-sky-200"
                }`}
              >
                {m.body}
              </div>
              <div className="mt-0.5 text-[10px] text-muted">{fmt(m.created_at)}</div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function fmt(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}
