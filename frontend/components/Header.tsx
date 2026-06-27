"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { RoleToggle } from "./RoleToggle";

const NAV = [
  { href: "/", label: "Cases" },
  { href: "/inbox", label: "Inbox" },
  { href: "/track-record", label: "Track record" },
];

export function Header() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-sm font-bold text-white">
            SC
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-ink">
            Supervision Cockpit
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  active ? "bg-brand-soft text-brand" : "text-muted hover:text-ink"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto">
          <RoleToggle />
        </div>
      </div>
    </header>
  );
}
