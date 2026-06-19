"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  ActivityLog,
  markAllDone,
  type ActivityStep,
  type StepStatus,
} from "@/components/ActivityLog";
import {
  createObsidianMocs,
  fetchBackfillStatus,
  migrateObsidianVault,
  organizeObsidianVault,
  syncObsidianBackfill,
  generateObsidianDigest,
  fetchNews,
  exportNewsToObsidian,
} from "@/lib/api";
import {
  applyPipelineStepEvent,
  applyObsidianStepEvent,
  RE_ENRICH_PIPELINE_STEPS,
  OBSIDIAN_PIPELINE_STEPS,
} from "@/lib/pipeline-steps";
import { streamReEnrichBackfill, streamObsidianExport } from "@/lib/pipeline-stream";
import type {
  BackfillStatus,
  EnrichBackfillResult,
  PipelineStepEvent,
} from "@/lib/types";

export function SystemPanel() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<BackfillStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [steps, setSteps] = useState<ActivityStep[]>([]);
  const [logTitle, setLogTitle] = useState("");
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [notesMap, setNotesMap] = useState<Record<number, { title: string; step_id: string; status: string; detail?: string; timestamp: number }>>({});
  const [totalNotes, setTotalNotes] = useState(0);

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
    if (totalNotes === 0) return;

    setSteps((prev) => {
      const stepOrder = ["fetch", "summarize", "analyze", "orchestrate", "render", "write"];
      return prev.map((step) => {
        const stepIdx = stepOrder.indexOf(step.id);
        if (stepIdx === -1) {
          return step;
        }

        let completedCount = 0;
        const activeNotes: number[] = [];

        for (const [idxStr, info] of Object.entries(notesMap)) {
          const idx = parseInt(idxStr, 10);
          const currentStepIdx = stepOrder.indexOf(info.step_id);

          if (
            currentStepIdx > stepIdx ||
            (currentStepIdx === stepIdx && info.status === "done")
          ) {
            completedCount++;
          } else if (currentStepIdx === stepIdx && info.status === "active") {
            activeNotes.push(idx);
          }
        }

        let status: StepStatus = "pending";
        let detail = "";

        if (completedCount === totalNotes) {
          status = "done";
          detail = `Todas as ${totalNotes} notas processadas.`;
        } else if (
          activeNotes.length > 0 ||
          (completedCount > 0 && completedCount < totalNotes)
        ) {
          status = "active";
          detail = `Processando: ${
            activeNotes.length > 0
              ? `Nota(s) ${activeNotes.join(", ")}`
              : "aguardando"
          } · ${completedCount}/${totalNotes} concluídas`;
        } else {
          status = "pending";
          detail = "Aguardando notas...";
        }

        return {
          ...step,
          status,
          detail,
        };
      });
    });
  }, [notesMap, totalNotes]);

  function handlePipelineEvent(event: PipelineStepEvent) {
    if (event.type !== "step") {
      return;
    }
    setSteps((prev) =>
      applyPipelineStepEvent(RE_ENRICH_PIPELINE_STEPS, event),
    );
    if (event.article_index && event.article_total) {
      const prefix = `Artigo ${event.article_index}/${event.article_total}`;
      setStatusLine(
        event.detail ? `${prefix} — ${event.detail}` : `${prefix} — processando…`,
      );
    } else if (event.detail) {
      setStatusLine(event.detail);
    }
  }

  function handleCancel() {
    if (abortController) {
      abortController.abort();
      setSteps((prev) => {
        const withErrors = prev.map((step) => {
          if (step.status === "active") {
            return {
              ...step,
              status: "error" as const,
              detail: "Cancelado pelo usuário.",
            };
          }
          return step;
        });
        return [
          ...withErrors,
          {
            id: "cancelled",
            label: "Operação cancelada.",
            status: "error" as const,
            detail: "Operação interrompida pelo usuário.",
          },
        ];
      });
      setActionError("Operação cancelada pelo usuário.");
      setBusyAction(null);
      setAbortController(null);
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
    setSteps([]);
    setLogTitle(title);
    setStatusLine("Processando operação no servidor...");
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
      setLogTitle("");
      setStatusLine(null);
    }
  }

  async function runObsidianExportStream() {
    if (busyAction) {
      return;
    }
    const controller = new AbortController();
    setAbortController(controller);
    setActionError(null);
    setActionResult(null);
    setBusyAction("export-pending");
    setLogTitle("Exportação para o Obsidian");
    setSteps(
      OBSIDIAN_PIPELINE_STEPS.map((def, index) => ({
        ...def,
        status: index === 0 ? "active" : "pending",
      })),
    );
    setStatusLine("Buscando notas relevantes pendentes...");
    setNotesMap({});
    setTotalNotes(0);

    try {
      const newsList = await fetchNews({
        ai_relevance: "RELEVANTE",
        obsidian_exported: false,
        limit: 100,
      });
      
      if (controller.signal.aborted) return;
      
      const ids = newsList.items.map((item) => item.id);
      if (ids.length === 0) {
        setActionResult("Nenhuma nota pendente para exportar.");
        setSteps([]);
        setStatusLine(null);
        return;
      }

      setStatusLine(`Exportando ${ids.length} nota(s) em lote...`);

      const result = await streamObsidianExport(ids, (event) => {
        if (event.type === "step") {
          const idx = event.article_index;
          if (idx) {
            if (event.article_total) {
              setTotalNotes(event.article_total);
            }
            setNotesMap((prev) => ({
              ...prev,
              [idx]: {
                title: event.title || prev[idx]?.title || "",
                step_id: event.step_id,
                status: event.status,
                detail: event.detail,
                timestamp: Date.now(),
              },
            }));
          } else {
            setSteps((prev) =>
              prev.map((step) => {
                if (step.id === event.step_id) {
                  return {
                    ...step,
                    status: event.status as StepStatus,
                    detail: event.detail,
                  };
                }
                return step;
              })
            );
          }

          if (event.article_index && event.article_total) {
            const prefix = `Nota ${event.article_index}/${event.article_total}`;
            setStatusLine(
              event.detail ? `${prefix} — ${event.detail}` : `${prefix} — processando…`,
            );
          } else if (event.detail) {
            setStatusLine(event.detail);
          }
        }
      }, controller.signal);

      if (controller.signal.aborted) return;

      setActionResult(
        `Exportação concluída — ${result.exported} nota(s) enviadas para o Obsidian.`,
      );
      setSteps((prev) => markAllDone(prev));
      await refreshStatus();
      router.refresh();
    } catch (err) {
      if (controller.signal.aborted) return;
      setActionError(err instanceof Error ? err.message : "Erro na exportação.");
    } finally {
      setBusyAction(null);
      setAbortController(null);
    }
  }

  async function runReEnrichLoop() {
    if (busyAction) {
      return;
    }
    const controller = new AbortController();
    setAbortController(controller);
    setActionError(null);
    setActionResult(null);
    setBusyAction("re-enrich");
    setLogTitle("Re-enriquecimento legado");
    setSteps(
      RE_ENRICH_PIPELINE_STEPS.map((def, index) => ({
        ...def,
        status: index === 0 ? "active" : "pending",
      })),
    );

    let remaining = 1;
    let totalProcessed = 0;
    let batches = 0;

    try {
      while (remaining > 0 && batches < 20) {
        if (controller.signal.aborted) break;
        batches += 1;
        const result: EnrichBackfillResult = await streamReEnrichBackfill(
          5,
          handlePipelineEvent,
          controller.signal,
        );
        totalProcessed += result.processed;
        remaining = result.remaining;
        setStatusLine(
          `Lote ${batches}: ${result.processed} processados · ${remaining} restantes`,
        );
        setSteps((prev) => markAllDone(prev));
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
      if (controller.signal.aborted) return;
      setActionError(err instanceof Error ? err.message : "Erro no re-enrich.");
    } finally {
      setBusyAction(null);
      setAbortController(null);
    }
  }

  const isBusy = busyAction !== null;

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
            {busyAction === "export-pending" && abortController ? (
              <button
                type="button"
                onClick={handleCancel}
                className="btn-interactive rounded-md border border-crimson bg-crimson/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-crimson hover:bg-crimson/25"
              >
                Cancelar
              </button>
            ) : (
              <button
                type="button"
                disabled={isBusy || !status?.obsidian_unmarked}
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
            {busyAction === "re-enrich" && abortController ? (
              <button
                type="button"
                onClick={handleCancel}
                className="btn-interactive rounded-md border border-crimson bg-crimson/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-crimson hover:bg-crimson/25"
              >
                Cancelar
              </button>
            ) : (
              <button
                type="button"
                disabled={isBusy || !status?.legacy_enrichment_pending}
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
 
          {busyAction === "export-pending" ? (
            <div className="mt-4 rounded-lg border border-border bg-surface p-4">
              {/* Header & General Progress */}
              <div className="flex items-center justify-between border-b border-border/60 pb-3 mb-4">
                <div>
                  <h4 className="text-sm font-semibold text-foreground">{logTitle}</h4>
                  <p className="text-xs text-muted mt-0.5">{statusLine}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-violet font-semibold">
                    {totalNotes > 0
                      ? Math.round(
                          (Object.values(notesMap).filter(
                            (n) => n.step_id === "write" && n.status === "done",
                          ).length /
                            totalNotes) *
                            100,
                        )
                      : 0}
                    %
                  </span>
                </div>
              </div>

              {/* Progress Bar */}
              <div className="h-1.5 w-full bg-border rounded-full overflow-hidden mb-4">
                <div
                  className="h-full bg-gradient-to-r from-violet to-cyan transition-all duration-300 ease-out"
                  style={{
                    width: `${
                      totalNotes > 0
                        ? Math.min(
                            100,
                            (Object.values(notesMap).filter(
                              (n) => n.step_id === "write" && n.status === "done",
                            ).length /
                              totalNotes) *
                              100,
                          )
                        : 0
                    }%`,
                  }}
                />
              </div>

              {/* Stats grid */}
              <div className="grid grid-cols-3 gap-2 mb-4 text-center">
                <div className="rounded border border-border/55 bg-surface-elevated/40 p-2">
                  <p className="text-[10px] font-mono uppercase tracking-wider text-muted">Total</p>
                  <p className="text-sm font-mono font-semibold text-foreground mt-0.5">{totalNotes}</p>
                </div>
                <div className="rounded border border-border/55 bg-surface-elevated/40 p-2">
                  <p className="text-[10px] font-mono uppercase tracking-wider text-emerald">Exportadas</p>
                  <p className="text-sm font-mono font-semibold text-emerald mt-0.5">
                    {Object.values(notesMap).filter((n) => n.step_id === "write" && n.status === "done").length}
                  </p>
                </div>
                <div className="rounded border border-border/55 bg-surface-elevated/40 p-2">
                  <p className="text-[10px] font-mono uppercase tracking-wider text-cyan">Ativas</p>
                  <p className="text-sm font-mono font-semibold text-cyan mt-0.5">
                    {Object.values(notesMap).filter((n) => !(n.step_id === "write" && n.status === "done") && n.status === "active").length}
                  </p>
                </div>
              </div>

              {/* Active notes cards */}
              <div className="space-y-2 mb-4">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted mb-1">Processando no Backend</p>
                {Object.entries(notesMap)
                  .filter(([_, note]) => !(note.step_id === "write" && note.status === "done"))
                  .map(([idxStr, note]) => {
                    const idx = parseInt(idxStr, 10);
                    const stepLabels: Record<string, string> = {
                      fetch: "🔍 Buscando Artigo",
                      summarize: "📝 Extraindo Resumo",
                      analyze: "📊 Estruturando JSON",
                      orchestrate: "🗺️ Orquestrando Pasta",
                      render: "🎨 Renderizando Nota",
                      write: "💾 Gravando Arquivo",
                    };
                    return (
                      <div
                        key={idx}
                        className="flex items-center justify-between rounded-md border border-border/60 bg-surface-elevated/30 p-2.5 transition-all duration-200 hover:border-violet/35"
                      >
                        <div className="flex-1 min-w-0 pr-3">
                          <p className="text-xs font-medium text-foreground truncate">
                            {note.title || `Nota #${idx}`}
                          </p>
                          <p className="text-[10px] text-muted truncate mt-0.5">
                            {note.detail || "Iniciando processamento..."}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[9px] font-mono font-medium ${
                              note.status === "active"
                                ? "bg-violet/10 text-violet border border-violet/20"
                                : "bg-muted/15 text-muted"
                            }`}
                          >
                            {stepLabels[note.step_id] || note.step_id}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                {Object.values(notesMap).filter((n) => !(n.step_id === "write" && n.status === "done")).length === 0 && (
                  <p className="text-xs text-muted italic text-center py-2">Nenhuma nota ativa no momento.</p>
                )}
              </div>

              {/* Recently completed logs */}
              <div className="border-t border-border/40 pt-3">
                <p className="text-[10px] font-mono uppercase tracking-wider text-muted mb-2">Concluídas Recentemente</p>
                <div className="space-y-1.5 max-h-32 overflow-y-auto">
                  {Object.entries(notesMap)
                    .filter(([_, note]) => note.step_id === "write" && note.status === "done")
                    .sort((a, b) => b[1].timestamp - a[1].timestamp) // most recent first
                    .slice(0, 5) // last 5
                    .map(([idxStr, note]) => (
                      <div key={idxStr} className="flex items-center justify-between text-xs text-muted/90">
                        <span className="truncate pr-2">✅ {note.title || `Nota #${idxStr}`}</span>
                        <span className="text-[9px] font-mono text-emerald/80 flex-shrink-0">Salva no vault</span>
                      </div>
                    ))}
                  {Object.values(notesMap).filter((n) => n.step_id === "write" && n.status === "done").length === 0 && (
                    <p className="text-xs text-muted/60 italic text-center py-1">Nenhuma nota concluída ainda.</p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <ActivityLog
              title={logTitle}
              steps={steps}
              statusLine={statusLine}
              visible={isBusy || steps.length > 0}
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
