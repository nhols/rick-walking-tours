import { supabase } from "./supabase";
import type { TourAssistantTurn } from "../types";


export async function loadTourAssistantTurns(
  tourId: string
): Promise<TourAssistantTurn[]> {
  const { data: latest, error: latestError } = await supabase
    .from("tour_assistant_turns")
    .select("thread_id")
    .eq("tour_id", tourId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (latestError) throw latestError;
  if (!latest) return [];

  const { data, error } = await supabase
    .from("tour_assistant_turns")
    .select("thread_id,turn,input,output,created_at")
    .eq("tour_id", tourId)
    .eq("thread_id", latest.thread_id)
    .order("turn");
  if (error) throw error;
  return (data ?? []) as TourAssistantTurn[];
}
