import { apiFetch } from "@/lib/client-api";
import type { ObsidianExportResult, PipelineStepEvent } from "@/lib/types";

async function consumeObsidianSseStream(
  ids: number[],
  onEvent: (event: PipelineStepEvent) => void,
): Promise<ObsidianExportResult> {
  const response = await apiFetch("/api/obsidian/export/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
    timeoutMs: 600_000,
  });

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("Resposta sem stream do backend.");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let result: ObsidianExportResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const line = chunk.split("\n").find((entry) => entry.startsWith("data: "));
      if (!line) {
        continue;
      }

      const event = JSON.parse(line.slice(6)) as PipelineStepEvent;
      onEvent(event);

      if (event.type === "complete") {
        result = event.result as ObsidianExportResult;
      }
      if (event.type === "error") {
        throw new Error(event.message ?? "Erro ao exportar para Obsidian.");
      }
    }
  }

  if (result === null) {
    throw new Error("Exportação encerrou sem resultado final.");
  }

  return result;
}

export async function streamObsidianExport(
  ids: number[],
  onEvent: (event: PipelineStepEvent) => void,
): Promise<ObsidianExportResult> {
  return consumeObsidianSseStream(ids, onEvent);
}
