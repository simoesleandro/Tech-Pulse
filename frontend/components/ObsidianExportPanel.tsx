"use client";

import { useEffect, useState } from "react";

import {
  ActivityLog,
  markAllDone,
  type ActivityStep,
} from "@/components/ActivityLog";
import { streamObsidianExport } from "@/lib/pipeline-stream";
import {
  applyObsidianStepEvent,
  formatEta,
  OBSIDIAN_PIPELINE_STEPS,
  totalEtaSeconds,
} from "@/lib/pipeline-steps";
import type { ObsidianExportResult, PipelineStepEvent } from "@/lib/types";

interface ObsidianExportPanelProps {
  ids: number[];
  title?: string;
  open: boolean;
  onClose: () => void;
  onComplete?: (result: ObsidianExportResult) => void;
}

function PanelSpinner() {
  return (
    <span
      className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-violet-300/30 border-t-violet-300"
      aria-hidden="true"
    />
  );
}

export function ObsidianExportPanel({
  ids,
  title,
  open,
  onClose,
  onComplete,
}: ObsidianExportPanelProps) {
  const [steps, setSteps] = useState<ActivityStep[]>([]);
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [minimized, setMinimized] = useState(false);

  useEffect(() => {
    if (!open || ids.length === 0) {
      return;
    }

    const abortController = new AbortController();
    let cancelled = false;
    setMinimized(false);

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

        setSteps(applyObsidianStepEvent(OBSIDIAN_PIPELINE_STEPS, event));

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
        const result = await streamObsidianExport(
          ids,
          handleEvent,
          abortController.signal,
        );
        if (cancelled || abortController.signal.aborted) {
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
        onComplete?.(result);
      } catch (err) {
        if (cancelled || abortController.signal.aborted) {
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
      abortController.abort();
    };
  }, [open, ids.join(",")]);

  if (!open) {
    return null;
  }

  if (minimized) {
    return (
      <div
        className="fixed bottom-20 left-4 right-4 sm:left-auto sm:right-4 z-40 flex max-w-none sm:max-w-sm items-center gap-2 rounded-lg border border-violet-400/40 bg-surface-elevated/95 px-3 py-2 shadow-lg backdrop-blur-md"
        role="status"
        aria-live="polite"
      >
        {isBusy ? <PanelSpinner /> : null}
        {!isBusy && done ? (
          <span className="text-emerald" aria-hidden="true">
            ✓
          </span>
        ) : null}
        <p className="min-w-0 flex-1 truncate font-mono text-[10px] text-violet-200">
          {error ?? statusLine ?? "Exportação Obsidian"}
        </p>
        <button
          type="button"
          onClick={() => setMinimized(false)}
          className="btn-interactive shrink-0 rounded border border-border px-2 py-0.5 font-mono text-[9px] uppercase text-muted"
        >
          Expandir
        </button>
        {!isBusy ? (
          <button
            type="button"
            onClick={onClose}
            className="btn-interactive shrink-0 rounded border border-border px-2 py-0.5 font-mono text-[9px] uppercase text-muted"
          >
            Fechar
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <aside
      className="pointer-events-none fixed left-4 right-4 sm:left-auto sm:right-4 top-20 z-40 flex max-h-[calc(100vh-7rem)] w-auto sm:w-[22rem] flex-col"
      role="complementary"
      aria-labelledby="obsidian-export-title"
    >
      <div className="pointer-events-auto flex max-h-full flex-col overflow-hidden rounded-lg border border-violet-400/30 bg-surface-elevated/95 shadow-2xl backdrop-blur-md">
        <div className="flex items-start justify-between gap-2 border-b border-border/60 px-4 py-3">
          <div className="min-w-0">
            <p
              id="obsidian-export-title"
              className="font-mono text-xs uppercase tracking-wide text-violet-300"
            >
              Exportação Obsidian
            </p>
            <p className="mt-0.5 truncate text-xs text-muted">
              {title ?? `${ids.length} nota(s) em processamento`}
            </p>
          </div>
          <div className="flex shrink-0 gap-1">
            <button
              type="button"
              onClick={() => setMinimized(true)}
              className="btn-interactive rounded-md border border-border px-2 py-1 font-mono text-[9px] uppercase text-muted"
              title="Minimizar e continuar navegando"
            >
              Minimizar
            </button>
            {!isBusy ? (
              <button
                type="button"
                onClick={onClose}
                className="btn-interactive rounded-md border border-border px-2 py-1 font-mono text-[9px] uppercase text-muted"
              >
                Fechar
              </button>
            ) : null}
          </div>
        </div>

        <div className="overflow-y-auto px-4 py-3">
          <ActivityLog
            title="Pipeline do agente"
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
    </aside>
  );
}
