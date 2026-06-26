"use client";

import Link from "next/link";
import { useSession } from "@/lib/useSession";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { session, loading } = useSession();

  if (loading) {
    return <div className="p-8 text-neutral-500">Loading…</div>;
  }

  if (!session) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4">
        <p className="text-neutral-600">Please sign in to continue.</p>
        <Link href="/login" className="rounded-md bg-black px-4 py-2 text-white">
          Sign in
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
