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
}

export interface Tour {
  id: string;
  status: TourStatus;
  title: string | null;
  input: TourInput;
  approved_plan_id: string | null;
  updated_at: string;
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

export interface PlanPayload {
  narrative_arc: string;
  checkpoints: Checkpoint[];
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

export interface TourStatusEvent {
  details: { error?: string } | null;
}

export interface TourBundle {
  tour: Tour;
  plans: TourPlan[];
  chapters: Chapter[];
  statusEvents: TourStatusEvent[];
}
