import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";

// In mock/local mode these may be blank; auth calls simply won't succeed until configured.
export const supabase = createClient(url || "http://localhost", key || "anon");
