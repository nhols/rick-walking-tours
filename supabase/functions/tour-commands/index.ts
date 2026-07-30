import { createClient } from "npm:@supabase/supabase-js@2";
import {
  invokeTourAssistant,
  invokeWorker,
  type TourAssistantInput
} from "../_shared/worker-invoker.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS"
};

interface CommandResult {
  tour_id: string;
  job_id: string;
  invoke_worker?: boolean;
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);

  try {
    const authorization = request.headers.get("Authorization");
    if (!authorization) return json({ error: "Authentication required" }, 401);

    const url = required("SUPABASE_URL");
    const publishableKey =
      Deno.env.get("SUPABASE_ANON_KEY") ?? required("SUPABASE_PUBLISHABLE_KEY");
    const serviceKey =
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? required("SUPABASE_SECRET_KEY");
    const userClient = createClient(url, publishableKey, {
      global: { headers: { Authorization: authorization } },
      auth: { persistSession: false }
    });
    const { data: userData, error: userError } = await userClient.auth.getUser();
    if (userError || !userData.user) return json({ error: "Invalid session" }, 401);

    const body = await request.json() as Record<string, unknown>;
    const action = string(body.action, "action");
    const idempotencyKey = optionalString(body.idempotency_key) ?? crypto.randomUUID();

    if (action === "ask") {
      const tourId = string(body.tour_id, "tour_id");
      const { data: visibleTour, error: tourError } = await userClient
        .from("tours")
        .select("id")
        .eq("id", tourId)
        .maybeSingle();
      if (tourError) throw tourError;
      if (!visibleTour) return json({ error: "Tour not found" }, 404);

      const answer = await invokeTourAssistant({
        action: "ask_tour",
        tour_id: tourId,
        user_id: userData.user.id,
        input: tourAssistantInput(body.input)
      });
      return json(answer, 200);
    }

    const admin = createClient(url, serviceKey, { auth: { persistSession: false } });

    let result: CommandResult;
    if (action === "create") {
      result = await command(admin, "enqueue_tour_creation", {
        p_owner_id: userData.user.id,
        p_input: tourInput(body),
        p_idempotency_key: `${userData.user.id}:${idempotencyKey}`
      });
    } else if (action === "feedback") {
      result = await command(admin, "enqueue_tour_feedback", {
        p_owner_id: userData.user.id,
        p_tour_id: string(body.tour_id, "tour_id"),
        p_plan_id: string(body.plan_id, "plan_id"),
        p_feedback: string(body.feedback, "feedback"),
        p_idempotency_key: `${userData.user.id}:${idempotencyKey}`
      });
    } else if (action === "approve") {
      result = await command(admin, "enqueue_tour_production", {
        p_owner_id: userData.user.id,
        p_tour_id: string(body.tour_id, "tour_id"),
        p_plan_id: string(body.plan_id, "plan_id"),
        p_idempotency_key: `${userData.user.id}:${idempotencyKey}`
      });
    } else {
      return json({ error: "Unknown action" }, 400);
    }

    if (result.invoke_worker !== false) await invokeWorker(result.job_id);
    return json(result, 202);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Command failed";
    console.error(message);
    return json({ error: message }, 400);
  }
});

async function command(
  client: ReturnType<typeof createClient>,
  name: string,
  args: Record<string, unknown>
): Promise<CommandResult> {
  const { data, error } = await client.rpc(name, args);
  if (error) throw error;
  if (
    !data ||
    typeof data.tour_id !== "string" ||
    typeof data.job_id !== "string" ||
    (data.invoke_worker !== undefined && typeof data.invoke_worker !== "boolean")
  ) {
    throw new Error("Command did not return a tour and job ID");
  }
  return data as CommandResult;
}

function string(value: unknown, name: string): string {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${name} is required`);
  return value.trim();
}

function optionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function number(value: unknown, name: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${name} must be a number`);
  }
  return value;
}

function integer(value: unknown, name: string): number {
  const parsed = number(value, name);
  if (!Number.isInteger(parsed)) throw new Error(`${name} must be an integer`);
  return parsed;
}

function tourInput(body: Record<string, unknown>): Record<string, unknown> {
  const minStops = integer(body.min_stops ?? 2, "min_stops");
  const maxStops = integer(body.max_stops ?? 10, "max_stops");
  if (minStops > maxStops) throw new Error("min_stops must not exceed max_stops");
  return {
    location: string(body.location, "location"),
    request: string(body.request, "request"),
    min_stops: minStops,
    max_stops: maxStops,
    max_checkpoint_distance_km: number(
      body.max_checkpoint_distance_km ?? 10,
      "max_checkpoint_distance_km"
    ),
    voice: optionalString(body.voice) ?? "Kore",
    voice_style: optionalString(body.voice_style),
    tts_model: optionalString(body.tts_model),
    audio_format: optionalString(body.audio_format) ?? "wav"
  };
}

function tourAssistantInput(value: unknown): TourAssistantInput {
  if (!isRecord(value) || value.version !== 1 || !Array.isArray(value.content)) {
    throw new Error("input must be a version 1 assistant document");
  }
  if (value.content.length === 0) throw new Error("input content is required");
  const content = value.content.map((block) => {
    if (!isRecord(block) || block.type !== "text") {
      throw new Error("Only text input is currently supported");
    }
    return { type: "text" as const, text: string(block.text, "input text") };
  });
  if (content.map((block) => block.text).join("\n\n").length > 2_000) {
    throw new Error("input text must be 2000 characters or fewer");
  }
  if (!isRecord(value.context)) throw new Error("input context is required");
  const playbackSeconds = number(
    value.context.chapter_playback_seconds,
    "chapter_playback_seconds"
  );
  if (playbackSeconds < 0) {
    throw new Error("chapter_playback_seconds must not be negative");
  }
  return {
    version: 1,
    content,
    context: {
      selected_chapter_id: string(
        value.context.selected_chapter_id,
        "selected_chapter_id"
      ),
      chapter_playback_seconds: playbackSeconds
    }
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function required(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function json(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" }
  });
}
