import { InvokeCommand, LambdaClient } from "npm:@aws-sdk/client-lambda@3";

export interface WorkerEvent {
  job_id: string;
  tour_id: string;
  kind: "plan" | "revise" | "produce";
}

export async function invokeWorker(event: WorkerEvent): Promise<void> {
  const mode = Deno.env.get("WORKER_INVOKER") ?? "local";
  if (mode === "local") {
    await invokeLocalWorker(event);
    return;
  }
  if (mode !== "aws") throw new Error(`Unsupported WORKER_INVOKER: ${mode}`);

  const functionName = required("WORKER_FUNCTION_NAME");
  const client = new LambdaClient({ region: required("AWS_REGION") });
  const response = await client.send(
    new InvokeCommand({
      FunctionName: functionName,
      InvocationType: "Event",
      Payload: new TextEncoder().encode(JSON.stringify(event))
    })
  );
  if (response.StatusCode !== 202) {
    throw new Error(`Lambda rejected the worker event (${response.StatusCode})`);
  }
}

async function invokeLocalWorker(event: WorkerEvent): Promise<void> {
  const url =
    Deno.env.get("LOCAL_WORKER_URL") ??
    "http://host.docker.internal:8001/internal/invoke";
  const token =
    Deno.env.get("LOCAL_WORKER_TOKEN") ?? required("SUPABASE_SERVICE_ROLE_KEY");
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Local-Worker-Token": token
    },
    body: JSON.stringify(event)
  });
  if (!response.ok) {
    throw new Error(`Local worker rejected the event (${response.status})`);
  }
}

function required(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`${name} is required`);
  return value;
}
