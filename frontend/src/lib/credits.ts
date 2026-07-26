import { supabase } from "./supabase";

export async function loadCreditBalance(): Promise<number> {
  const { data, error } = await supabase.from("credit_transactions").select("delta");
  if (error) throw error;
  return (data ?? []).reduce((sum, row) => sum + Number(row.delta), 0);
}
