"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import {
  ActivityLog,
  buildSteps,
  markAllDone,
  type ActivityStep,
} from "@/components/ActivityLog";
import { checkApiHealth } from "@/lib/client-api";
import { enrichBackfill, triggerIngest } from "@/lib/api";
import {
  BACKFILL_PIPELINE_STEPS,
  formatEta,
  INGEST_PIPELINE_STEPS,
  totalEtaSeconds,
  type PipelineStepDef,
} from "@/lib/pipeline-steps";
import type { EnrichBackfillResult, IngestResult } from "@/lib/types";

type ActiveAction = "idle" | "ingest" | "backfill";

function advanceSteps(
  defs: PipelineStepDef[],
  index: number,
  detail?: string,
): ActivityStep[] {
  return buildSteps(defs, index).map((step, i) =>
    i === index && detail ? { ...step, detail } : step,
  );
}

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
  const stepTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    void checkApiHealth().then(setApiOnline);
  }, []);

  function clearStepTimer() {
    if (stepTimerRef.current) {
      clearTimeout(stepTimerRef.current);
      stepTimerRef.current = null;
    }
  }

  function startStepAnimation(defs: PipelineStepDef[], startIndex = 0) {
    clearStepTimer();
    let index = startIndex;
    setSteps(advanceSteps(defs, index));

    const scheduleNext = () => {
      const current = defs[index];
      const delayMs = Math.max((current?.estimatedSeconds ?? 8) * 1000, 2000);

      stepTimerRef.current = setTimeout(() => {
        if (index < defs.length - 1) {
          index += 1;
          setSteps(advanceSteps(defs, index));
          scheduleNext();
        }
      }, delayMs);
    };

    scheduleNext();
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
      `Pipeline multi-agente — ETA total aproximado ${formatEta(totalEtaSeconds(INGEST_PIPELINE_STEPS))} por artigo novo.`,
    );
    setSteps(advanceSteps(INGEST_PIPELINE_STEPS, 0));
    startStepAnimation(INGEST_PIPELINE_STEPS);

    try {
      const online = await checkApiHealth();
      setApiOnline(online);
      if (!online) {
        throw new Error(
          "Backend offline. Execute: cd backend && uvicorn app.main:app --reload",
        );
      }

      const stats = await triggerIngest();
      clearStepTimer();
      setSteps(
        markAllDone(
          INGEST_PIPELINE_STEPS.map((def) => ({
            ...def,
            status: "pending" as const,
          })),
          `${stats.saved} salvas · ${stats.relevante} relevantes · ${stats.skipped_duplicate} duplicadas ignoradas`,
        ),
      );
      setStatusLine("Ingestão concluída.");
      setIngestResult(stats);
      router.refresh();
    } catch (err) {
      clearStepTimer();
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
      `Aguarde — 3 agentes por artigo (Triador ~50s · Tradutor ~90s · Hype ~45s).`,
    );
    setSteps(advanceSteps(BACKFILL_PIPELINE_STEPS, 0, "Preparando primeiro artigo…"));

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
      let lastResult: EnrichBackfillResult | null = null;
      let rounds = 0;
      const maxRounds = 25;

      while (remaining > 0 && rounds < maxRounds) {
        const articleNum = totalProcessed + totalErrors + 1;
        const pendingHint =
          candidates > 0
            ? `artigo ${articleNum} de ~${candidates}`
            : `rodada ${rounds + 1}`;

        setStatusLine(`Processando ${pendingHint}… não feche esta página.`);

        clearStepTimer();
        let stepIndex = 0;
        setSteps(advanceSteps(BACKFILL_PIPELINE_STEPS, stepIndex, pendingHint));

        const advanceBackfillStep = () => {
          const current = BACKFILL_PIPELINE_STEPS[stepIndex];
          const delayMs = Math.max((current?.estimatedSeconds ?? 8) * 1000, 2000);
          stepTimerRef.current = setTimeout(() => {
            if (stepIndex < BACKFILL_PIPELINE_STEPS.length - 2) {
              stepIndex += 1;
              setSteps(advanceSteps(BACKFILL_PIPELINE_STEPS, stepIndex, pendingHint));
              advanceBackfillStep();
            }
          }, delayMs);
        };
        advanceBackfillStep();

        const stats = await enrichBackfill(1);
        clearStepTimer();

        lastResult = stats;
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
              BACKFILL_PIPELINE_STEPS.map((def) => ({
                ...def,
                status: "pending" as const,
              })),
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

      const finalResult: EnrichBackfillResult = lastResult
        ? {
            ...lastResult,
            processed: totalProcessed,
            errors: totalErrors,
            candidates,
          }
        : {
            processed: 0,
            errors: 0,
            candidates: 0,
            remaining: 0,
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
      clearStepTimer();
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
              ? "Tradução em andamento — acompanhe os passos abaixo."
              : "Atualização do feed em andamento — acompanhe os passos abaixo."}
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
