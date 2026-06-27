"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getRole, setRole, subscribeRole, type Role, ROLE_HOME, ROLE_IDENTITY } from "@/lib/role";

export function RoleToggle() {
  const router = useRouter();
  const [role, setLocal] = useState<Role>("partner");

  useEffect(() => {
    setLocal(getRole());
    return subscribeRole(() => setLocal(getRole()));
  }, []);

  // Switching role is switching view: route to that role's home so the toggle — not a nav link — is
  // how you enter the associate's workspace.
  const choose = (r: Role) => {
    if (r === role) return;
    setRole(r);
    setLocal(r);
    router.push(ROLE_HOME[r]);
  };

  return (
    <div className="flex items-center gap-3">
      <div className="hidden text-right sm:block">
        <div className="text-xs font-medium text-ink">{ROLE_IDENTITY[role].label}</div>
        <div className="text-[11px] text-muted">{ROLE_IDENTITY[role].email}</div>
      </div>
      <div className="inline-flex rounded-lg bg-canvas p-0.5 ring-1 ring-inset ring-line">
        {(["partner", "associate"] as Role[]).map((r) => (
          <button
            key={r}
            onClick={() => choose(r)}
            className={`rounded-md px-3 py-1.5 text-xs font-semibold capitalize transition-colors ${
              role === r ? "bg-brand text-white shadow-sm" : "text-muted hover:text-ink"
            }`}
          >
            {r}
          </button>
        ))}
      </div>
    </div>
  );
}
