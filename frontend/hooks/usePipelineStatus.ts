"use client";

import { useEffect, useState } from "react";

import { fetchPipelineStatus } from "@/lib/api";
import type { PipelineStatus } from "@/lib/types";

const IDLE: PipelineStatus = { busy: false, active_job: null };

export function usePipelineStatus(enabled: boolean, intervalMs = 3000) {
  const [status, setStatus] = useState<PipelineStatus>(IDLE);

  useEffect(() => {
    if (!enabled) {
      setStatus(IDLE);
      return;
    }

    let cancelled = false;

    async function poll() {
      try {
        const data = await fetchPipelineStatus();
        if (!cancelled) {
          setStatus(data);
        }
      } catch {
        if (!cancelled) {
          setStatus(IDLE);
        }
      }
    }

    void poll();
    const timer = setInterval(() => void poll(), intervalMs);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [enabled, intervalMs]);

  return status;
}

export const PIPELINE_JOB_LABELS: Record<string, string> = {
  ingest: "Ingestão manual",
  "ingest-background": "Ingestão em background",
  "ingest-startup": "Ingestão na inicialização",
  "obsidian-export": "Exportação Obsidian",
  "re-enrich": "Re-enriquecimento legado",
  "enrich-backfill": "Enriquecimento pendente",
};

export function pipelineJobLabel(job: string | null | undefined): string {
  if (!job) {
    return "Pipeline";
  }
  return PIPELINE_JOB_LABELS[job] ?? job;
}
