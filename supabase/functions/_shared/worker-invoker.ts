import { InvokeCommand, LambdaClient } from "npm:@aws-sdk/client-lambda@3";

export async function invokeWorker(jobId: string): Promise<void> {
  const mode = Deno.env.get("WORKER_INVOKER") ?? "local";
  if (mode !== "local" && mode !== "aws") {
    throw new Error(`Unsupported WORKER_INVOKER: ${mode}`);
  }
  const local = mode === "local";
  const functionName = local
    ? Deno.env.get("WORKER_FUNCTION_NAME") ?? "WorkerFunction"
    : required("WORKER_FUNCTION_NAME");
  const client = new LambdaClient({
    region: local ? "eu-west-2" : required("AWS_REGION"),
    endpoint: local ? "http://host.docker.internal:3001" : undefined,
    credentials: local
      ? { accessKeyId: "local", secretAccessKey: "local" }
      : undefined
  });
  const response = await client.send(
    new InvokeCommand({
      FunctionName: functionName,
      InvocationType: "Event",
      Payload: new TextEncoder().encode(JSON.stringify({ job_id: jobId }))
    })
  );
  if (response.StatusCode !== 202) {
    throw new Error(`Lambda rejected the worker event (${response.StatusCode})`);
  }
}

function required(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`${name} is required`);
  return value;
}
