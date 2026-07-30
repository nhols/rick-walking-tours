import { InvokeCommand, LambdaClient } from "npm:@aws-sdk/client-lambda@3";

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

export interface TourAssistantInvocation {
  action: "ask_tour";
  tour_id: string;
  user_id: string;
  input: TourAssistantInput;
}

export interface TourAssistantInvocationResult {
  thread_id: string;
  turn: number;
  input: TourAssistantInput;
  output: TourAssistantOutput;
}

export async function invokeWorker(jobId: string): Promise<void> {
  const client = lambdaClient();
  const response = await client.send(
    new InvokeCommand({
      FunctionName: functionName(),
      InvocationType: "Event",
      Payload: new TextEncoder().encode(JSON.stringify({ job_id: jobId }))
    })
  );
  if (response.StatusCode !== 202) {
    throw new Error(`Lambda rejected the worker event (${response.StatusCode})`);
  }
}

export async function invokeTourAssistant(
  event: TourAssistantInvocation
): Promise<TourAssistantInvocationResult> {
  const response = await lambdaClient().send(
    new InvokeCommand({
      FunctionName: functionName(),
      InvocationType: "RequestResponse",
      Payload: new TextEncoder().encode(JSON.stringify(event))
    })
  );
  const payload = response.Payload
    ? JSON.parse(new TextDecoder().decode(response.Payload)) as unknown
    : null;
  if (response.StatusCode !== 200 || response.FunctionError) {
    const errorMessage = isRecord(payload) && typeof payload.errorMessage === "string"
      ? payload.errorMessage
      : `Tour assistant failed (${response.StatusCode})`;
    throw new Error(errorMessage);
  }
  if (
    !isRecord(payload) ||
    typeof payload.thread_id !== "string" ||
    typeof payload.turn !== "number" ||
    !isTourAssistantInput(payload.input) ||
    !isTourAssistantOutput(payload.output)
  ) {
    throw new Error("Tour assistant returned an invalid response");
  }
  return payload as unknown as TourAssistantInvocationResult;
}

function lambdaClient(): LambdaClient {
  const mode = invocationMode();
  if (mode !== "local" && mode !== "aws") {
    throw new Error(`Unsupported WORKER_INVOKER: ${mode}`);
  }
  const local = mode === "local";
  return new LambdaClient({
    region: local ? "eu-west-2" : required("AWS_REGION"),
    endpoint: local ? "http://host.docker.internal:3001" : undefined,
    credentials: local
      ? { accessKeyId: "local", secretAccessKey: "local" }
      : undefined
  });
}

function invocationMode(): string {
  return Deno.env.get("WORKER_INVOKER") ?? "local";
}

function functionName(): string {
  return invocationMode() === "local"
    ? Deno.env.get("WORKER_FUNCTION_NAME") ?? "WorkerFunction"
    : required("WORKER_FUNCTION_NAME");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
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

function required(name: string): string {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`${name} is required`);
  return value;
}
