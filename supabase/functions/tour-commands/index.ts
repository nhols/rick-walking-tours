import { createClient } from "npm:@supabase/supabase-js@2";
import { invokeWorker } from "../_shared/worker-invoker.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS"
};

interface CommandResult {
  tour_id: string;
  job_id: string;
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

    await invokeWorker(result.job_id);
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
  if (!data || typeof data.tour_id !== "string" || typeof data.job_id !== "string") {
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
