import { createClient } from "@supabase/supabase-js";
import type {
  Chapter,
  PlanWithCheckpoints,
  Tour,
  TourBundle,
  TourPlan,
  TourStatusEvent
} from "../types";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error("VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY are required");
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export async function loadTours(): Promise<Tour[]> {
  const { data, error } = await supabase
    .from("tours")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Tour[];
}

export async function loadTourBundle(tourId: string): Promise<TourBundle> {
  const [tourResult, plansResult, outputResult, eventsResult] = await Promise.all([
    supabase.from("tours").select("*").eq("id", tourId).single(),
    supabase
      .from("tour_plan_revisions")
      .select("id,tour_id,revision,feedback,payload,created_at")
      .eq("tour_id", tourId)
      .order("revision"),
    supabase
      .from("tour_outputs")
      .select("payload")
      .eq("tour_id", tourId)
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("tour_status_events")
      .select("*")
      .eq("tour_id", tourId)
      .order("created_at")
  ]);

  const error =
    tourResult.error ?? plansResult.error ?? outputResult.error ?? eventsResult.error;
  if (error) throw error;

  const plans = ((plansResult.data ?? []) as unknown as TourPlan[]).map(
    (plan): PlanWithCheckpoints => ({
      id: plan.id,
      tour_id: plan.tour_id,
      revision: plan.revision,
      feedback: plan.feedback,
      created_at: plan.created_at,
      narrative_arc: plan.payload.narrative_arc,
      checkpoints: plan.payload.checkpoints
    })
  );
  const payload = outputResult.data?.payload as { chapters?: Chapter[] } | undefined;

  return {
    tour: tourResult.data as Tour,
    plans,
    chapters: payload?.chapters ?? [],
    statusEvents: (eventsResult.data ?? []) as TourStatusEvent[]
  };
}

export async function loadCreditBalance(): Promise<number> {
  const { data, error } = await supabase.from("credit_transactions").select("delta");
  if (error) throw error;
  return (data ?? []).reduce((sum, row) => sum + Number(row.delta), 0);
}
