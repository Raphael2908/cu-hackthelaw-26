"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { slug: "plan", label: "Plan" },
  { slug: "cockpit", label: "Cockpit" },
  { slug: "audit", label: "Audit" },
  { slug: "debrief", label: "Debrief" },
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
                className={`border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors ${
                  active
                    ? "border-brand text-brand"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
