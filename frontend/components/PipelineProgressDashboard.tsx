"use client";

interface PipelineItemState {
  title: string;
  step_id: string;
  status: string;
  detail?: string;
  timestamp: number;
}

interface PipelineProgressDashboardProps {
  logTitle: string;
  statusLine: string | null;
  totalItems: number;
  itemsMap: Record<number, PipelineItemState>;
  stepLabels?: Record<string, string>;
  completedStepId?: string;
  entityLabel?: string;
}

const DEFAULT_STEP_LABELS: Record<string, string> = {
  triador: "🛡️ Triando Artigo (IA)",
  tradutor: "🇧🇷 Traduzindo Tópicos (IA)",
  hype: "🔥 Avaliando Hype (IA)",
  unified: "🤖 Análise Unificada (IA)",
  save: "💾 Gravando Item",
  fetch: "📥 Buscando",
  summarize: "📝 Resumindo",
  analyze: "🔍 Analisando",
  orchestrate: "🎯 Orquestrando",
  render: "📄 Renderizando",
  write: "✍️ Gravando no vault",
};

export function PipelineProgressDashboard({
  logTitle,
  statusLine,
  totalItems,
  itemsMap,
  stepLabels = DEFAULT_STEP_LABELS,
  completedStepId = "save",
  entityLabel = "artigo",
}: PipelineProgressDashboardProps) {
  const completed = Object.values(itemsMap).filter(
    (item) => item.step_id === completedStepId && item.status === "done",
  ).length;
  const percent = totalItems > 0 ? Math.round((completed / totalItems) * 100) : 0;
  const activeItems = Object.values(itemsMap).filter(
    (item) => !(item.step_id === completedStepId && item.status === "done"),
  );

  return (
    <div className="mt-4 rounded-lg border border-border bg-surface-elevated/40 p-4">
      <div className="mb-4 flex items-center justify-between border-b border-border/60 pb-3">
        <div>
          <h4 className="text-sm font-semibold text-foreground">{logTitle}</h4>
          {statusLine ? (
            <p className="mt-0.5 text-xs text-muted">{statusLine}</p>
          ) : null}
        </div>
        <span className="text-xs font-mono font-semibold text-cyan">{percent}%</span>
      </div>

      <div className="mb-4 h-1.5 w-full overflow-hidden rounded-full bg-border">
        <div
          className="h-full bg-gradient-to-r from-cyan to-violet transition-all duration-300 ease-out"
          style={{ width: `${Math.min(100, percent)}%` }}
        />
      </div>

      <div className="mb-4 grid grid-cols-3 gap-2 text-center">
        <div className="rounded border border-border/55 bg-surface p-2">
          <p className="text-[10px] font-mono uppercase tracking-wider text-muted">Total</p>
          <p className="mt-0.5 text-sm font-mono font-semibold text-foreground">{totalItems}</p>
        </div>
        <div className="rounded border border-border/55 bg-surface p-2">
          <p className="text-[10px] font-mono uppercase tracking-wider text-emerald">Processados</p>
          <p className="mt-0.5 text-sm font-mono font-semibold text-emerald">{completed}</p>
        </div>
        <div className="rounded border border-border/55 bg-surface p-2">
          <p className="text-[10px] font-mono uppercase tracking-wider text-cyan">Em andamento</p>
          <p className="mt-0.5 text-sm font-mono font-semibold text-cyan">
            {activeItems.filter((item) => item.status === "active").length}
          </p>
        </div>
      </div>

      <div className="mb-4 space-y-2">
        <p className="mb-1 text-[10px] font-mono uppercase tracking-wider text-muted">
          Processando por etapas
        </p>
        {Object.entries(itemsMap)
          .filter(([, item]) => !(item.step_id === completedStepId && item.status === "done"))
          .map(([idxStr, item]) => {
            const idx = parseInt(idxStr, 10);
            return (
              <div
                key={idx}
                className="flex items-center justify-between rounded-md border border-border/60 bg-surface p-2.5 transition-all duration-200 hover:border-cyan/35"
              >
                <div className="min-w-0 flex-1 pr-3">
                  <p className="truncate text-xs font-medium text-foreground">
                    {item.title || `${entityLabel} #${idx}`}
                  </p>
                  <p className="mt-0.5 truncate text-[10px] text-muted">
                    {item.detail || "Iniciando…"}
                  </p>
                </div>
                <span
                  className={`flex-shrink-0 rounded px-1.5 py-0.5 text-[9px] font-mono font-medium ${
                    item.status === "active"
                      ? "animate-pulse border border-cyan/20 bg-cyan/10 text-cyan"
                      : "bg-muted/15 text-muted"
                  }`}
                >
                  {stepLabels[item.step_id] || item.step_id}
                </span>
              </div>
            );
          })}
        {activeItems.length === 0 ? (
          <p className="py-2 text-center text-xs italic text-muted">
            Nenhum {entityLabel} ativo no momento.
          </p>
        ) : null}
      </div>

      <div className="border-t border-border/40 pt-3">
        <p className="mb-2 text-[10px] font-mono uppercase tracking-wider text-muted">
          Processados recentemente
        </p>
        <div className="max-h-32 space-y-1.5 overflow-y-auto">
          {Object.entries(itemsMap)
            .filter(([, item]) => item.step_id === completedStepId && item.status === "done")
            .sort((a, b) => b[1].timestamp - a[1].timestamp)
            .slice(0, 5)
            .map(([idxStr, item]) => (
              <div
                key={idxStr}
                className="flex items-center justify-between text-xs text-muted/90"
              >
                <span className="truncate pr-2">
                  ✅ {item.title || `${entityLabel} #${idxStr}`}
                </span>
                <span className="flex-shrink-0 text-[9px] font-mono text-emerald/80">
                  {item.detail?.includes("LIXO") ? "Filtrado (Lixo)" : "Concluído"}
                </span>
              </div>
            ))}
          {completed === 0 ? (
            <p className="py-1 text-center text-xs italic text-muted/60">
              Nenhum {entityLabel} processado ainda.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
