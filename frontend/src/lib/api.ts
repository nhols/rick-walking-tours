import { FunctionsHttpError } from "@supabase/supabase-js";
import { supabase } from "./supabase";

export interface CommandAccepted {
  tour_id: string;
  job_id: string;
}

export async function workerCommand<T>(
  action: "create" | "feedback" | "approve",
  body: Record<string, unknown>
): Promise<T> {
  const { data, error } = await supabase.functions.invoke("tour-commands", {
    body: {
      action,
      idempotency_key: crypto.randomUUID(),
      ...body
    }
  });
  if (error instanceof FunctionsHttpError) {
    const response = error.context as Response;
    const payload = await response.clone().json().catch(() => null) as { error?: unknown } | null;
    if (response.status === 401) await supabase.auth.signOut({ scope: "local" });
    throw new Error(typeof payload?.error === "string" ? payload.error : error.message);
  }
  if (error) throw error;
  return data as T;
}
