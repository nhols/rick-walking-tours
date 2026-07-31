import { supabase } from "./supabase";

export async function markTourCompleted(tourId: string): Promise<string> {
  const { data, error } = await supabase.rpc("complete_tour", {
    p_tour_id: tourId
  });
  if (error) throw error;
  return String(data);
}

export async function unmarkTourCompleted(tourId: string): Promise<void> {
  const { error } = await supabase
    .from("tour_completions")
    .delete()
    .eq("tour_id", tourId);
  if (error) throw error;
}
