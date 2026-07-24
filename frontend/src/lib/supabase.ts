import { createClient } from "@supabase/supabase-js";
import type {
  Chapter,
  Checkpoint,
  PlanWithCheckpoints,
  Tour,
  TourBundle,
  TourPlan
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
  const [tourResult, plansResult, checkpointsResult, chaptersResult] =
    await Promise.all([
      supabase.from("tours").select("*").eq("id", tourId).single(),
      supabase
        .from("tour_plan_revisions")
        .select(
          "id,tour_id,revision,route_plan,parent_plan_id,feedback,created_at"
        )
        .eq("tour_id", tourId)
        .order("revision"),
      supabase
        .from("tour_checkpoints")
        .select("*")
        .eq("tour_id", tourId)
        .order("position"),
      supabase
        .from("tour_chapters")
        .select("*")
        .eq("tour_id", tourId)
        .order("position")
    ]);

  const error =
    tourResult.error ??
    plansResult.error ??
    checkpointsResult.error ??
    chaptersResult.error;
  if (error) throw error;

  const checkpoints = (checkpointsResult.data ?? []) as Checkpoint[];
  const plans = ((plansResult.data ?? []) as TourPlan[]).map(
    (plan): PlanWithCheckpoints => ({
      ...plan,
      checkpoints: checkpoints.filter((item) => item.plan_id === plan.id)
    })
  );

  return {
    tour: tourResult.data as Tour,
    plans,
    chapters: (chaptersResult.data ?? []) as Chapter[]
  };
}

export async function loadCreditBalance(): Promise<number> {
  const { data, error } = await supabase
    .from("credit_transactions")
    .select("delta");
  if (error) throw error;
  return (data ?? []).reduce((sum, row) => sum + Number(row.delta), 0);
}
