import { supabase } from "./supabase";

export async function saveTourReview(
  tourId: string,
  userId: string,
  rating: number,
  body: string,
  reviewId?: string
) {
  const query = reviewId
    ? supabase.from("tour_reviews").update({ rating, body }).eq("id", reviewId)
    : supabase.from("tour_reviews").insert({
        tour_id: tourId,
        user_id: userId,
        rating,
        body
      });
  const { error } = await query;
  if (error) throw error;
}

export async function deleteTourReview(reviewId: string) {
  const { error } = await supabase
    .from("tour_reviews")
    .delete()
    .eq("id", reviewId);
  if (error) throw error;
}
