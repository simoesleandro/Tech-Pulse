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
