from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineStepMeta:
    id: str
    label: str
    estimated_seconds: int
    agent: str | None = None


INGEST_PIPELINE_STEPS: tuple[PipelineStepMeta, ...] = (
    PipelineStepMeta(
        id="fetch",
        label="Buscando artigos em dev.to, Reddit, Hacker News, GitHub e RSS…",
        estimated_seconds=20,
        agent=None,
    ),
    PipelineStepMeta(
        id="dedup",
        label="Filtrando duplicatas já existentes no feed…",
        estimated_seconds=1,
        agent=None,
    ),
    PipelineStepMeta(
        id="triador",
        label="Agente 1 — Triador: classificando relevância (RELEVANTE ou LIXO)…",
        estimated_seconds=50,
        agent="triador",
    ),
    PipelineStepMeta(
        id="tradutor",
        label="Agente 2 — Tradutor: título e descrição em PT-BR…",
        estimated_seconds=90,
        agent="tradutor",
    ),
    PipelineStepMeta(
        id="hype",
        label="Agente 3 — Analista: avaliando hype da comunidade (0–5)…",
        estimated_seconds=45,
        agent="hype",
    ),
    PipelineStepMeta(
        id="save",
        label="Salvando artigos no banco de dados…",
        estimated_seconds=2,
        agent=None,
    ),
)

BACKFILL_PIPELINE_STEPS: tuple[PipelineStepMeta, ...] = (
    PipelineStepMeta(
        id="pick",
        label="Selecionando próximo artigo pendente de tradução…",
        estimated_seconds=1,
        agent=None,
    ),
    PipelineStepMeta(
        id="triador",
        label="Agente 1 — Triador: verificando relevância…",
        estimated_seconds=50,
        agent="triador",
    ),
    PipelineStepMeta(
        id="tradutor",
        label="Agente 2 — Tradutor: título e resumo em português…",
        estimated_seconds=90,
        agent="tradutor",
    ),
    PipelineStepMeta(
        id="hype",
        label="Agente 3 — Analista: calculando hype (0–5 estrelas)…",
        estimated_seconds=45,
        agent="hype",
    ),
    PipelineStepMeta(
        id="save",
        label="Persistindo artigo enriquecido no feed…",
        estimated_seconds=2,
        agent=None,
    ),
)


def steps_to_dict(steps: tuple[PipelineStepMeta, ...]) -> list[dict]:
    return [
        {
            "id": step.id,
            "label": step.label,
            "estimated_seconds": step.estimated_seconds,
            "agent": step.agent,
        }
        for step in steps
    ]
