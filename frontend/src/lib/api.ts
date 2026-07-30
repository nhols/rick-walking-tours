import { FunctionsHttpError } from "@supabase/supabase-js";
import { supabase } from "./supabase";
import type { TourAssistantInput, TourAssistantOutput } from "../types";

interface CommandAccepted {
  tour_id: string;
  job_id: string;
}

interface TourAssistantReply {
  thread_id: string;
  turn: number;
  input: TourAssistantInput;
  output: TourAssistantOutput;
}

export interface CreateTourRequest {
  location: string;
  request: string;
  min_stops: number;
  max_stops: number;
  max_checkpoint_distance_km: number;
}

export function createTour(body: CreateTourRequest): Promise<CommandAccepted> {
  return workerCommand("create", body);
}

export function reviseTour(
  tourId: string,
  planId: string,
  feedback: string
): Promise<CommandAccepted> {
  return workerCommand("feedback", {
    tour_id: tourId,
    plan_id: planId,
    feedback
  });
}

export function approveTour(
  tourId: string,
  planId: string
): Promise<CommandAccepted> {
  return workerCommand("approve", { tour_id: tourId, plan_id: planId });
}

export async function askTourAssistant(
  tourId: string,
  selectedChapterId: string,
  chapterPlaybackSeconds: number,
  message: string
): Promise<TourAssistantReply> {
  const { data, error } = await supabase.functions.invoke("tour-commands", {
    body: {
      action: "ask",
      tour_id: tourId,
      input: {
        version: 1,
        content: [{ type: "text", text: message }],
        context: {
          selected_chapter_id: selectedChapterId,
          chapter_playback_seconds: chapterPlaybackSeconds
        }
      }
    }
  });
  if (error) await throwFunctionError(error);
  if (
    !data ||
    typeof data.thread_id !== "string" ||
    typeof data.turn !== "number" ||
    !isTourAssistantInput(data.input) ||
    !isTourAssistantOutput(data.output)
  ) {
    throw new Error("Tour assistant returned an invalid response");
  }
  return data as TourAssistantReply;
}

function isTourAssistantInput(value: unknown): value is TourAssistantInput {
  if (!isRecord(value) || !isRecord(value.context)) return false;
  return typeof value.context.selected_chapter_id === "string" &&
    typeof value.context.chapter_playback_seconds === "number" &&
    isTourAssistantDocument(value);
}

function isTourAssistantOutput(value: unknown): value is TourAssistantOutput {
  return isTourAssistantDocument(value);
}

function isTourAssistantDocument(value: unknown): value is TourAssistantOutput {
  return isRecord(value) &&
    value.version === 1 &&
    Array.isArray(value.content) &&
    value.content.length > 0 &&
    value.content.every(
      (block) => isRecord(block) &&
        block.type === "text" &&
        typeof block.text === "string"
    );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

async function workerCommand(
  action: "create" | "feedback" | "approve",
  body: object
): Promise<CommandAccepted> {
  const { data, error } = await supabase.functions.invoke("tour-commands", {
    body: {
      action,
      idempotency_key: crypto.randomUUID(),
      ...body
    }
  });
  if (error) await throwFunctionError(error);
  if (
    !data ||
    typeof data.tour_id !== "string" ||
    typeof data.job_id !== "string"
  ) {
    throw new Error("Tour command returned an invalid response");
  }
  return data;
}

async function throwFunctionError(error: unknown): Promise<never> {
  if (error instanceof FunctionsHttpError) {
    const response = error.context as Response;
    const payload = await response.clone().json().catch(() => null) as {
      error?: unknown;
    } | null;
    if (response.status === 401) await supabase.auth.signOut({ scope: "local" });
    throw new Error(
      typeof payload?.error === "string" ? payload.error : error.message
    );
  }
  if (error instanceof Error) throw error;
  throw new Error("Tour command failed");
}
