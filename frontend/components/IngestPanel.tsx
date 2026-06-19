"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  ActivityLog,
  type StepStatus,
} from "@/components/ActivityLog";
import { PipelineProgressDashboard } from "@/components/PipelineProgressDashboard";
import { useParallelPipelineProgress } from "@/hooks/useParallelPipelineProgress";
import { usePipelineStream } from "@/hooks/usePipelineStream";
import { API_BASE, checkApiHealth } from "@/lib/client-api";
import { fetchPipelineSteps, seedDemoData } from "@/lib/api";
import {
  formatEta,
  INGEST_PIPELINE_STEPS,
  mapApiSteps,
  totalEtaSeconds,
  type PipelineStepDef,
} from "@/lib/pipeline-steps";
import { streamIngest } from "@/lib/pipeline-stream";
import type { IngestResult, PipelineStepEvent, SeedResult } from "@/lib/types";

const INGEST_AGENT_STEPS = new Set([
  "triador",
  "tradutor",
  "hype",
  "unified",
  "save",
]);

const INGEST_STEP_ORDER = [
  "fetch",
  "dedup",
  "triador",
  "tradutor",
  "hype",
  "unified",
  "save",
];

export function IngestPanel() {
  const router = useRouter();
  const pipeline = usePipelineStream();
  const parallel = useParallelPipelineProgress(INGEST_STEP_ORDER, INGEST_AGENT_STEPS);

  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null);
  const [seedResult, setSeedResult] = useState<SeedResult | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [ingestDefs, setIngestDefs] = useState<PipelineStepDef[]>(INGEST_PIPELINE_STEPS);
  const [seedBusy, setSeedBusy] = useState(false);

  const isBusy = pipeline.isRunning || seedBusy;

  useEffect(() => {
    void checkApiHealth().then(setApiOnline);
    void fetchPipelineSteps()
      .then((config) => {
        setIngestDefs(mapApiSteps(config.ingest));
      })
      .catch(() => {
        /* mantém fallback estático */
      });
  }, []);

  useEffect(() => {
    if (parallel.totalItems === 0) {
      return;
    }
    pipeline.setSteps((prev) => parallel.syncSteps(prev));
  }, [parallel.itemsMap, parallel.totalItems, parallel.syncSteps, pipeline.setSteps]);

  function handlePipelineEvent(event: PipelineStepEvent) {
    if (event.type !== "step") {
      return;
    }

    if (parallel.recordParallelEvent(event)) {
      const prefix = `Artigo ${event.article_index}/${event.article_total}`;
      if (event.step_id === "save") {
        pipeline.setStatusLine(
          event.status === "active"
            ? `${prefix} — salvando no banco de dados…`
            : event.detail ?? `${prefix} — salvo.`,
        );
        return;
      }

      const agentLabel =
        event.step_id === "triador"
          ? "Triador"
          : event.step_id === "tradutor"
            ? "Tradutor"
            : event.step_id === "hype"
              ? "Analista"
              : event.step_id === "unified"
                ? "Análise Unificada"
                : event.step_id;

      if (event.status === "active") {
        pipeline.setStatusLine(`${prefix} — ${agentLabel} em andamento…`);
      } else if (event.detail) {
        pipeline.setStatusLine(`${prefix} — ${event.detail}`);
      }
      return;
    }

    pipeline.setSteps((prev) => {
      const stepIndex = prev.findIndex((step) => step.id === event.step_id);
      return prev.map((step, index) => {
        if (step.id === event.step_id) {
          return {
            ...step,
            status: event.status as StepStatus,
            detail: event.detail,
          };
        }
        if (
          stepIndex !== -1 &&
          index < stepIndex &&
          step.status !== "done" &&
          event.status === "active"
        ) {
          return { ...step, status: "done" as const };
        }
        if (
          stepIndex !== -1 &&
          index < stepIndex &&
          event.status === "done"
        ) {
          return { ...step, status: "done" as const };
        }
        return step;
      });
    });

    if (event.detail) {
      pipeline.setStatusLine(event.detail);
    } else if (event.step_id === "fetch" && event.status === "active") {
      pipeline.setStatusLine("Buscando artigos nas fontes configuradas…");
    }
  }

  async function handleIngest() {
    if (isBusy) {
      return;
    }

    const controller = pipeline.begin("Atualizando feed com IA", ingestDefs);
    parallel.reset();
    setIngestResult(null);
    pipeline.setStatusLine(
      `Pipeline multi-agente — ETA ~${formatEta(totalEtaSeconds(ingestDefs))} por artigo novo.`,
    );

    try {
      const online = await checkApiHealth();
      setApiOnline(online);
      if (!online) {
        throw new Error(
          "Backend offline. Execute: cd backend && uvicorn app.main:app --reload",
        );
      }

      const stats = await streamIngest((event) => {
        handlePipelineEvent(event);
      }, controller.signal);

      setIngestResult(stats);
      pipeline.completeSteps(ingestDefs);
      pipeline.setStatusLine(
        stats.saved > 0
          ? `Concluído — ${stats.saved} artigos salvos no feed.`
          : "Concluído — nenhum artigo novo para salvar.",
      );
      router.refresh();
    } catch (err) {
      if (controller.signal.aborted) {
        return;
      }
      pipeline.setSteps([
        {
          id: "error",
          label: "Falha na ingestão.",
          status: "error",
          detail: err instanceof Error ? err.message : "Erro desconhecido.",
        },
      ]);
      pipeline.setStatusLine(null);
      pipeline.setError(err instanceof Error ? err.message : "Erro ao atualizar o feed.");
    } finally {
      pipeline.finish();
    }
  }

  async function handleSeedDemo() {
    if (isBusy) {
      return;
    }

    pipeline.setError(null);
    setSeedResult(null);
    setSeedBusy(true);
    pipeline.setLogTitle("");
    pipeline.setSteps([]);
    pipeline.setStatusLine(null);

    try {
      const online = await checkApiHealth();
      setApiOnline(online);
      if (!online) {
        throw new Error(
          "Backend offline. Execute: cd backend && uvicorn app.main:app --reload",
        );
      }

      const result = await seedDemoData();
      setSeedResult(result);
      router.refresh();
    } catch (err) {
      pipeline.setError(err instanceof Error ? err.message : "Erro ao carregar dados demo.");
    } finally {
      setSeedBusy(false);
    }
  }

  const showDashboard = useMemo(
    () =>
      pipeline.logTitle === "Atualizando feed com IA" && parallel.totalItems > 0,
    [pipeline.logTitle, parallel.totalItems],
  );

  return (
    <div className="rounded-lg border border-border bg-surface-elevated p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-wide text-cyan">
            Ingestão
          </p>
          <p className="mt-1 text-sm text-muted">
            Busca fontes, deduplica e executa 3 agentes (Triador → Tradutor → Hype).
          </p>
          {apiOnline === false ? (
            <p className="mt-2 text-xs text-crimson" role="alert">
              Backend offline em {API_BASE} — inicie a API antes de usar o botão.
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          {pipeline.isRunning && pipeline.abortController ? (
            <button
              type="button"
              onClick={() =>
                pipeline.cancel({
                  label: "Ingestão cancelada.",
                  message: "Ingestão cancelada pelo usuário.",
                })
              }
              className="btn-interactive rounded-md border border-crimson bg-crimson/10 px-4 py-2 font-mono text-xs uppercase tracking-wide text-crimson hover:bg-crimson/25"
            >
              Cancelar
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void handleIngest()}
              disabled={isBusy}
              className="btn-interactive btn-primary rounded-md border border-cyan bg-cyan/10 px-4 py-2 font-mono text-xs uppercase tracking-wide text-cyan"
            >
              {pipeline.isRunning ? "Processando…" : "Atualizar feed"}
            </button>
          )}
          <button
            type="button"
            onClick={() => void handleSeedDemo()}
            disabled={isBusy}
            className="btn-interactive rounded-md border border-border px-4 py-2 font-mono text-xs uppercase tracking-wide text-muted hover:border-cyan/50 hover:text-cyan disabled:opacity-50"
          >
            Dados demo
          </button>
        </div>
      </div>

      {pipeline.isRunning ? (
        <div
          className="mt-3 flex items-center gap-2 rounded-md border border-cyan/25 bg-cyan/5 px-3 py-2"
          role="status"
        >
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan/30 border-t-cyan" />
          <p className="text-xs text-cyan">
            Atualização do feed em andamento — progresso em tempo real abaixo.
          </p>
        </div>
      ) : null}

      {showDashboard ? (
        <PipelineProgressDashboard
          logTitle={pipeline.logTitle}
          statusLine={pipeline.statusLine}
          totalItems={parallel.totalItems}
          itemsMap={parallel.itemsMap}
          entityLabel="artigo"
        />
      ) : (
        <ActivityLog
          title={pipeline.logTitle}
          steps={pipeline.steps}
          statusLine={pipeline.statusLine}
          visible={pipeline.isRunning || pipeline.steps.length > 0}
        />
      )}

      {pipeline.error ? (
        <p className="mt-3 text-sm text-crimson" role="alert">
          {pipeline.error}
        </p>
      ) : null}

      {seedResult && !isBusy ? (
        <p className="mt-3 font-mono text-xs text-muted">
          Demo — {seedResult.created} criados · {seedResult.skipped} já existiam
        </p>
      ) : null}

      {ingestResult && !pipeline.isRunning ? (
        <p className="mt-3 font-mono text-xs text-muted">
          {ingestResult.saved} salvas · {ingestResult.relevante} relevantes ·{" "}
          {ingestResult.skipped_duplicate} duplicadas ignoradas
          {ingestResult.errors.length > 0
            ? ` · ${ingestResult.errors.length} erros`
            : null}
        </p>
      ) : null}
    </div>
  );
}
