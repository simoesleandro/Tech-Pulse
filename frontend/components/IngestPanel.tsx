"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ActivityLog,
  markAllDone,
  type ActivityStep,
} from "@/components/ActivityLog";
import { API_BASE, checkApiHealth } from "@/lib/client-api";
import { fetchPipelineSteps, seedDemoData } from "@/lib/api";
import {
  applyPipelineStepEvent,
  formatEta,
  INGEST_PIPELINE_STEPS,
  mapApiSteps,
  totalEtaSeconds,
  type PipelineStepDef,
} from "@/lib/pipeline-steps";
import { streamIngest } from "@/lib/pipeline-stream";
import type { IngestResult, PipelineStepEvent, SeedResult } from "@/lib/types";

export function IngestPanel() {
  const router = useRouter();
  const [isBusy, setIsBusy] = useState(false);
  const [steps, setSteps] = useState<ActivityStep[]>([]);
  const [logTitle, setLogTitle] = useState("");
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null);
  const [seedResult, setSeedResult] = useState<SeedResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [ingestDefs, setIngestDefs] = useState<PipelineStepDef[]>(INGEST_PIPELINE_STEPS);

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

  function handlePipelineEvent(event: PipelineStepEvent) {
    if (event.type !== "step") {
      return;
    }

    setSteps((prev) => {
      const saveInProgress = prev.some(
        (step) => step.id === "save" && step.status === "active",
      );
      if (
        saveInProgress &&
        event.step_id === "triador" &&
        event.status === "active"
      ) {
        return prev;
      }
      return applyPipelineStepEvent(ingestDefs, event);
    });

    if (event.article_index && event.article_total) {
      const prefix = `Artigo ${event.article_index}/${event.article_total}`;
      if (event.step_id === "save") {
        setStatusLine(
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
              : event.step_id;

      if (event.status === "active") {
        setStatusLine(`${prefix} — ${agentLabel} em andamento…`);
      } else if (event.detail) {
        setStatusLine(`${prefix} — ${event.detail}`);
      }
    }
  }

  async function handleIngest() {
    if (isBusy) {
      return;
    }

    setError(null);
    setIngestResult(null);
    setIsBusy(true);
    setLogTitle("Atualizando feed com IA");
    setStatusLine(
      `Pipeline multi-agente — ETA ~${formatEta(totalEtaSeconds(ingestDefs))} por artigo novo.`,
    );
    setSteps(
      ingestDefs.map((def, index) => ({
        ...def,
        status: index === 0 ? "active" : "pending",
      })),
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
      });

      setIngestResult(stats);
      setSteps((prev) => markAllDone(prev.length > 0 ? prev : ingestDefs.map((def) => ({ ...def, status: "pending" as const }))));
      setStatusLine(
        stats.saved > 0
          ? `Concluído — ${stats.saved} artigos salvos no feed.`
          : "Concluído — nenhum artigo novo para salvar.",
      );
      router.refresh();
    } catch (err) {
      setSteps([
        {
          id: "error",
          label: "Falha na ingestão.",
          status: "error",
          detail: err instanceof Error ? err.message : "Erro desconhecido.",
        },
      ]);
      setStatusLine(null);
      setError(err instanceof Error ? err.message : "Erro ao atualizar o feed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleSeedDemo() {
    if (isBusy) {
      return;
    }

    setError(null);
    setSeedResult(null);
    setIsBusy(true);
    setLogTitle("");
    setSteps([]);
    setStatusLine(null);

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
      setError(err instanceof Error ? err.message : "Erro ao carregar dados demo.");
    } finally {
      setIsBusy(false);
    }
  }

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
          <button
            type="button"
            onClick={() => void handleIngest()}
            disabled={isBusy}
            className="btn-interactive btn-primary rounded-md border border-cyan bg-cyan/10 px-4 py-2 font-mono text-xs uppercase tracking-wide text-cyan"
          >
            {isBusy ? "Processando…" : "Atualizar feed"}
          </button>
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

      {isBusy ? (
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

      <ActivityLog
        title={logTitle}
        steps={steps}
        statusLine={statusLine}
        visible={isBusy || steps.length > 0}
      />

      {error ? (
        <p className="mt-3 text-sm text-crimson" role="alert">
          {error}
        </p>
      ) : null}

      {seedResult && !isBusy ? (
        <p className="mt-3 font-mono text-xs text-muted">
          Demo — {seedResult.created} criados · {seedResult.skipped} já existiam
        </p>
      ) : null}

      {ingestResult && !isBusy ? (
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
