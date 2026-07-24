import { supabase } from "./supabase";

export interface CommandAccepted {
  tour_id: string;
  run_id: string;
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
  if (error) throw error;
  return data as T;
}
