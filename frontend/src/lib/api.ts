import { FunctionsHttpError } from "@supabase/supabase-js";
import { supabase } from "./supabase";

interface CommandAccepted {
  tour_id: string;
  job_id: string;
}

export interface CreateTourRequest {
  location: string;
  request: string;
  min_stops: number;
  max_stops: number;
  max_checkpoint_distance_km: number;
}

export function createTour(body: CreateTourRequest): Promise<CommandAccepted> {
  return workerCommand("create", body);
}

export function reviseTour(
  tourId: string,
  planId: string,
  feedback: string
): Promise<CommandAccepted> {
  return workerCommand("feedback", {
    tour_id: tourId,
    plan_id: planId,
    feedback
  });
}

export function approveTour(
  tourId: string,
  planId: string
): Promise<CommandAccepted> {
  return workerCommand("approve", { tour_id: tourId, plan_id: planId });
}

async function workerCommand(
  action: "create" | "feedback" | "approve",
  body: object
): Promise<CommandAccepted> {
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
  if (
    !data ||
    typeof data.tour_id !== "string" ||
    typeof data.job_id !== "string"
  ) {
    throw new Error("Tour command returned an invalid response");
  }
  return data;
}
