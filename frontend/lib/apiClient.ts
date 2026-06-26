import { supabase } from "./supabaseClient";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }

  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text();
    if (res.status === 503) {
      throw new Error("New update incoming — please try again shortly.");
    }
    throw new Error(`API ${res.status}: ${body}`);
  }
  return (await res.json()) as T;
}
