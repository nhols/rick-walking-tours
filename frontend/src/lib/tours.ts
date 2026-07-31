import type {
  Chapter,
  Tour,
  TourBundle,
  TourPlan,
  TourReview,
  TourStatusEvent
} from "../types";
import { supabase } from "./supabase";

const tourColumns =
  "id,owner_id,status,title,input,approved_plan_id,is_public,updated_at,start_lat,start_lon";

export async function loadOwnedTours(ownerId: string): Promise<Tour[]> {
  const { data, error } = await supabase
    .from("tours")
    .select(tourColumns)
    .eq("owner_id", ownerId)
    .order("updated_at", { ascending: false });
  if (error) throw error;
  return attachCompletions((data ?? []) as Tour[]);
}

export async function loadLibraryTours(ownerId: string): Promise<Tour[]> {
  const { data, error } = await supabase
    .from("tours")
    .select(tourColumns)
    .eq("status", "ready")
    .or(`owner_id.eq.${ownerId},is_public.eq.true`)
    .order("updated_at", { ascending: false });
  if (error) throw error;

  const tours = (data ?? []) as Tour[];
  if (tours.length === 0) return tours;

  const [reviewResult, completedTours] = await Promise.all([
    supabase
      .from("tour_reviews")
      .select("tour_id,rating")
      .in("tour_id", tours.map((tour) => tour.id)),
    attachCompletions(tours)
  ]);
  const { data: reviewData, error: reviewError } = reviewResult;
  if (reviewError) throw reviewError;

  const ratings = new Map<string, number[]>();
  for (const review of reviewData ?? []) {
    const values = ratings.get(review.tour_id) ?? [];
    values.push(Number(review.rating));
    ratings.set(review.tour_id, values);
  }

  return completedTours.map((tour) => {
    const values = ratings.get(tour.id) ?? [];
    return {
      ...tour,
      average_rating: values.length
        ? values.reduce((sum, rating) => sum + rating, 0) / values.length
        : null,
      review_count: values.length
    };
  });
}

async function attachCompletions(tours: Tour[]): Promise<Tour[]> {
  if (tours.length === 0) return tours;
  const { data, error } = await supabase
    .from("tour_completions")
    .select("tour_id,completed_at")
    .in("tour_id", tours.map((tour) => tour.id));
  if (error) throw error;

  const completedAtByTour = new Map(
    (data ?? []).map((completion) => [completion.tour_id, completion.completed_at])
  );
  return tours.map((tour) => ({
    ...tour,
    completed_at: completedAtByTour.get(tour.id) ?? null
  }));
}

export async function loadTourBundle(tourId: string): Promise<TourBundle> {
  const [
    tourResult,
    plansResult,
    outputResult,
    eventsResult,
    reviewsResult
  ] = await Promise.all([
    supabase
      .from("tours")
      .select(tourColumns)
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
      .order("created_at"),
    supabase
      .from("tour_reviews")
      .select("id,tour_id,user_id,rating,body,created_at,updated_at")
      .eq("tour_id", tourId)
      .order("created_at", { ascending: false })
  ]);

  const error =
    tourResult.error ?? plansResult.error ?? outputResult.error ??
    eventsResult.error ?? reviewsResult.error;
  if (error) throw error;

  const payload = outputResult.data?.payload as { chapters?: Chapter[] } | undefined;

  return {
    tour: tourResult.data as Tour,
    plans: (plansResult.data ?? []) as TourPlan[],
    chapters: payload?.chapters ?? [],
    statusEvents: (eventsResult.data ?? []) as TourStatusEvent[],
    reviews: (reviewsResult.data ?? []) as TourReview[]
  };
}

export async function setTourPublic(tourId: string, isPublic: boolean) {
  const { error } = await supabase
    .from("tours")
    .update({ is_public: isPublic })
    .eq("id", tourId);
  if (error) throw error;
}
