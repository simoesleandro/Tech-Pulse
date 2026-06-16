import asyncio
import json
import logging
import re
from collections.abc import Callable

from app.services.hype_backfill import resolve_hype_score
from app.services.ollama_client import ollama_generate
from app.services.scrapers.base import EnrichedArticle, RawArticle

logger = logging.getLogger(__name__)

TRIADOR_SYSTEM = (
    "Você é um firewall cognitivo para um feed de engenharia de software. "
    "Julgue estritamente se o conteúdo pertence ao escopo técnico. "
    "Responda apenas RELEVANTE ou LIXO."
)

TRIADOR_PROMPT = """Analise o item abaixo.

Título: {title}
Descrição/resumo: {snippet}
Fonte: {source}

O assunto pertence a Engenharia de Software, Python, IA/LLMs, Infraestrutura/DevOps ou Bancos de Dados?

Responda EXATAMENTE com uma palavra: RELEVANTE ou LIXO
"""

TRADUTOR_SYSTEM = (
    "Você é um editor técnico bilíngue para desenvolvedores brasileiros. "
    "Traduza títulos para português do Brasil e escreva resumos cirúrgicos."
)

TRADUTOR_PROMPT = """Traduza e resuma o item técnico abaixo.

Título original: {title}
Descrição original: {snippet}

Responda EXATAMENTE neste formato JSON (sem markdown):
{{"titulo_pt": "título em português do Brasil", "descricao_pt": "resumo objetivo em 1 ou 2 frases em português do Brasil"}}
"""

HYPE_SYSTEM = (
    "Você avalia o impacto técnico de notícias para desenvolvedores de 0 a 5 estrelas. "
    "Considere a fonte e o engajamento da comunidade."
)

SOURCE_WEIGHT_HINTS = {
    "hacker_news": "Hacker News costuma trazer discussões densas e alto impacto.",
    "github_trends": "GitHub Trends reflete adoção real via stars.",
    "dev.to": "dev.to mede hype via reações e comentários da comunidade.",
    "reddit": "Reddit mede burburinho via upvotes e comentários.",
}

HYPE_PROMPT = """Avalie o hype/impacto técnico desta matéria para desenvolvedores.

Título (PT-BR): {title_pt}
Fonte: {source}
Contexto da fonte: {source_hint}

Sinais de engajamento:
- Reações (dev.to): {reactions}
- Comentários: {comments}
- Stars (GitHub): {stars}
- Upvotes (Reddit/HN): {ups}

Responda EXATAMENTE neste formato (uma linha):
HYPE: número inteiro de 0 a 5
"""


def _parse_relevance(raw: str) -> str:
    upper = raw.upper()
    if "LIXO" in upper and "RELEVANTE" not in upper:
        return "LIXO"
    if "RELEVANTE" in upper:
        return "RELEVANTE"
    return "LIXO"


def _parse_tradutor_response(raw: str, article: RawArticle) -> tuple[str, str]:
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            title_pt = str(data.get("titulo_pt", "")).strip()
            desc_pt = str(data.get("descricao_pt", "")).strip()
            if title_pt and desc_pt:
                return title_pt, desc_pt
        except json.JSONDecodeError:
            pass

    title_match = re.search(r"TITULO:\s*(.+)", raw, re.IGNORECASE)
    desc_match = re.search(r"DESCRICAO:\s*(.+)", raw, re.IGNORECASE | re.DOTALL)
    title_pt = title_match.group(1).strip() if title_match else article.title
    desc_pt = (
        desc_match.group(1).strip().split("\n")[0]
        if desc_match
        else (article.description_snippet or "Resumo indisponível no momento.")
    )
    return title_pt, desc_pt


def _parse_hype(raw: str, article: RawArticle) -> int:
    hype_match = re.search(r"HYPE:\s*(\d)", raw, re.IGNORECASE)
    parsed = 0
    if hype_match:
        parsed = min(5, max(0, int(hype_match.group(1))))
    return resolve_hype_score(parsed, article)


async def agente_triador(article: RawArticle) -> str:
    snippet = article.description_snippet or "Sem descrição disponível."
    prompt = TRIADOR_PROMPT.format(
        title=article.title,
        snippet=snippet[:500],
        source=article.source,
    )
    raw = await ollama_generate(prompt, system=TRIADOR_SYSTEM)
    relevance = _parse_relevance(raw)
    logger.info("[triador] %s → %s", article.url, relevance)
    return relevance


async def agente_tradutor(article: RawArticle) -> tuple[str, str]:
    snippet = article.description_snippet or "Sem descrição disponível."
    prompt = TRADUTOR_PROMPT.format(title=article.title, snippet=snippet[:500])
    raw = await ollama_generate(prompt, system=TRADUTOR_SYSTEM)
    title_pt, desc_pt = _parse_tradutor_response(raw, article)
    logger.info("[tradutor] %s → título traduzido", article.url)
    return title_pt, desc_pt


async def agente_hype(article: RawArticle, title_pt: str) -> int:
    source_hint = SOURCE_WEIGHT_HINTS.get(article.source, "Avalie o impacto técnico geral.")
    prompt = HYPE_PROMPT.format(
        title_pt=title_pt,
        source=article.source,
        source_hint=source_hint,
        reactions=article.positive_reactions,
        comments=article.comments_count,
        stars=article.stars,
        ups=article.ups,
    )
    raw = await ollama_generate(prompt, system=HYPE_SYSTEM)
    hype = _parse_hype(raw, article)
    logger.info("[hype] %s → %s estrelas", article.url, hype)
    return hype


AgentProgressCallback = Callable[[str, str, str | None], None]


async def orquestrador_enriquecimento(
    article: RawArticle,
    on_agent_progress: AgentProgressCallback | None = None,
) -> EnrichedArticle:
    def emit(step_id: str, status: str, detail: str | None = None) -> None:
        if on_agent_progress:
            on_agent_progress(step_id, status, detail)

    emit("triador", "active", article.title[:80])
    relevance = await agente_triador(article)
    emit("triador", "done", relevance)

    if relevance == "LIXO":
        logger.info("[orquestrador] %s barrado no triador — pulando tradutor/hype", article.url)
        return EnrichedArticle(
            ai_relevance="LIXO",
            title_pt=article.title,
            description_pt=article.description_snippet or "Conteúdo fora do escopo técnico.",
            hype_score=0,
        )

    emit("tradutor", "active", article.title[:80])
    title_pt, desc_pt = await agente_tradutor(article)
    emit("tradutor", "done", title_pt[:80])

    emit("hype", "active", title_pt[:80])
    hype_score = await agente_hype(article, title_pt)
    emit("hype", "done", f"{hype_score} estrelas")

    return EnrichedArticle(
        ai_relevance="RELEVANTE",
        title_pt=title_pt,
        description_pt=desc_pt,
        hype_score=hype_score,
    )


def enrich_article_sync(
    article: RawArticle,
    on_agent_progress: AgentProgressCallback | None = None,
) -> EnrichedArticle:
    return asyncio.run(orquestrador_enriquecimento(article, on_agent_progress))
