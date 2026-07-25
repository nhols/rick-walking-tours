export type TourStatus =
  | "researching"
  | "awaiting_review"
  | "writing_chapters"
  | "generating_audio"
  | "ready"
  | "failed";

export interface TourInput {
  location: string;
  request: string;
  min_stops: number;
  max_stops: number;
  max_checkpoint_distance_km: number;
  voice: string;
  voice_style?: string | null;
  tts_model?: string | null;
  audio_format: string;
}

export interface Tour {
  id: string;
  owner_id: string;
  status: TourStatus;
  title: string | null;
  input: TourInput;
  approved_plan_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Checkpoint {
  id: string;
  position: number;
  title: string;
  description: string;
  route_reasoning: string;
  distance_tool_place_name: string;
  lat: number;
  lon: number;
  formatted_address: string | null;
}

export interface PlanPayload {
  narrative_arc: string;
  checkpoints: Checkpoint[];
}

export interface TourPlan {
  id: string;
  tour_id: string;
  revision: number;
  feedback: string | null;
  payload: PlanPayload;
  created_at: string;
}

export interface PlanWithCheckpoints extends Omit<TourPlan, "payload"> {
  narrative_arc: string;
  checkpoints: Checkpoint[];
}

export interface Chapter {
  id: string;
  checkpoint_id: string;
  position: number;
  title: string;
  narration: string;
  audio_path: string | null;
  duration_seconds: number | null;
}

export interface TourStatusEvent {
  id: string;
  tour_id: string;
  status: TourStatus;
  details: { error?: string } | null;
  created_at: string;
}

export interface TourBundle {
  tour: Tour;
  plans: PlanWithCheckpoints[];
  chapters: Chapter[];
  statusEvents: TourStatusEvent[];
}

export interface DownloadedTour {
  tourId: string;
  bundle: TourBundle;
  savedAt: string;
}
