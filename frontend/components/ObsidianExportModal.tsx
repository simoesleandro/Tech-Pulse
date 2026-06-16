"use client";

import { useEffect, useState } from "react";

import {
  ActivityLog,
  markAllDone,
  type ActivityStep,
} from "@/components/ActivityLog";
import { streamObsidianExport } from "@/lib/obsidian-stream";
import {
  applyObsidianStepEvent,
  formatEta,
  OBSIDIAN_PIPELINE_STEPS,
  totalEtaSeconds,
} from "@/lib/pipeline-steps";
import type { PipelineStepEvent } from "@/lib/types";

interface ObsidianExportModalProps {
  ids: number[];
  title?: string;
  open: boolean;
  onClose: () => void;
  onComplete?: (exported: number) => void;
}

export function ObsidianExportModal({
  ids,
  title,
  open,
  onClose,
  onComplete,
}: ObsidianExportModalProps) {
  const [steps, setSteps] = useState<ActivityStep[]>([]);
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!open || ids.length === 0) {
      return;
    }

    let cancelled = false;

    async function runExport() {
      setError(null);
      setDone(false);
      setIsBusy(true);
      setStatusLine(
        `Agente Obsidian — ETA ${formatEta(totalEtaSeconds(OBSIDIAN_PIPELINE_STEPS))} por nota.`,
      );
      setSteps(
        OBSIDIAN_PIPELINE_STEPS.map((def, index) => ({
          ...def,
          status: index === 0 ? "active" : "pending",
        })),
      );

      function handleEvent(event: PipelineStepEvent) {
        if (cancelled || event.type !== "step") {
          return;
        }

        setSteps((prev) => applyObsidianStepEvent(OBSIDIAN_PIPELINE_STEPS, event));

        if (event.article_index && event.article_total) {
          const prefix = `Nota ${event.article_index}/${event.article_total}`;
          const stepLabel =
            OBSIDIAN_PIPELINE_STEPS.find((step) => step.id === event.step_id)?.label ??
            event.step_id;

          if (event.status === "active") {
            setStatusLine(`${prefix} — ${stepLabel}`);
          } else if (event.detail) {
            setStatusLine(`${prefix} — ${event.detail}`);
          }
        }
      }

      try {
        const result = await streamObsidianExport(ids, handleEvent);
        if (cancelled) {
          return;
        }
        setSteps((prev) =>
          markAllDone(
            prev.length > 0
              ? prev
              : OBSIDIAN_PIPELINE_STEPS.map((def) => ({ ...def, status: "pending" as const })),
            `${result.exported} nota(s) gravada(s) no vault.`,
          ),
        );
        setStatusLine(`${result.exported} nota(s) exportada(s) com sucesso.`);
        setDone(true);
        onComplete?.(result.exported);
      } catch (err) {
        if (cancelled) {
          return;
        }
        setSteps([
          {
            id: "error",
            label: "Falha na exportação Obsidian.",
            status: "error",
            detail: err instanceof Error ? err.message : "Erro desconhecido.",
          },
        ]);
        setStatusLine(null);
        setError(err instanceof Error ? err.message : "Erro ao exportar.");
      } finally {
        if (!cancelled) {
          setIsBusy(false);
        }
      }
    }

    void runExport();

    return () => {
      cancelled = true;
    };
  }, [open, ids.join(",")]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="obsidian-export-title"
    >
      <div className="w-full max-w-lg rounded-lg border border-violet-400/30 bg-surface-elevated p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p
              id="obsidian-export-title"
              className="font-mono text-xs uppercase tracking-wide text-violet-300"
            >
              Exportação Obsidian
            </p>
            <p className="mt-1 text-sm text-muted">
              {title ?? `${ids.length} nota(s) sendo processada(s) pelo agente.`}
            </p>
          </div>
          {!isBusy ? (
            <button
              type="button"
              onClick={onClose}
              className="btn-interactive rounded-md border border-border px-2 py-1 font-mono text-[10px] uppercase text-muted"
            >
              Fechar
            </button>
          ) : null}
        </div>

        <ActivityLog
          title="Pipeline do agente Obsidian"
          steps={steps}
          visible
          statusLine={statusLine}
        />

        {error ? (
          <p className="mt-3 text-xs text-crimson" role="alert">
            {error}
          </p>
        ) : null}

        {done && !isBusy ? (
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="btn-interactive rounded-md border border-violet-400/40 bg-violet-500/10 px-4 py-2 font-mono text-[10px] uppercase tracking-wide text-violet-300"
            >
              Concluído
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
