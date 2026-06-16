import asyncio
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

from app.services.hype import compute_hype_score
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
    "Use TODA a escala: 0 = irrelevante, 1 = muito baixo, 2 = nicho, 3 = moderado, "
    "4 = alto impacto, 5 = disruptivo. Evite polarizar só em 1 ou 5.\n\n"
    "Antes da nota final, avalie três dimensões (0-5 cada):\n"
    "- novelty: quão novo ou inédito é o tema\n"
    "- practicality: utilidade prática para o dia a dia de um dev\n"
    "- community_signal: força do engajamento/buzz na comunidade\n\n"
    "Exemplos calibrados:\n"
    "1) 'Fix typo in README' → hype 1, novelty 0, practicality 1, community_signal 1\n"
    "2) 'Guia completo de asyncio em Python' → hype 3, novelty 2, practicality 4, community_signal 3\n"
    "3) 'OpenAI lança modelo open-source rival ao GPT-4' → hype 5, novelty 5, practicality 4, community_signal 5"
)

HYPE_OPTIONS = {"temperature": 0.15, "num_predict": 256}

SOURCE_WEIGHT_HINTS = {
    "hacker_news": "Hacker News costuma trazer discussões densas e alto impacto.",
    "github_trends": "GitHub Trends reflete adoção real via stars.",
    "dev.to": "dev.to mede hype via reações e comentários da comunidade.",
    "reddit": "Reddit mede burburinho via upvotes e comentários.",
}

HYPE_PROMPT = """Avalie o hype/impacto técnico desta matéria para desenvolvedores.

Título (PT-BR): {title_pt}
Resumo (PT-BR): {desc_pt}
Título original: {title_original}
Resumo original: {snippet}
Fonte: {source}
Contexto da fonte: {source_hint}

Sinais brutos de engajamento:
- Reações (dev.to): {reactions}
- Comentários: {comments}
- Stars (GitHub): {stars}
- Upvotes (Reddit/HN): {ups}

Score de engajamento pré-calculado (0-5, use como âncora para community_signal): {engagement_score}

Escala obrigatória (use valores intermediários quando couber):
0 = sem impacto · 1 = muito baixo · 2 = nicho · 3 = moderado · 4 = alto · 5 = disruptivo

Responda EXATAMENTE neste JSON (sem markdown):
{{"hype": inteiro 0-5, "novelty": inteiro 0-5, "practicality": inteiro 0-5, "community_signal": inteiro 0-5, "reasoning": "1-2 frases em português explicando a nota"}}
"""


@dataclass(frozen=True)
class HypeAssessment:
    hype: int
    reasoning: str
    novelty: int | None = None
    practicality: int | None = None
    community_signal: int | None = None


def _clamp_score(value: object, default: int | None = None) -> int | None:
    try:
        return min(5, max(0, int(value)))
    except (TypeError, ValueError):
        return default


def _format_hype_reasoning(
    *,
    reasoning: str,
    novelty: int | None = None,
    practicality: int | None = None,
    community_signal: int | None = None,
) -> str:
    dims: list[str] = []
    if novelty is not None:
        dims.append(f"Novidade {novelty}")
    if practicality is not None:
        dims.append(f"Utilidade {practicality}")
    if community_signal is not None:
        dims.append(f"Comunidade {community_signal}")

    summary = reasoning.strip()
    if dims and summary:
        return f"{' · '.join(dims)} — {summary}"
    if dims:
        return " · ".join(dims)
    return summary or "Impacto técnico avaliado pelo analista de hype."


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


def _parse_hype_response(raw: str) -> HypeAssessment:
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            hype = _clamp_score(data.get("hype", 0), default=0) or 0
            novelty = _clamp_score(data.get("novelty"))
            practicality = _clamp_score(data.get("practicality"))
            community_signal = _clamp_score(data.get("community_signal"))
            reasoning = _format_hype_reasoning(
                reasoning=str(data.get("reasoning", "")).strip(),
                novelty=novelty,
                practicality=practicality,
                community_signal=community_signal,
            )
            return HypeAssessment(
                hype=hype,
                reasoning=reasoning,
                novelty=novelty,
                practicality=practicality,
                community_signal=community_signal,
            )
        except json.JSONDecodeError:
            pass

    hype_match = re.search(r"HYPE:\s*(\d)", raw, re.IGNORECASE)
    parsed = min(5, max(0, int(hype_match.group(1)))) if hype_match else 0
    return HypeAssessment(
        hype=parsed,
        reasoning="Classificação legada sem justificativa detalhada.",
    )


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


async def agente_hype(
    article: RawArticle,
    title_pt: str,
    desc_pt: str,
) -> HypeAssessment:
    source_hint = SOURCE_WEIGHT_HINTS.get(article.source, "Avalie o impacto técnico geral.")
    snippet = article.description_snippet or "Sem descrição disponível."
    engagement_score = compute_hype_score(article)
    prompt = HYPE_PROMPT.format(
        title_pt=title_pt,
        desc_pt=desc_pt[:600],
        title_original=article.title[:200],
        snippet=snippet[:500],
        source=article.source,
        source_hint=source_hint,
        reactions=article.positive_reactions,
        comments=article.comments_count,
        stars=article.stars,
        ups=article.ups,
        engagement_score=engagement_score,
    )
    raw = await ollama_generate(prompt, system=HYPE_SYSTEM, options=HYPE_OPTIONS)
    assessment = _parse_hype_response(raw)
    logger.info("[hype] %s → %s estrelas — %s", article.url, assessment.hype, assessment.reasoning)
    return assessment


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
            ai_reasoning=None,
        )

    emit("tradutor", "active", article.title[:80])
    title_pt, desc_pt = await agente_tradutor(article)
    emit("tradutor", "done", title_pt[:80])

    emit("hype", "active", title_pt[:80])
    assessment = await agente_hype(article, title_pt, desc_pt)
    emit("hype", "done", f"{assessment.hype} estrelas")

    return EnrichedArticle(
        ai_relevance="RELEVANTE",
        title_pt=title_pt,
        description_pt=desc_pt,
        hype_score=assessment.hype,
        ai_reasoning=assessment.reasoning,
    )


async def enrich_articles_parallel(
    articles: list[RawArticle],
    on_agent_progress_factory: Callable[[int, int], AgentProgressCallback] | None = None,
) -> list[tuple[int, RawArticle, EnrichedArticle | Exception]]:
    total = len(articles)

    async def enrich_one(index: int, article: RawArticle) -> tuple[int, RawArticle, EnrichedArticle | Exception]:
        callback = (
            on_agent_progress_factory(index, total)
            if on_agent_progress_factory
            else None
        )
        try:
            enriched = await orquestrador_enriquecimento(article, callback)
            return index, article, enriched
        except Exception as exc:
            return index, article, exc

    results = await asyncio.gather(
        *[enrich_one(index, article) for index, article in enumerate(articles, start=1)]
    )
    return list(results)


async def enrich_articles_as_completed(
    articles: list[RawArticle],
    on_agent_progress_factory: Callable[[int, int], AgentProgressCallback] | None = None,
):
    total = len(articles)

    async def enrich_one(index: int, article: RawArticle) -> tuple[int, RawArticle, EnrichedArticle | Exception]:
        callback = (
            on_agent_progress_factory(index, total)
            if on_agent_progress_factory
            else None
        )
        try:
            enriched = await orquestrador_enriquecimento(article, callback)
            return index, article, enriched
        except Exception as exc:
            return index, article, exc

    tasks = [
        asyncio.create_task(enrich_one(index, article))
        for index, article in enumerate(articles, start=1)
    ]

    for task in asyncio.as_completed(tasks):
        yield await task


def enrich_article_sync(
    article: RawArticle,
    on_agent_progress: AgentProgressCallback | None = None,
) -> EnrichedArticle:
    return asyncio.run(orquestrador_enriquecimento(article, on_agent_progress))
