"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ActivityLog,
  markAllDone,
  type ActivityStep,
} from "@/components/ActivityLog";
import { checkApiHealth } from "@/lib/client-api";
import { fetchPipelineSteps } from "@/lib/api";
import {
  applyPipelineStepEvent,
  BACKFILL_PIPELINE_STEPS,
  formatEta,
  INGEST_PIPELINE_STEPS,
  mapApiSteps,
  totalEtaSeconds,
  type PipelineStepDef,
} from "@/lib/pipeline-steps";
import { streamEnrichBackfill, streamIngest } from "@/lib/pipeline-stream";
import type {
  EnrichBackfillResult,
  IngestResult,
  PipelineStepEvent,
} from "@/lib/types";

type ActiveAction = "idle" | "ingest" | "backfill";

export function IngestPanel() {
  const router = useRouter();
  const [isBusy, setIsBusy] = useState(false);
  const [activeAction, setActiveAction] = useState<ActiveAction>("idle");
  const [steps, setSteps] = useState<ActivityStep[]>([]);
  const [logTitle, setLogTitle] = useState("");
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [ingestResult, setIngestResult] = useState<IngestResult | null>(null);
  const [backfillResult, setBackfillResult] = useState<EnrichBackfillResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [ingestDefs, setIngestDefs] = useState<PipelineStepDef[]>(INGEST_PIPELINE_STEPS);
  const [backfillDefs, setBackfillDefs] = useState<PipelineStepDef[]>(
    BACKFILL_PIPELINE_STEPS,
  );

  useEffect(() => {
    void checkApiHealth().then(setApiOnline);
    void fetchPipelineSteps()
      .then((config) => {
        setIngestDefs(mapApiSteps(config.ingest));
        setBackfillDefs(mapApiSteps(config.backfill));
      })
      .catch(() => {
        /* mantém fallback estático */
      });
  }, []);

  function handlePipelineEvent(
    defs: PipelineStepDef[],
    event: PipelineStepEvent,
  ) {
    if (event.type !== "step") {
      return;
    }

    setSteps(applyPipelineStepEvent(defs, event));

    if (event.article_index && event.article_total) {
      setStatusLine(
        `Artigo ${event.article_index}/${event.article_total} — acompanhe o agente ativo abaixo.`,
      );
    }
  }

  async function handleIngest() {
    if (isBusy) {
      return;
    }

    setError(null);
    setIngestResult(null);
    setBackfillResult(null);
    setActiveAction("ingest");
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
        handlePipelineEvent(ingestDefs, event);
      });

      setSteps(
        markAllDone(
          ingestDefs.map((def) => ({ ...def, status: "pending" as const })),
          `${stats.saved} salvas · ${stats.relevante} relevantes · ${stats.skipped_duplicate} duplicadas ignoradas`,
        ),
      );
      setStatusLine("Ingestão concluída.");
      setIngestResult(stats);
      router.refresh();
    } catch (err) {
      setStatusLine(null);
      setSteps([
        {
          id: "error",
          label: "Falha na ingestão.",
          status: "error",
          detail: err instanceof Error ? err.message : "Erro desconhecido.",
        },
      ]);
      setError(err instanceof Error ? err.message : "Erro desconhecido na ingestão.");
    } finally {
      setIsBusy(false);
      setActiveAction("idle");
    }
  }

  async function handleBackfill() {
    if (isBusy) {
      return;
    }

    setError(null);
    setIngestResult(null);
    setBackfillResult(null);
    setActiveAction("backfill");
    setIsBusy(true);
    setLogTitle("Traduzindo artigos pendentes");
    setStatusLine(
      "Aguarde — 3 agentes por artigo (Triador · Tradutor · Hype).",
    );
    setSteps(
      backfillDefs.map((def, index) => ({
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

      let totalProcessed = 0;
      let totalErrors = 0;
      let remaining = 1;
      let candidates = 0;
      let rounds = 0;
      const maxRounds = 25;

      while (remaining > 0 && rounds < maxRounds) {
        const stats = await streamEnrichBackfill(1, (event) => {
          handlePipelineEvent(backfillDefs, event);
        });

        if (rounds === 0) {
          candidates = stats.candidates;
        }

        totalProcessed += stats.processed;
        totalErrors += stats.errors;
        remaining = stats.remaining;
        rounds += 1;

        if (stats.processed > 0) {
          setSteps(
            markAllDone(
              backfillDefs.map((def) => ({ ...def, status: "pending" as const })),
              `Artigo ${totalProcessed} concluído · ${remaining} pendente(s)`,
            ),
          );
        }

        if (stats.processed === 0) {
          if (stats.errors > 0) {
            setStatusLine("Erro ao processar artigo. Verifique se o Ollama está ativo.");
          }
          break;
        }
      }

      const finalResult: EnrichBackfillResult = {
        processed: totalProcessed,
        errors: totalErrors,
        candidates,
        remaining,
      };

      setBackfillResult(finalResult);

      if (finalResult.candidates === 0 && finalResult.processed === 0) {
        setSteps([
          {
            id: "done",
            label: "Nenhum artigo pendente de tradução no momento.",
            status: "done",
          },
        ]);
        setStatusLine("Nada a traduzir.");
      } else {
        setSteps([
          {
            id: "complete",
            label: "Tradução em lote finalizada.",
            status: "done",
            detail: `${finalResult.processed} traduzidos · ${finalResult.remaining} pendentes · ${finalResult.errors} erros`,
          },
        ]);
        setStatusLine("Tradução finalizada.");
      }

      router.refresh();
    } catch (err) {
      setSteps([
        {
          id: "error",
          label: "Falha na tradução.",
          status: "error",
          detail: err instanceof Error ? err.message : "Erro desconhecido.",
        },
      ]);
      setStatusLine(null);
      setError(
        err instanceof Error ? err.message : "Erro ao traduzir artigos pendentes.",
      );
    } finally {
      setIsBusy(false);
      setActiveAction("idle");
    }
  }

  const isIngesting = isBusy && activeAction === "ingest";
  const isBackfilling = isBusy && activeAction === "backfill";

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
              Backend offline em localhost:8000 — inicie a API antes de usar os botões.
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void handleBackfill()}
            disabled={isBusy}
            className="btn-interactive rounded-md border border-border px-4 py-2 font-mono text-xs uppercase tracking-wide text-muted"
          >
            {isBackfilling ? "Traduzindo…" : "Traduzir pendentes"}
          </button>
          <button
            type="button"
            onClick={() => void handleIngest()}
            disabled={isBusy}
            className="btn-interactive btn-primary rounded-md border border-cyan bg-cyan/10 px-4 py-2 font-mono text-xs uppercase tracking-wide text-cyan"
          >
            {isIngesting ? "Processando…" : "Atualizar feed"}
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
            {isBackfilling
              ? "Tradução em andamento — progresso em tempo real abaixo."
              : "Atualização do feed em andamento — progresso em tempo real abaixo."}
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

      {ingestResult && !isBusy ? (
        <p className="mt-3 font-mono text-xs text-muted">
          {ingestResult.saved} salvas · {ingestResult.relevante} relevantes ·{" "}
          {ingestResult.skipped_duplicate} duplicadas ignoradas
          {ingestResult.errors.length > 0
            ? ` · ${ingestResult.errors.length} erros`
            : null}
        </p>
      ) : null}

      {backfillResult && !isBusy ? (
        <p className="mt-3 font-mono text-xs text-muted">
          {backfillResult.candidates === 0 && backfillResult.processed === 0
            ? "Nenhum artigo pendente de tradução."
            : `${backfillResult.processed} traduzidos · ${backfillResult.remaining} ainda pendentes · ${backfillResult.errors} erros`}
        </p>
      ) : null}
    </div>
  );
}
