import { createClient } from "@supabase/supabase-js";

export function createSupabaseClient(accessToken?: string) {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "http://localhost:5000";
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

  const options = accessToken
    ? { global: { headers: { Authorization: `Bearer ${accessToken}` } } }
    : {};

  return createClient(supabaseUrl, supabaseKey, options);
}

/**
 * Subscribe to batch status updates
 */
export function subscribeToBatch(
  batchId: string,
  onUpdate: (payload: Record<string, unknown>) => void,
) {
  const supabase = createSupabaseClient(); // real token required in prod, simplified here
  return supabase
    .channel(`batch:${batchId}`)
    .on(
      "postgres_changes",
      {
        event: "UPDATE",
        schema: "public",
        table: "batches",
        filter: `id=eq.${batchId}`,
      },
      (payload) => onUpdate(payload.new),
    )
    .subscribe();
}
