// Role state for the demo. Persisted in localStorage; the apiClient reads it to set auth headers.
// A tiny pub/sub lets the header + pages re-render when the role flips.

export type Role = "partner" | "associate";

const KEY = "sc-role";

export const ROLE_IDENTITY: Record<Role, { email: string; label: string }> = {
  partner: { email: "partner@firm.example", label: "Partner" },
  associate: { email: "amara@firm.example", label: "Associate" },
};

export function getRole(): Role {
  if (typeof window === "undefined") return "partner";
  const v = window.localStorage.getItem(KEY);
  return v === "associate" ? "associate" : "partner";
}

export function setRole(role: Role): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, role);
  window.dispatchEvent(new Event("sc-role-change"));
}

export function subscribeRole(cb: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("sc-role-change", cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener("sc-role-change", cb);
    window.removeEventListener("storage", cb);
  };
}
