"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ActivityLog,
  markAllDone,
  type ActivityStep,
  type StepStatus,
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
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  const [articlesMap, setArticlesMap] = useState<Record<number, { title: string; step_id: string; status: string; detail?: string; timestamp: number }>>({});
  const [totalArticles, setTotalArticles] = useState(0);

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

    if (!event.article_index) {
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
        }),
      );
      return;
    }

    const idx = event.article_index;
    if (event.article_total) {
      setTotalArticles(event.article_total);
    }
    setArticlesMap((prev) => ({
      ...prev,
      [idx]: {
        title: event.title || prev[idx]?.title || "",
        step_id: event.step_id,
        status: event.status,
        detail: event.detail,
        timestamp: Date.now(),
      },
    }));

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
            : event.step_id === "unified"
              ? "Análise Unificada"
              : event.step_id;

    if (event.status === "active") {
      setStatusLine(`${prefix} — ${agentLabel} em andamento…`);
    } else if (event.detail) {
      setStatusLine(`${prefix} — ${event.detail}`);
    }
  }

  useEffect(() => {
    if (totalArticles === 0) return;

    setSteps((prev) => {
      const stepOrder = prev.map((s) => s.id);
      const agentStepIds = new Set(["triador", "tradutor", "hype", "unified", "save"]);
      return prev.map((step) => {
        if (!agentStepIds.has(step.id)) {
          // fetch ou dedup: mantém o status original do pipeline
          return step;
        }

        const stepIdx = stepOrder.indexOf(step.id);
        if (stepIdx === -1) {
          return step;
        }

        let completedCount = 0;
        const activeArticles: number[] = [];

        for (const [idxStr, info] of Object.entries(articlesMap)) {
          const idx = parseInt(idxStr, 10);
          const currentStepIdx = stepOrder.indexOf(info.step_id);

          if (
            currentStepIdx > stepIdx ||
            (currentStepIdx === stepIdx && info.status === "done")
          ) {
            completedCount++;
          } else if (currentStepIdx === stepIdx && info.status === "active") {
            activeArticles.push(idx);
          }
        }

        let status: StepStatus = "pending";
        let detail = "";

        if (completedCount === totalArticles) {
          status = "done";
          detail = `Todos os ${totalArticles} artigos processados.`;
        } else if (
          activeArticles.length > 0 ||
          (completedCount > 0 && completedCount < totalArticles)
        ) {
          status = "active";
          detail = `Processando: ${
            activeArticles.length > 0
              ? `Artigo(s) ${activeArticles.join(", ")}`
              : "aguardando"
          } · ${completedCount}/${totalArticles} concluídos`;
        } else {
          status = "pending";
          detail = "Aguardando artigos...";
        }

        return {
          ...step,
          status,
          detail,
        };
      });
    });
  }, [articlesMap, totalArticles]);

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
            label: "Ingestão cancelada.",
            status: "error" as const,
            detail: "Operação interrompida pelo usuário.",
          },
        ];
      });
      setError("Ingestão cancelada pelo usuário.");
      setIsBusy(false);
      setAbortController(null);
    }
  }

  async function handleIngest() {
    if (isBusy) {
      return;
    }

    const controller = new AbortController();
    setAbortController(controller);
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
    setArticlesMap({});
    setTotalArticles(0);

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
      setSteps((prev) =>
        markAllDone(
          prev.length > 0
            ? prev
            : ingestDefs.map((def) => ({ ...def, status: "pending" as const })),
        ),
      );
      setStatusLine(
        stats.saved > 0
          ? `Concluído — ${stats.saved} artigos salvos no feed.`
          : "Concluído — nenhum artigo novo para salvar.",
      );
      router.refresh();
    } catch (err) {
      if (controller.signal.aborted) {
        return;
      }
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
      setAbortController(null);
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
          {isBusy && abortController ? (
            <button
              type="button"
              onClick={handleCancel}
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
              {isBusy ? "Processando…" : "Atualizar feed"}
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

      {logTitle === "Atualizando feed com IA" && totalArticles > 0 ? (
        <div className="mt-4 rounded-lg border border-border bg-surface-elevated/40 p-4">
          {/* Header & General Progress */}
          <div className="flex items-center justify-between border-b border-border/60 pb-3 mb-4">
            <div>
              <h4 className="text-sm font-semibold text-foreground">{logTitle}</h4>
              <p className="text-xs text-muted mt-0.5">{statusLine}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono text-cyan font-semibold">
                {totalArticles > 0
                  ? Math.round(
                      (Object.values(articlesMap).filter(
                        (a) => a.step_id === "save" && a.status === "done",
                      ).length /
                        totalArticles) *
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
              className="h-full bg-gradient-to-r from-cyan to-violet transition-all duration-300 ease-out"
              style={{
                width: `${
                  totalArticles > 0
                    ? Math.min(
                        100,
                        (Object.values(articlesMap).filter(
                          (a) => a.step_id === "save" && a.status === "done",
                        ).length /
                          totalArticles) *
                          100,
                      )
                    : 0
                }%`,
              }}
            />
          </div>

          {/* Stats grid */}
          <div className="grid grid-cols-3 gap-2 mb-4 text-center">
            <div className="rounded border border-border/55 bg-surface p-2">
              <p className="text-[10px] font-mono uppercase tracking-wider text-muted">Total</p>
              <p className="text-sm font-mono font-semibold text-foreground mt-0.5">{totalArticles}</p>
            </div>
            <div className="rounded border border-border/55 bg-surface p-2">
              <p className="text-[10px] font-mono uppercase tracking-wider text-emerald">Processados</p>
              <p className="text-sm font-mono font-semibold text-emerald mt-0.5">
                {Object.values(articlesMap).filter((a) => a.step_id === "save" && a.status === "done").length}
              </p>
            </div>
            <div className="rounded border border-border/55 bg-surface p-2">
              <p className="text-[10px] font-mono uppercase tracking-wider text-cyan">Em Andamento</p>
              <p className="text-sm font-mono font-semibold text-cyan mt-0.5">
                {Object.values(articlesMap).filter((a) => !(a.step_id === "save" && a.status === "done") && a.status === "active").length}
              </p>
            </div>
          </div>

          {/* Active articles cards */}
          <div className="space-y-2 mb-4">
            <p className="text-[10px] font-mono uppercase tracking-wider text-muted mb-1">Processando por Agentes de IA</p>
            {Object.entries(articlesMap)
              .filter(([_, article]) => !(article.step_id === "save" && article.status === "done"))
              .map(([idxStr, article]) => {
                const idx = parseInt(idxStr, 10);
                const stepLabels: Record<string, string> = {
                  triador: "🛡️ Triando Artigo (IA)",
                  tradutor: "🇧🇷 Traduzindo Tópicos (IA)",
                  hype: "🔥 Avaliando Hype (IA)",
                  save: "💾 Gravando Item",
                };
                return (
                  <div
                    key={idx}
                    className="flex items-center justify-between rounded-md border border-border/60 bg-surface p-2.5 transition-all duration-200 hover:border-cyan/35"
                  >
                    <div className="flex-1 min-w-0 pr-3">
                      <p className="text-xs font-medium text-foreground truncate">
                        {article.title || `Artigo #${idx}`}
                      </p>
                      <p className="text-[10px] text-muted truncate mt-0.5">
                        {article.detail || "Iniciando classificação..."}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span
                        className={`rounded px-1.5 py-0.5 text-[9px] font-mono font-medium ${
                          article.status === "active"
                            ? "bg-cyan/10 text-cyan border border-cyan/20 animate-pulse"
                            : "bg-muted/15 text-muted"
                        }`}
                      >
                        {stepLabels[article.step_id] || article.step_id}
                      </span>
                    </div>
                  </div>
                );
              })}
            {Object.values(articlesMap).filter((a) => !(a.step_id === "save" && a.status === "done")).length === 0 && (
              <p className="text-xs text-muted italic text-center py-2">Nenhum artigo ativo no momento.</p>
            )}
          </div>

          {/* Recently completed logs */}
          <div className="border-t border-border/40 pt-3">
            <p className="text-[10px] font-mono uppercase tracking-wider text-muted mb-2">Processados Recentemente</p>
            <div className="space-y-1.5 max-h-32 overflow-y-auto">
              {Object.entries(articlesMap)
                .filter(([_, article]) => article.step_id === "save" && article.status === "done")
                .sort((a, b) => b[1].timestamp - a[1].timestamp)
                .slice(0, 5)
                .map(([idxStr, article]) => (
                  <div key={idxStr} className="flex items-center justify-between text-xs text-muted/90">
                    <span className="truncate pr-2">✅ {article.title || `Artigo #${idxStr}`}</span>
                    <span className="text-[9px] font-mono text-emerald/80 flex-shrink-0">
                      {article.detail?.includes("LIXO") ? "Filtrado (Lixo)" : "Salvo no feed"}
                    </span>
                  </div>
                ))}
              {Object.values(articlesMap).filter((a) => a.step_id === "save" && a.status === "done").length === 0 && (
                <p className="text-xs text-muted/60 italic text-center py-1">Nenhum artigo processado ainda.</p>
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
