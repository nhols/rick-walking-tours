export type TourStatus =
  | "researching"
  | "planning_route"
  | "awaiting_review"
  | "writing_chapters"
  | "generating_audio"
  | "ready"
  | "failed";

export interface Tour {
  id: string;
  owner_id: string;
  location: string;
  request: string;
  status: TourStatus;
  title: string | null;
  narrative_arc: string | null;
  voice: string;
  current_plan_revision: number;
  approved_plan_id: string | null;
  progress_message: string | null;
  progress_current: number | null;
  progress_total: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface TourPlan {
  id: string;
  tour_id: string;
  revision: number;
  route_plan: { narrative_arc?: string };
  parent_plan_id: string | null;
  feedback: string | null;
  created_at: string;
}

export interface Checkpoint {
  id: string;
  tour_id: string;
  plan_id: string;
  position: number;
  title: string;
  description: string;
  route_reasoning: string;
  distance_tool_place_name: string;
  lat: number;
  lon: number;
  formatted_address: string | null;
}

export interface Chapter {
  id: string;
  tour_id: string;
  plan_id: string;
  checkpoint_id: string;
  position: number;
  title: string;
  narration: string;
  status: "written" | "ready";
  audio_path: string | null;
  media_type: string | null;
  duration_seconds: number | null;
}

export interface PlanWithCheckpoints extends TourPlan {
  checkpoints: Checkpoint[];
}

export interface TourBundle {
  tour: Tour;
  plans: PlanWithCheckpoints[];
  chapters: Chapter[];
}

export interface DownloadedTour {
  tourId: string;
  bundle: TourBundle;
  savedAt: string;
}
