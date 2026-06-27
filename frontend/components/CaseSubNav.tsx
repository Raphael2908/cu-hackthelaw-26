"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Hints frame each tab in the partner's language so the destination is recognisable from the nav
// (H2 match-real-world / H6 recognition; addresses cognitive-walkthrough gap G3 — see DESIGN.md).
const TABS = [
  { slug: "plan", label: "Plan", hint: "Propose & approve who does what" },
  { slug: "cockpit", label: "Cockpit", hint: "Review flagged work & decide" },
  { slug: "audit", label: "Audit", hint: "Trace who did what, when" },
  { slug: "debrief", label: "Debrief", hint: "Case summary at close" },
];

export function CaseSubNav({ caseId, title }: { caseId: string; title?: string }) {
  const pathname = usePathname();
  return (
    <div className="border-b border-line bg-paper">
      <div className="mx-auto max-w-7xl px-6">
        {title ? (
          <div className="pt-5">
            <Link href="/" className="text-xs font-medium text-muted hover:text-brand">
              ← Cases
            </Link>
            <h1 className="mt-1 text-lg font-semibold tracking-tight text-ink">{title}</h1>
          </div>
        ) : null}
        <nav className="mt-3 flex gap-1">
          {TABS.map((tab) => {
            const href = `/cases/${caseId}/${tab.slug}`;
            const active = pathname === href;
            return (
              <Link
                key={tab.slug}
                href={href}
                title={tab.hint}
                aria-label={`${tab.label} — ${tab.hint}`}
                className={`border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors ${
                  active
                    ? "border-brand text-brand"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {tab.label}
                <span className="ml-2 hidden text-[11px] font-normal text-muted xl:inline">
                  {tab.hint}
                </span>
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
