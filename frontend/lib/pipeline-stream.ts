import { apiFetch } from "@/lib/client-api";
import type {
  EnrichBackfillResult,
  IngestResult,
  PipelineStepEvent,
  ObsidianExportResult,
} from "@/lib/types";

async function consumeSseStream<T>(
  path: string,
  onEvent: (event: PipelineStepEvent) => void,
  signal?: AbortSignal,
  body?: any,
): Promise<T> {
  const response = await apiFetch(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    timeoutMs: 600_000,
    signal,
  });

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Resposta sem stream do backend.");
  }

  // Handle stream reader cancellation when aborted
  if (signal) {
    signal.addEventListener("abort", () => {
      void reader.cancel().catch(() => {});
    });
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let result: T | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .find((entry) => entry.startsWith("data: "));
      if (!line) {
        continue;
      }

      const event = JSON.parse(line.slice(6)) as PipelineStepEvent;
      onEvent(event);

      if (event.type === "complete") {
        result = event.result as T;
      }
      if (event.type === "error") {
        throw new Error(event.message ?? "Erro no pipeline.");
      }
    }
  }

  if (result === null) {
    throw new Error("Pipeline encerrou sem resultado final.");
  }

  return result;
}

export async function streamIngest(
  onEvent: (event: PipelineStepEvent) => void,
  signal?: AbortSignal,
): Promise<IngestResult> {
  return consumeSseStream<IngestResult>("/api/ingest/stream", onEvent, signal);
}

export async function streamReEnrichBackfill(
  limit: number,
  onEvent: (event: PipelineStepEvent) => void,
  signal?: AbortSignal,
): Promise<EnrichBackfillResult> {
  return consumeSseStream<EnrichBackfillResult>(
    `/api/backfill/re-enrich/stream?limit=${limit}`,
    onEvent,
    signal,
  );
}

export async function streamEnrichBackfill(
  limit: number,
  onEvent: (event: PipelineStepEvent) => void,
  signal?: AbortSignal,
): Promise<EnrichBackfillResult> {
  return consumeSseStream<EnrichBackfillResult>(
    `/api/enrich-backfill/stream?limit=${limit}`,
    onEvent,
    signal,
  );
}

export async function streamObsidianExport(
  ids: number[],
  onEvent: (event: PipelineStepEvent) => void,
  signal?: AbortSignal,
): Promise<ObsidianExportResult> {
  return consumeSseStream<ObsidianExportResult>(
    "/api/obsidian/export/stream",
    onEvent,
    signal,
    { ids },
  );
}
