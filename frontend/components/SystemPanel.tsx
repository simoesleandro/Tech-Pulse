"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  ActivityLog,
  markAllDone,
  type ActivityStep,
} from "@/components/ActivityLog";
import {
  createObsidianMocs,
  fetchBackfillStatus,
  migrateObsidianVault,
  organizeObsidianVault,
  syncObsidianBackfill,
} from "@/lib/api";
import {
  applyPipelineStepEvent,
  RE_ENRICH_PIPELINE_STEPS,
} from "@/lib/pipeline-steps";
import { streamReEnrichBackfill } from "@/lib/pipeline-stream";
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

  async function runQuickAction(
    label: string,
    action: () => Promise<{ message: string }>,
  ) {
    if (busyAction) {
      return;
    }
    setActionError(null);
    setActionResult(null);
    setSteps([]);
    setStatusLine(null);
    setBusyAction(label);
    try {
      const result = await action();
      setActionResult(result.message);
      await refreshStatus();
      router.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Erro na operação.");
    } finally {
      setBusyAction(null);
    }
  }

  async function runReEnrichLoop() {
    if (busyAction) {
      return;
    }
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
        batches += 1;
        const result: EnrichBackfillResult = await streamReEnrichBackfill(
          5,
          handlePipelineEvent,
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
      setActionResult(
        `Re-enrich concluído — ${totalProcessed} artigo(s) atualizados em ${batches} lote(s).`,
      );
      await refreshStatus();
      router.refresh();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Erro no re-enrich.");
    } finally {
      setBusyAction(null);
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
                void runQuickAction("sync", async () => {
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
            <button
              type="button"
              disabled={isBusy}
              onClick={() =>
                void runQuickAction("mocs", async () => {
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
                void runQuickAction("organize", async () => {
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
                void runQuickAction("migrate", async () => {
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
              disabled={isBusy || !status?.legacy_enrichment_pending}
              onClick={() => void runReEnrichLoop()}
              className="btn-interactive rounded-md border border-violet/40 bg-violet/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-violet disabled:opacity-50"
            >
              {busyAction === "re-enrich"
                ? "Re-enriquecendo…"
                : "Re-enrich legado"}
            </button>
            <button
              type="button"
              disabled={isBusy}
              onClick={() => void refreshStatus()}
              className="btn-interactive rounded-md border border-border px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-muted hover:text-foreground disabled:opacity-50"
            >
              Atualizar status
            </button>
          </div>

          <ActivityLog
            title={logTitle}
            steps={steps}
            statusLine={statusLine}
            visible={isBusy && steps.length > 0}
          />

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
