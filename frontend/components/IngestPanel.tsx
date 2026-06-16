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
import type { EnrichBackfillResult, IngestResult } from "@/lib/types";

type ActiveAction = "idle" | "ingest" | "backfill";

const INGEST_STEP_DEFS = [
  { id: "fetch", label: "Buscando artigos em dev.to, Reddit e GitHub Trends…" },
  { id: "dedup", label: "Filtrando duplicatas já existentes no feed…" },
  {
    id: "classify",
    label: "Gemma4: classificando relevância (RELEVANTE ou LIXO)…",
  },
  {
    id: "translate",
    label: "Gemma4: traduzindo título e gerando descrição em PT-BR…",
  },
  {
    id: "hype",
    label: "Gemma4: avaliando hype da comunidade (0–5 estrelas)…",
  },
  { id: "save", label: "Salvando artigos no banco de dados…" },
];

const BACKFILL_STEP_DEFS = [
  { id: "pick", label: "Selecionando próximo artigo pendente de tradução…" },
  { id: "analyze", label: "Gemma4: analisando conteúdo e contexto da fonte…" },
  {
    id: "translate",
    label: "Gemma4: traduzindo título e escrevendo resumo em português…",
  },
  {
    id: "hype",
    label: "Gemma4: calculando hype com base no engajamento da comunidade…",
  },
  { id: "save", label: "Persistindo artigo enriquecido no feed…" },
];

function advanceSteps(
  defs: Array<{ id: string; label: string }>,
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
  const stepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    void checkApiHealth().then(setApiOnline);
  }, []);

  function clearStepTimer() {
    if (stepTimerRef.current) {
      clearInterval(stepTimerRef.current);
      stepTimerRef.current = null;
    }
  }

  function startStepAnimation(
    defs: Array<{ id: string; label: string }>,
    intervalMs = 12_000,
  ) {
    clearStepTimer();
    let index = 0;
    setSteps(advanceSteps(defs, index));

    stepTimerRef.current = setInterval(() => {
      if (index < defs.length - 1) {
        index += 1;
        setSteps(advanceSteps(defs, index));
      }
    }, intervalMs);
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
    setStatusLine("Conectando às fontes e ao Ollama…");
    setSteps(advanceSteps(INGEST_STEP_DEFS, 0));
    startStepAnimation(INGEST_STEP_DEFS, 15_000);

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
          INGEST_STEP_DEFS.map((def) => ({ ...def, status: "pending" as const })),
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
      "Aguarde — o Gemma4 processa um artigo por vez (pode levar 2–4 min cada).",
    );
    setSteps(advanceSteps(BACKFILL_STEP_DEFS, 0, "Preparando primeiro artigo…"));

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
        setSteps(advanceSteps(BACKFILL_STEP_DEFS, stepIndex, pendingHint));

        stepTimerRef.current = setInterval(() => {
          stepIndex = Math.min(stepIndex + 1, BACKFILL_STEP_DEFS.length - 2);
          setSteps(advanceSteps(BACKFILL_STEP_DEFS, stepIndex, pendingHint));
        }, 8_000);

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
              BACKFILL_STEP_DEFS.map((def) => ({
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
            Busca fontes, traduz para PT-BR e o Gemma4 classifica relevância e hype (0–5).
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
