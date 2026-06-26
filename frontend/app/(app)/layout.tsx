import { AuthGate } from "@/components/AuthGate";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <div className="mx-auto max-w-5xl px-6 py-8">{children}</div>
    </AuthGate>
  );
}
