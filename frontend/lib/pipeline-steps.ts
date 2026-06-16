export interface PipelineStepDef {
  id: string;
  label: string;
  estimatedSeconds: number;
  agent?: string | null;
}

/** Espelha `backend/app/services/pipeline_config.py` (v1 estática). */
export const INGEST_PIPELINE_STEPS: PipelineStepDef[] = [
  {
    id: "fetch",
    label: "Buscando artigos em dev.to, Reddit, Hacker News, GitHub e RSS…",
    estimatedSeconds: 20,
  },
  {
    id: "dedup",
    label: "Filtrando duplicatas já existentes no feed…",
    estimatedSeconds: 1,
  },
  {
    id: "triador",
    label: "Agente 1 — Triador: classificando relevância (RELEVANTE ou LIXO)…",
    estimatedSeconds: 50,
    agent: "triador",
  },
  {
    id: "tradutor",
    label: "Agente 2 — Tradutor: título e descrição em PT-BR…",
    estimatedSeconds: 90,
    agent: "tradutor",
  },
  {
    id: "hype",
    label: "Agente 3 — Analista: avaliando hype da comunidade (0–5)…",
    estimatedSeconds: 45,
    agent: "hype",
  },
  {
    id: "save",
    label: "Salvando artigos no banco de dados…",
    estimatedSeconds: 2,
  },
];

export const BACKFILL_PIPELINE_STEPS: PipelineStepDef[] = [
  {
    id: "pick",
    label: "Selecionando próximo artigo pendente de tradução…",
    estimatedSeconds: 1,
  },
  {
    id: "triador",
    label: "Agente 1 — Triador: verificando relevância…",
    estimatedSeconds: 50,
    agent: "triador",
  },
  {
    id: "tradutor",
    label: "Agente 2 — Tradutor: título e resumo em português…",
    estimatedSeconds: 90,
    agent: "tradutor",
  },
  {
    id: "hype",
    label: "Agente 3 — Analista: calculando hype (0–5 estrelas)…",
    estimatedSeconds: 45,
    agent: "hype",
  },
  {
    id: "save",
    label: "Persistindo artigo enriquecido no feed…",
    estimatedSeconds: 2,
  },
];

export function formatEta(seconds: number): string {
  if (seconds < 60) {
    return `~${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder > 0 ? `~${minutes}m ${remainder}s` : `~${minutes}m`;
}

export function totalEtaSeconds(steps: PipelineStepDef[]): number {
  return steps.reduce((sum, step) => sum + step.estimatedSeconds, 0);
}

export function mapApiSteps(
  steps: Array<{
    id: string;
    label: string;
    estimated_seconds: number;
    agent?: string | null;
  }>,
): PipelineStepDef[] {
  return steps.map((step) => ({
    id: step.id,
    label: step.label,
    estimatedSeconds: step.estimated_seconds,
    agent: step.agent,
  }));
}

export function applyPipelineStepEvent(
  defs: PipelineStepDef[],
  event: Extract<
    import("@/lib/types").PipelineStepEvent,
    { type: "step" }
  >,
): import("@/components/ActivityLog").ActivityStep[] {
  const activeIndex = defs.findIndex((def) => def.id === event.step_id);
  if (activeIndex < 0) {
    return defs.map((def) => ({ ...def, status: "pending" as const }));
  }

  const agentStepIds = new Set(["triador", "tradutor", "hype", "save"]);
  const isNewArticleCycle =
    event.step_id === "triador" && event.status === "active";

  return defs.map((def, index) => {
    let status: "pending" | "active" | "done" = "pending";

    if (isNewArticleCycle && agentStepIds.has(def.id)) {
      if (def.id === "triador") {
        status = "active";
      }
      return {
        ...def,
        status,
        detail: def.id === "triador" ? event.detail : undefined,
      };
    }

    if (event.status === "active") {
      if (index < activeIndex) {
        status = "done";
      } else if (index === activeIndex) {
        status = "active";
      }
    } else if (index <= activeIndex) {
      status = "done";
    }

    return {
      ...def,
      status,
      detail: index === activeIndex ? event.detail : undefined,
    };
  });
}
