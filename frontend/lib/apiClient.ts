// The SINGLE gateway for every backend call. All endpoint wrappers (lib/api.ts) go through here.
// It injects the current demo role's identity headers and normalises errors.

import { getRole, ROLE_IDENTITY } from "./role";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail || `Request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const role = getRole();
  const identity = ROLE_IDENTITY[role];

  const headers = new Headers(init?.headers);
  headers.set("X-User-Email", identity.email);
  headers.set("X-User-Role", role);
  // Let the browser set the multipart boundary for FormData uploads; only default JSON otherwise.
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, "Cannot reach the backend. Is it running on :8000?");
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
      else if (body?.detail) detail = JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
