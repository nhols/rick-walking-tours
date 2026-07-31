import type { ProfileStats } from "../types";
import { supabase } from "./supabase";

export async function loadProfileStats(): Promise<ProfileStats> {
  const { data, error } = await supabase.rpc("get_profile_stats");
  if (error) throw error;
  if (!data) throw new Error("Profile statistics are unavailable");
  return data as ProfileStats;
}
