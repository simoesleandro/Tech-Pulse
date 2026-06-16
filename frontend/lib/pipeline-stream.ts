import { apiFetch } from "@/lib/client-api";
import type {
  EnrichBackfillResult,
  IngestResult,
  PipelineStepEvent,
} from "@/lib/types";

async function consumeSseStream<T>(
  path: string,
  onEvent: (event: PipelineStepEvent) => void,
): Promise<T> {
  const response = await apiFetch(path, {
    method: "POST",
    timeoutMs: 600_000,
  });

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Resposta sem stream do backend.");
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
): Promise<IngestResult> {
  return consumeSseStream<IngestResult>("/api/ingest/stream", onEvent);
}

export async function streamEnrichBackfill(
  limit: number,
  onEvent: (event: PipelineStepEvent) => void,
): Promise<EnrichBackfillResult> {
  return consumeSseStream<EnrichBackfillResult>(
    `/api/enrich-backfill/stream?limit=${limit}`,
    onEvent,
  );
}
