"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  ActivityLog,
  markAllDone,
  type StepStatus,
} from "@/components/ActivityLog";
import { PipelineProgressDashboard } from "@/components/PipelineProgressDashboard";
import { pipelineJobLabel } from "@/hooks/usePipelineStatus";
import { useParallelPipelineProgress } from "@/hooks/useParallelPipelineProgress";
import { usePipelineStream } from "@/hooks/usePipelineStream";
import {
  createObsidianMocs,
  fetchBackfillStatus,
  migrateObsidianVault,
  organizeObsidianVault,
  syncObsidianBackfill,
  generateObsidianDigest,
  fetchNews,
} from "@/lib/api";
import {
  applyPipelineStepEvent,
  RE_ENRICH_PIPELINE_STEPS,
  OBSIDIAN_PIPELINE_STEPS,
} from "@/lib/pipeline-steps";
import { streamReEnrichBackfill, streamObsidianExport } from "@/lib/pipeline-stream";
import type {
  BackfillStatus,
  EnrichBackfillResult,
  PipelineStatus,
  PipelineStepEvent,
} from "@/lib/types";

const OBSIDIAN_STEP_ORDER = [
  "fetch",
  "summarize",
  "analyze",
  "orchestrate",
  "render",
  "write",
];

export function SystemPanel({
  pipelineStatus = { busy: false, active_job: null },
}: {
  pipelineStatus?: PipelineStatus;
}) {
  const router = useRouter();
  const pipeline = usePipelineStream();
  const parallel = useParallelPipelineProgress(OBSIDIAN_STEP_ORDER);

  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<BackfillStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const refreshStatus = useCallback(async () => {
    try {
      const data = await fetchBackfillStatus();
      setStatus(data);
      setStatusError(null);
    } catch {
      setStatusError("Não foi possível carregar o status do sistema.");
    }
  }, []);

  useEffect(() => {
    if (open) {
      void refreshStatus();
    }
  }, [open, refreshStatus]);

  useEffect(() => {
    if (parallel.totalItems === 0 || busyAction !== "export-pending") {
      return;
    }
    pipeline.setSteps((prev) => parallel.syncSteps(prev));
  }, [
    parallel.itemsMap,
    parallel.totalItems,
    parallel.syncSteps,
    pipeline.setSteps,
    busyAction,
  ]);

  function handleReEnrichPipelineEvent(event: PipelineStepEvent) {
    if (event.type !== "step") {
      return;
    }
    pipeline.setSteps((prev) =>
      applyPipelineStepEvent(RE_ENRICH_PIPELINE_STEPS, event),
    );
    if (event.article_index && event.article_total) {
      const prefix = `Artigo ${event.article_index}/${event.article_total}`;
      pipeline.setStatusLine(
        event.detail ? `${prefix} — ${event.detail}` : `${prefix} — processando…`,
      );
    } else if (event.detail) {
      pipeline.setStatusLine(event.detail);
    }
  }

  function handleObsidianPipelineEvent(event: PipelineStepEvent) {
    if (event.type !== "step") {
      return;
    }

    if (parallel.recordParallelEvent(event)) {
      const prefix = `Nota ${event.article_index}/${event.article_total}`;
      pipeline.setStatusLine(
        event.detail ? `${prefix} — ${event.detail}` : `${prefix} — processando…`,
      );
      return;
    }

    pipeline.setSteps((prev) =>
      prev.map((step) => {
        if (step.id === event.step_id) {
          return {
            ...step,
            status: event.status as StepStatus,
            detail: event.detail,
          };
        }
        return step;
      }),
    );
    if (event.detail) {
      pipeline.setStatusLine(event.detail);
    }
  }

  async function runQuickAction(
    actionId: string,
    title: string,
    action: () => Promise<{ message: string }>,
  ) {
    if (busyAction) {
      return;
    }
    setActionError(null);
    setActionResult(null);
    pipeline.setSteps([]);
    pipeline.setLogTitle(title);
    pipeline.setStatusLine("Processando operação no servidor...");
    setBusyAction(actionId);
    try {
      const result = await action();
      setActionResult(result.message);
      await refreshStatus();
      router.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Erro na operação.");
    } finally {
      setBusyAction(null);
      pipeline.setLogTitle("");
      pipeline.setStatusLine(null);
    }
  }

  async function runObsidianExportStream() {
    if (busyAction) {
      return;
    }
    const controller = pipeline.begin(
      "Exportação para o Obsidian",
      OBSIDIAN_PIPELINE_STEPS,
    );
    parallel.reset();
    setActionError(null);
    setActionResult(null);
    setBusyAction("export-pending");
    pipeline.setStatusLine("Buscando notas relevantes pendentes...");

    try {
      const newsList = await fetchNews({
        ai_relevance: "RELEVANTE",
        obsidian_exported: false,
        limit: 100,
      });

      if (controller.signal.aborted) {
        return;
      }

      const ids = newsList.items.map((item) => item.id);
      if (ids.length === 0) {
        setActionResult("Nenhuma nota pendente para exportar.");
        pipeline.setSteps([]);
        pipeline.setStatusLine(null);
        return;
      }

      pipeline.setStatusLine(`Exportando ${ids.length} nota(s) em lote...`);

      const result = await streamObsidianExport(
        ids,
        handleObsidianPipelineEvent,
        controller.signal,
      );

      if (controller.signal.aborted) {
        return;
      }

      setActionResult(
        `Exportação concluída — ${result.exported} nota(s) enviadas para o Obsidian.`,
      );
      pipeline.setSteps((prev) => markAllDone(prev));
      await refreshStatus();
      router.refresh();
    } catch (err) {
      if (controller.signal.aborted) {
        return;
      }
      setActionError(err instanceof Error ? err.message : "Erro na exportação.");
    } finally {
      setBusyAction(null);
      pipeline.finish();
    }
  }

  async function runReEnrichLoop() {
    if (busyAction) {
      return;
    }
    const controller = pipeline.begin(
      "Re-enriquecimento legado",
      RE_ENRICH_PIPELINE_STEPS,
    );
    setActionError(null);
    setActionResult(null);
    setBusyAction("re-enrich");

    let remaining = 1;
    let totalProcessed = 0;
    let batches = 0;

    try {
      while (remaining > 0 && batches < 20) {
        if (controller.signal.aborted) {
          break;
        }
        batches += 1;
        const result: EnrichBackfillResult = await streamReEnrichBackfill(
          5,
          handleReEnrichPipelineEvent,
          controller.signal,
        );
        totalProcessed += result.processed;
        remaining = result.remaining;
        pipeline.setStatusLine(
          `Lote ${batches}: ${result.processed} processados · ${remaining} restantes`,
        );
        pipeline.setSteps((prev) => markAllDone(prev));
        if (remaining <= 0) {
          break;
        }
      }
      if (!controller.signal.aborted) {
        setActionResult(
          `Re-enrich concluído — ${totalProcessed} artigo(s) atualizados em ${batches} lote(s).`,
        );
        await refreshStatus();
        router.refresh();
      }
    } catch (err) {
      if (controller.signal.aborted) {
        return;
      }
      setActionError(err instanceof Error ? err.message : "Erro no re-enrich.");
    } finally {
      setBusyAction(null);
      pipeline.finish();
    }
  }

  const isBusy = busyAction !== null;
  const pipelineBlocked = pipelineStatus.busy && !isBusy;

  return (
    <div className="rounded-lg border border-border bg-surface-elevated">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        aria-expanded={open}
      >
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-violet">
            Sistema
          </p>
          <p className="mt-0.5 text-sm text-muted">
            Manutenção do feed, Obsidian e backfill
          </p>
        </div>
        <div className="flex items-center gap-2">
          {status ? (
            <span className="rounded-md border border-border px-2 py-0.5 font-mono text-[10px] text-muted">
              Obsidian: {status.obsidian_unmarked} pendente
            </span>
          ) : null}
          <span className="font-mono text-xs text-muted">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open ? (
        <div className="border-t border-border px-4 pb-4 pt-3">
          {statusError ? (
            <p className="mb-3 text-xs text-crimson" role="alert">
              {statusError}
            </p>
          ) : null}

          {status ? (
            <div className="mb-4 grid gap-2 sm:grid-cols-2">
              <div className="rounded-md border border-border/80 bg-surface px-3 py-2">
                <p className="font-mono text-[10px] uppercase tracking-wide text-muted">
                  Obsidian pendente
                </p>
                <p className="mt-1 font-mono text-lg text-foreground">
                  {status.obsidian_unmarked}
                </p>
              </div>
              <div className="rounded-md border border-border/80 bg-surface px-3 py-2">
                <p className="font-mono text-[10px] uppercase tracking-wide text-muted">
                  Re-enrich legado
                </p>
                <p className="mt-1 font-mono text-lg text-foreground">
                  {status.legacy_enrichment_pending}
                </p>
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={isBusy}
              onClick={() =>
                void runQuickAction("sync", "Sincronizar vault", async () => {
                  const r = await syncObsidianBackfill();
                  return {
                    message: `Sincronizado — ${r.updated} nota(s) marcadas no banco.`,
                  };
                })
              }
              className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted hover:border-violet/50 hover:text-violet disabled:opacity-50"
            >
              Sincronizar vault
            </button>
            {busyAction === "export-pending" && pipeline.abortController ? (
              <button
                type="button"
                onClick={() => {
                  pipeline.cancel();
                  setActionError("Operação cancelada pelo usuário.");
                  setBusyAction(null);
                }}
                className="btn-interactive rounded-md border border-crimson bg-crimson/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-crimson hover:bg-crimson/25"
              >
                Cancelar
              </button>
            ) : (
              <button
                type="button"
                disabled={isBusy || !status?.obsidian_unmarked || pipelineBlocked}
                title={
                  pipelineBlocked
                    ? `${pipelineJobLabel(pipelineStatus.active_job)} em andamento`
                    : undefined
                }
                onClick={() => void runObsidianExportStream()}
                className="btn-interactive rounded-md border border-violet/40 bg-violet/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-violet disabled:opacity-50"
              >
                Exportar pendentes
              </button>
            )}
            <button
              type="button"
              disabled={isBusy}
              onClick={() =>
                void runQuickAction("mocs", "Criar MOCs", async () => {
                  const r = await createObsidianMocs();
                  return {
                    message: `MOCs — ${r.created} criados, ${r.updated} atualizados.`,
                  };
                })
              }
              className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted hover:border-violet/50 hover:text-violet disabled:opacity-50"
            >
              Criar MOCs
            </button>
            <button
              type="button"
              disabled={isBusy}
              onClick={() =>
                void runQuickAction("organize", "Organizar soltas", async () => {
                  const r = await organizeObsidianVault();
                  return {
                    message: `Organizado — ${r.organized} nota(s) movidas para pastas.`,
                  };
                })
              }
              className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted hover:border-violet/50 hover:text-violet disabled:opacity-50"
            >
              Organizar soltas
            </button>
            <button
              type="button"
              disabled={isBusy}
              onClick={() =>
                void runQuickAction("migrate", "Migrar layout", async () => {
                  const r = await migrateObsidianVault();
                  return {
                    message: `Migrado — ${r.migrated} arquivo(s), ${r.retitled} renomeados.`,
                  };
                })
              }
              className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted hover:border-violet/50 hover:text-violet disabled:opacity-50"
            >
              Migrar layout
            </button>
            <button
              type="button"
              disabled={isBusy}
              onClick={() =>
                void runQuickAction("digest", "Gerar Digest Semanal", async () => {
                  const r = await generateObsidianDigest();
                  return {
                    message: `Digest criado — gravado em: ${r.path}.`,
                  };
                })
              }
              className="btn-interactive rounded-md border border-violet/40 bg-violet/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-violet disabled:opacity-50"
            >
              Gerar Digest Semanal
            </button>
            {busyAction === "re-enrich" && pipeline.abortController ? (
              <button
                type="button"
                onClick={() => {
                  pipeline.cancel();
                  setActionError("Operação cancelada pelo usuário.");
                  setBusyAction(null);
                }}
                className="btn-interactive rounded-md border border-crimson bg-crimson/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-crimson hover:bg-crimson/25"
              >
                Cancelar
              </button>
            ) : (
              <button
                type="button"
                disabled={isBusy || !status?.legacy_enrichment_pending || pipelineBlocked}
                title={
                  pipelineBlocked
                    ? `${pipelineJobLabel(pipelineStatus.active_job)} em andamento`
                    : undefined
                }
                onClick={() => void runReEnrichLoop()}
                className="btn-interactive rounded-md border border-violet/40 bg-violet/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-violet disabled:opacity-50"
              >
                Re-enrich legado
              </button>
            )}
            <button
              type="button"
              disabled={isBusy}
              onClick={() => void refreshStatus()}
              className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted hover:text-foreground disabled:opacity-50"
            >
              Atualizar status
            </button>
          </div>

          {busyAction === "export-pending" && parallel.totalItems > 0 ? (
            <PipelineProgressDashboard
              logTitle={pipeline.logTitle}
              statusLine={pipeline.statusLine}
              totalItems={parallel.totalItems}
              itemsMap={parallel.itemsMap}
              completedStepId="write"
              entityLabel="nota"
            />
          ) : (
            <ActivityLog
              title={pipeline.logTitle}
              steps={pipeline.steps}
              statusLine={pipeline.statusLine}
              visible={isBusy || pipeline.steps.length > 0}
            />
          )}

          {actionResult ? (
            <p className="mt-3 font-mono text-xs text-emerald">{actionResult}</p>
          ) : null}
          {actionError ? (
            <p className="mt-3 text-xs text-crimson" role="alert">
              {actionError}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
