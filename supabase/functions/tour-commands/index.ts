import { createClient } from "npm:@supabase/supabase-js@2";
import { invokeWorker, type WorkerEvent } from "../_shared/worker-invoker.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS"
};

interface CommandResult {
  tour_id: string;
  run_id: string;
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
    let workerAction: WorkerEvent["action"];
    if (action === "create") {
      result = await command(admin, "enqueue_tour_creation", {
        p_owner_id: userData.user.id,
        p_location: string(body.location, "location"),
        p_request: string(body.request, "request"),
        p_voice: optionalString(body.voice) ?? "Kore",
        p_voice_style: optionalString(body.voice_style),
        p_tts_model: optionalString(body.tts_model),
        p_audio_format: optionalString(body.audio_format) ?? "wav",
        p_idempotency_key: `${userData.user.id}:${idempotencyKey}`
      });
      workerAction = "plan";
    } else if (action === "feedback") {
      result = await command(admin, "enqueue_tour_feedback", {
        p_owner_id: userData.user.id,
        p_tour_id: string(body.tour_id, "tour_id"),
        p_plan_id: string(body.plan_id, "plan_id"),
        p_feedback: string(body.feedback, "feedback"),
        p_idempotency_key: `${userData.user.id}:${idempotencyKey}`
      });
      workerAction = "plan";
    } else if (action === "approve") {
      result = await command(admin, "enqueue_tour_production", {
        p_owner_id: userData.user.id,
        p_tour_id: string(body.tour_id, "tour_id"),
        p_plan_id: string(body.plan_id, "plan_id"),
        p_idempotency_key: `${userData.user.id}:${idempotencyKey}`
      });
      workerAction = "produce";
    } else {
      return json({ error: "Unknown action" }, 400);
    }

    await invokeWorker({ ...result, action: workerAction });
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
  if (!data || typeof data.tour_id !== "string" || typeof data.run_id !== "string") {
    throw new Error("Command did not return a tour and run ID");
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
