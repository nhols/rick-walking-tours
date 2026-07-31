import { supabase } from "./supabase";

export interface EditableTourReview {
  rating: number;
  body: string;
}

export async function loadTourReview(
  tourId: string,
  userId: string
): Promise<EditableTourReview | null> {
  const { data, error } = await supabase
    .from("tour_reviews")
    .select("rating,body")
    .eq("tour_id", tourId)
    .eq("user_id", userId)
    .maybeSingle();
  if (error) throw error;
  return data ? { rating: Number(data.rating), body: data.body } : null;
}

export async function saveTourReview(
  tourId: string,
  userId: string,
  rating: number,
  body: string
) {
  const { error } = await supabase.from("tour_reviews").upsert(
    {
      tour_id: tourId,
      user_id: userId,
      rating,
      body
    },
    { onConflict: "tour_id,user_id" }
  );
  if (error) throw error;
}

export async function deleteTourReview(reviewId: string) {
  const { error } = await supabase
    .from("tour_reviews")
    .delete()
    .eq("id", reviewId);
  if (error) throw error;
}
