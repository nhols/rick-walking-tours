import { createClient } from "@supabase/supabase-js";
import type {
  Chapter,
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
    .select("id,status,title,input,approved_plan_id,updated_at")
    .order("updated_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Tour[];
}

export async function loadTourBundle(tourId: string): Promise<TourBundle> {
  const [tourResult, plansResult, outputResult, eventsResult] = await Promise.all([
    supabase
      .from("tours")
      .select("id,status,title,input,approved_plan_id,updated_at")
      .eq("id", tourId)
      .single(),
    supabase
      .from("tour_plan_revisions")
      .select("id,revision,feedback,payload")
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
      .select("details")
      .eq("tour_id", tourId)
      .order("created_at")
  ]);

  const error =
    tourResult.error ?? plansResult.error ?? outputResult.error ?? eventsResult.error;
  if (error) throw error;

  const payload = outputResult.data?.payload as { chapters?: Chapter[] } | undefined;

  return {
    tour: tourResult.data as Tour,
    plans: (plansResult.data ?? []) as TourPlan[],
    chapters: payload?.chapters ?? [],
    statusEvents: (eventsResult.data ?? []) as TourStatusEvent[]
  };
}

export async function loadCreditBalance(): Promise<number> {
  const { data, error } = await supabase.from("credit_transactions").select("delta");
  if (error) throw error;
  return (data ?? []).reduce((sum, row) => sum + Number(row.delta), 0);
}
