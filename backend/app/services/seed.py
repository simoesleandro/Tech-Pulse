from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NewsItem

DEMO_ARTICLES = [
    {
        "title": "Construindo um orquestrador de agentes LLM do zero com Python",
        "title_original": "Building an LLM Agent Orchestrator from Scratch with Python",
        "description": "Guia prático para montar um orquestrador de agentes de IA usando Python, do desenho à execução.",
        "url": "https://example.com/techpulse/demo-llm-agent",
        "source": "dev.to",
        "ai_relevance": "RELEVANTE",
        "hype_score": 4,
        "is_enriched": True,
    },
    {
        "title": "Estratégias de indexação no SQLite para cargas intensas de leitura",
        "title_original": "SQLite Indexing Strategies for Read-Heavy Workloads",
        "description": "Como escolher índices e otimizar consultas quando o banco recebe muito mais leituras do que escritas.",
        "url": "https://example.com/techpulse/demo-sqlite-indexing",
        "source": "dev.to",
        "ai_relevance": "RELEVANTE",
        "hype_score": 3,
        "is_enriched": True,
    },
    {
        "title": "Hooks de lifespan do FastAPI em produção",
        "title_original": "FastAPI Lifespan Hooks in Production",
        "description": "Padrões para inicializar recursos, agendar tarefas em background e encerrar serviços com segurança.",
        "url": "https://example.com/techpulse/demo-fastapi-lifespan",
        "source": "github_trends",
        "ai_relevance": "RELEVANTE",
        "hype_score": 5,
        "is_enriched": True,
    },
    {
        "title": "CEO de startup captura US$ 50M em Série A",
        "title_original": "CEO of tech startup raises 50M dollars in Series A",
        "description": "Notícia corporativa sobre rodada de investimento, sem conteúdo técnico direto para engenharia.",
        "url": "https://example.com/techpulse/demo-ceo-funding",
        "source": "reddit",
        "ai_relevance": "LIXO",
        "hype_score": 2,
        "is_enriched": True,
    },
]


def seed_demo_articles(db: Session) -> dict[str, int]:
    created = 0
    skipped = 0

    for article in DEMO_ARTICLES:
        exists = db.scalar(
            select(NewsItem.id).where(NewsItem.url == article["url"])
        )
        if exists:
            skipped += 1
            continue

        db.add(NewsItem(**article))
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "total": len(DEMO_ARTICLES)}
