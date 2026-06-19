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


def steps_to_dict(steps) -> list[dict]:
    return [
        {
            "id": step.id,
            "label": step.label,
            "estimated_seconds": step.estimated_seconds,
            "agent": step.agent,
        }
        for step in steps
    ]


def get_ingest_pipeline_steps() -> list[PipelineStepMeta]:
    from app.services.settings import load_settings
    settings = load_settings()
    mode = settings.get("pipeline_mode", "unified")
    
    steps = [
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
    ]
    
    import os
    has_groq = bool(os.getenv("GROQ_API_KEY", "").strip())

    if mode == "unified":
        est = 5 if has_groq else 45
        steps.append(
            PipelineStepMeta(
                id="unified",
                label="Análise Unificada (Triagem + Tradução + Hype por IA)…",
                estimated_seconds=est,
                agent="unified",
            )
        )
    else:
        provider_triador = os.getenv("PROVIDER_TRIADOR", "ollama").strip().lower()
        provider_tradutor = os.getenv("PROVIDER_TRADUTOR", "ollama").strip().lower()
        provider_hype = os.getenv("PROVIDER_HYPE", "groq").strip().lower()
        
        est_triador = 4 if (has_groq and provider_triador == "groq") else 40
        est_tradutor = 5 if (has_groq and provider_tradutor == "groq") else 80
        est_hype = 4 if (has_groq and provider_hype == "groq") else 40
        
        steps.extend([
            PipelineStepMeta(
                id="triador",
                label="Agente 1 — Triador: classificando relevância (RELEVANTE ou LIXO)…",
                estimated_seconds=est_triador,
                agent="triador",
            ),
            PipelineStepMeta(
                id="tradutor",
                label="Agente 2 — Tradutor: título e descrição em PT-BR…",
                estimated_seconds=est_tradutor,
                agent="tradutor",
            ),
            PipelineStepMeta(
                id="hype",
                label="Agente 3 — Analista: avaliando hype da comunidade (0–5)…",
                estimated_seconds=est_hype,
                agent="hype",
            )
        ])
        
    steps.append(
        PipelineStepMeta(
            id="save",
            label="Salvando artigos no banco de dados…",
            estimated_seconds=2,
            agent=None,
        )
    )
    return steps


def get_backfill_pipeline_steps() -> list[PipelineStepMeta]:
    import os
    has_groq = bool(os.getenv("GROQ_API_KEY", "").strip())
    provider_tradutor = os.getenv("PROVIDER_TRADUTOR", "ollama").strip().lower()
    provider_hype = os.getenv("PROVIDER_HYPE", "groq").strip().lower()
    
    est_tradutor = 5 if (has_groq and provider_tradutor == "groq") else 80
    est_hype = 4 if (has_groq and provider_hype == "groq") else 40

    return [
        PipelineStepMeta(
            id="pick",
            label="Selecionando próximo artigo pendente de tradução…",
            estimated_seconds=1,
            agent=None,
        ),
        PipelineStepMeta(
            id="tradutor",
            label="Agente 2 — Tradutor: título e resumo em português…",
            estimated_seconds=est_tradutor,
            agent="tradutor",
        ),
        PipelineStepMeta(
            id="hype",
            label="Agente 3 — Analista: calculando hype (0–5 estrelas)…",
            estimated_seconds=est_hype,
            agent="hype",
        ),
        PipelineStepMeta(
            id="save",
            label="Persistindo artigo enriquecido no feed…",
            estimated_seconds=2,
            agent=None,
        ),
    ]
