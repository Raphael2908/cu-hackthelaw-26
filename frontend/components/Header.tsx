"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getRole, subscribeRole, ROLE_HOME, type Role } from "@/lib/role";
import { RoleToggle } from "./RoleToggle";

// Navigation follows the role: the partner supervises cases, the associate works their inbox.
// You move between the two worlds with the role toggle (right), not a shared link.
const NAV_BY_ROLE: Record<Role, { href: string; label: string }[]> = {
  partner: [
    { href: "/", label: "Cases" },
    { href: "/track-record", label: "Track record" },
  ],
  associate: [{ href: "/inbox", label: "My inbox" }],
};

export function Header() {
  const pathname = usePathname();
  const [role, setRole] = useState<Role>("partner");

  useEffect(() => {
    setRole(getRole());
    return subscribeRole(() => setRole(getRole()));
  }, []);

  const nav = NAV_BY_ROLE[role];

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-paper/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-6">
        <Link href={ROLE_HOME[role]} className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand text-sm font-bold text-white">
            SC
          </span>
          <span className="text-[15px] font-semibold tracking-tight text-ink">
            Supervision Cockpit
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {nav.map((item) => {
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
