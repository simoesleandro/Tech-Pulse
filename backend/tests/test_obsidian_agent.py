import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.models import NewsItem
from app.services.obsidian_agent import agente_obsidian, render_obsidian_body


def _sample_item(**overrides) -> NewsItem:
    defaults = {
        "id": 1,
        "title": "LLM agents",
        "title_original": "LLM agents",
        "description": "Como orquestrar agentes.",
        "url": "https://dev.to/user/llm-agents",
        "source": "dev.to",
        "ai_relevance": "RELEVANTE",
        "hype_score": 4,
        "ai_reasoning": "Utilidade alta.",
        "is_enriched": True,
        "is_read": False,
        "is_bookmarked": False,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return NewsItem(**defaults)


def test_render_obsidian_body_includes_rich_sections():
    analysis = {
        "tema": "Orquestração de agentes LLM.",
        "problema": "Coordenar múltiplos passos com modelos.",
        "solucao": "Padrão planner-executor com filas.",
        "publico": "Engenheiros Python",
        "topicos": [
            {
                "titulo": "Arquitetura",
                "pontos": ["Planner define tarefas", "Executor roda tools", "Memória compartilhada"],
            },
            {
                "titulo": "Stack",
                "pontos": ["Python asyncio", "Ollama local", "Redis para fila"],
            },
            {
                "titulo": "Operação",
                "pontos": ["Logs estruturados", "Retries", "Circuit breaker"],
            },
        ],
        "termos": [
            {"termo": "Agente", "definicao": "Loop LLM + tools"},
            {"termo": "Planner", "definicao": "Decompõe objetivos"},
            {"termo": "Gateway", "definicao": "Roteamento"},
            {"termo": "Queue", "definicao": "Fila de tarefas"},
        ],
        "takeaways": ["Comece com um agente", "Logue cada tool call"],
        "quando_aplicar": ["Workflows repetitivos"],
        "quando_evitar": ["Tarefas determinísticas simples"],
        "perguntas": ["Como versionar prompts?"],
        "wikilinks": ["LLM", "Python", "Ollama"],
        "titulo_nota": "Orquestração de agentes LLM com Python",
        "pasta": "ia-llms",
        "area_label": "IA & LLMs",
        "moc": "MOC-IA-LLMs",
        "conexoes": ["[[RAG]]"],
    }

    body = render_obsidian_body(_sample_item(), analysis)
    assert "> [!abstract] O que é" in body
    assert "## Desenvolvimento" in body
    assert "## Glossário" in body
    assert "[[LLM]]" in body


def test_agente_obsidian_two_phase_pipeline():
    summary = """## Tese central
- Gateway local de IA

## Tecnologias e ferramentas
- Ollama
- Silício local

## Arquitetura e fluxo
- Spec no chip
- Menor latência

## Termos-chave
- **Gateway** — roteamento de modelos
- **Edge** — inferência local
- **Spec** — contrato da API
- **Soberania** — autonomia tecnológica
"""
    analysis = {
        "tema": "Gateway de IA local.",
        "problema": "Dependência de APIs externas.",
        "solucao": "Migrar spec para silício local.",
        "publico": "MLOps",
        "topicos": [
            {"titulo": "Soberania", "pontos": ["Controle local", "Menor latência", "Dados no perímetro"]},
            {"titulo": "Gateway", "pontos": ["Roteamento", "Fallback offline", "Observabilidade"]},
            {"titulo": "Silício", "pontos": ["Spec no chip", "Menos hops", "Custo previsível"]},
        ],
        "termos": [
            {"termo": "Gateway", "definicao": "Camada de roteamento"},
            {"termo": "Edge", "definicao": "Inferência local"},
            {"termo": "Spec", "definicao": "Contrato da API"},
            {"termo": "Soberania", "definicao": "Autonomia tecnológica"},
        ],
        "takeaways": ["Avalie hardware", "Documente contratos", "Teste fallback"],
        "quando_aplicar": ["Dados sensíveis"],
        "quando_evitar": ["Prototipagem rápida"],
        "perguntas": ["Qual chip suporta o modelo?"],
        "wikilinks": ["MLOps", "Gateway", "EdgeAI", "SoberaniaDigital"],
    }

    with patch(
        "app.services.obsidian_agent.fetch_article_context",
        return_value=("Conteúdo completo do artigo.", 4200),
    ), patch(
        "app.services.obsidian_agent.ollama_generate",
        new_callable=AsyncMock,
        side_effect=[summary, json.dumps(analysis)],
    ) as mock_ollama, patch(
        "app.services.obsidian_agent.agente_orquestrador_obsidian",
        new_callable=AsyncMock,
        return_value={
            **analysis,
            "titulo_nota": "Gateway de IA soberano no edge",
            "pasta": "ia-llms",
            "area_label": "IA & LLMs",
            "moc": "MOC-IA-LLMs",
            "conexoes": ["[[MLOps]]"],
            "tags_extra": ["ia-local"],
        },
    ):
        note = asyncio.run(agente_obsidian(_sample_item()))

    assert mock_ollama.call_count == 2
    assert "### Soberania" in note.body
    assert "## Mapa de conhecimento" in note.body
    assert "[[MOC-IA-LLMs]]" in note.body
