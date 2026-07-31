export type TourStatus =
  | "researching"
  | "awaiting_review"
  | "writing_chapters"
  | "generating_audio"
  | "ready"
  | "failed";

export const ACTIVE_STATUSES: TourStatus[] = [
  "researching",
  "writing_chapters",
  "generating_audio"
];

export const STATUS_LABELS: Record<TourStatus, string> = {
  researching: "Researching checkpoints",
  awaiting_review: "Awaiting your review",
  writing_chapters: "Writing chapters",
  generating_audio: "Generating audio",
  ready: "Ready to walk",
  failed: "Needs attention"
};

export interface TourInput {
  location: string;
  request: string;
  min_stops?: number;
  max_stops?: number;
  max_checkpoint_distance_km?: number;
}

export interface Tour {
  id: string;
  owner_id: string;
  status: TourStatus;
  title: string | null;
  input: TourInput;
  approved_plan_id: string | null;
  is_public: boolean;
  updated_at: string;
  start_lat: number | null;
  start_lon: number | null;
  completed_at?: string | null;
  average_rating?: number | null;
  review_count?: number;
}

export interface ProfileStats {
  credits: number;
  created: {
    ready_tours: number;
    public_tours: number;
    distance_meters: number;
    duration_seconds: number;
  };
  completed: {
    tours: number;
    distance_meters: number;
    duration_seconds: number;
  };
  community: {
    completions: number;
    unique_walkers: number;
    distance_meters: number;
    duration_seconds: number;
  };
  reviews: {
    left_count: number;
    left_average: number | null;
    owned_count: number;
    owned_average: number | null;
  };
}

export interface Checkpoint {
  id: string;
  position: number;
  title: string;
  description: string;
  lat: number;
  lon: number;
  formatted_address: string | null;
}

export interface GeoPosition {
  lat: number;
  lon: number;
}

export interface RouteLeg {
  distance_meters: number;
  duration_seconds: number;
  start: GeoPosition | null;
  end: GeoPosition | null;
}

export interface WalkingRoute {
  provider: string;
  geometry: {
    type: "LineString";
    coordinates: [number, number][];
  };
  distance_meters: number;
  duration_seconds: number;
  legs: RouteLeg[];
  warnings: string[];
}

export interface PlanPayload {
  narrative_arc: string;
  checkpoints: Checkpoint[];
  response_to_user?: string | null;
  route?: WalkingRoute | null;
}

export interface TourPlan {
  id: string;
  revision: number;
  feedback: string | null;
  payload: PlanPayload;
}

export interface Chapter {
  id: string;
  checkpoint_id: string;
  position: number;
  title: string;
  narration: string;
  audio_path: string | null;
}

export interface TourAssistantTextContent {
  type: "text";
  text: string;
}

export interface TourAssistantInput {
  version: 1;
  content: TourAssistantTextContent[];
  context: {
    selected_chapter_id: string;
    chapter_playback_seconds: number;
  };
}

export interface TourAssistantOutput {
  version: 1;
  content: TourAssistantTextContent[];
}

export interface TourAssistantTurn {
  thread_id: string;
  turn: number;
  input: TourAssistantInput;
  output: TourAssistantOutput;
  created_at: string;
}

export interface TourStatusEvent {
  details: { error?: string } | null;
}

export interface TourReview {
  id: string;
  tour_id: string;
  user_id: string;
  rating: number;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface TourBundle {
  tour: Tour;
  plans: TourPlan[];
  chapters: Chapter[];
  statusEvents: TourStatusEvent[];
  reviews: TourReview[];
}
