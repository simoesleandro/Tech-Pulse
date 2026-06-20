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

HYPE_OPTIONS = {"temperature": 0.15, "num_predict": 1024}

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


UNIFIED_SYSTEM = (
    "Você é um engenheiro de software sênior e editor técnico bilingue.\n"
    "Sua tarefa é analisar uma notícia tecnológica sob três aspectos combinados:\n"
    "1. Triagem: Avaliar se o assunto pertence estritamente ao escopo técnico (Engenharia de Software, Python, IA/LLMs, Infraestrutura/DevOps ou Bancos de Dados). Se não pertencer a nenhuma dessas áreas, classifique como LIXO.\n"
    "2. Tradução: Se for RELEVANTE, traduza o título para português do Brasil de forma profissional e faça um resumo curto e objetivo (1 a 2 frases) em português do Brasil.\n"
    "3. Hype/Impacto: Se for RELEVANTE, avalie o impacto técnico para desenvolvedores na escala de 0 a 5 estrelas. Avalie também as dimensões novelty, practicality e community_signal (0 a 5 cada), e forneça uma breve justificativa em português.\n\n"
    "Responda EXATAMENTE no seguinte formato JSON (sem markdown, sem tags html):\n"
    "{\n"
    '  "relevance": "RELEVANTE" ou "LIXO",\n'
    '  "titulo_pt": "Título traduzido (ou string vazia se LIXO)",\n'
    '  "descricao_pt": "Resumo em português (ou string vazia se LIXO)",\n'
    '  "hype": número de 0 a 5,\n'
    '  "novelty": número de 0 a 5,\n'
    '  "practicality": número de 0 a 5,\n'
    '  "community_signal": número de 0 a 5,\n'
    '  "reasoning": "Breve justificativa técnica em português (ou string vazia se LIXO)"\n'
    "}"
)

UNIFIED_PROMPT = """Analise o item abaixo para triagem, tradução e avaliação de hype.

Título original: {title}
Descrição original: {snippet}
Fonte: {source}
Sinais brutos de engajamento da fonte:
- Reações: {reactions}
- Comentários: {comments}
- Stars: {stars}
- Upvotes: {ups}
- Score de engajamento pré-calculado: {engagement_score}

Responda rigorosamente com o formato JSON solicitado.
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


def _infer_hype_dims(hype: int) -> tuple[int, int, int]:
    clamped = min(5, max(0, hype))
    novelty = clamped
    practicality = min(5, max(0, clamped - 1)) if clamped > 0 else 0
    community_signal = clamped
    return novelty, practicality, community_signal


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
            if novelty is None or practicality is None or community_signal is None:
                inferred = _infer_hype_dims(hype)
                novelty = novelty if novelty is not None else inferred[0]
                practicality = practicality if practicality is not None else inferred[1]
                community_signal = (
                    community_signal if community_signal is not None else inferred[2]
                )
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

    hype_match = re.search(r'"?hype"?\s*[:=]\s*(\d)', raw, re.IGNORECASE)
    if not hype_match:
        hype_match = re.search(r"HYPE:\s*(\d)", raw, re.IGNORECASE)
    parsed = min(5, max(0, int(hype_match.group(1)))) if hype_match else 3
    novelty, practicality, community_signal = _infer_hype_dims(parsed)
    reasoning = _format_hype_reasoning(
        reasoning="Resposta do modelo sem JSON válido; dimensões estimadas pela nota.",
        novelty=novelty,
        practicality=practicality,
        community_signal=community_signal,
    )
    return HypeAssessment(
        hype=parsed,
        reasoning=reasoning,
        novelty=novelty,
        practicality=practicality,
        community_signal=community_signal,
    )


async def agente_triador(article: RawArticle) -> str:
    snippet = article.description_snippet or "Sem descrição disponível."
    prompt = TRIADOR_PROMPT.format(
        title=article.title,
        snippet=snippet[:500],
        source=article.source,
    )
    raw = await ollama_generate(prompt, system=TRIADOR_SYSTEM, step_name="triador")
    relevance = _parse_relevance(raw)
    logger.info("[triador] %s → %s", article.url, relevance)
    return relevance


async def agente_tradutor(article: RawArticle) -> tuple[str, str]:
    snippet = article.description_snippet or "Sem descrição disponível."
    prompt = TRADUTOR_PROMPT.format(title=article.title, snippet=snippet[:500])
    raw = await ollama_generate(prompt, system=TRADUTOR_SYSTEM, step_name="tradutor")
    title_pt, desc_pt = _parse_tradutor_response(raw, article)
    if article.source == "github_trends":
        from app.services.obsidian_titles import prettify_github_title
        title_pt = prettify_github_title(title_pt)
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
    raw = await ollama_generate(prompt, system=HYPE_SYSTEM, options=HYPE_OPTIONS, step_name="hype")
    assessment = _parse_hype_response(raw)
    logger.info("[hype] %s → %s estrelas — %s", article.url, assessment.hype, assessment.reasoning)
    return assessment


AgentProgressCallback = Callable[[str, str, str | None], None]


async def agente_unificado(article: RawArticle) -> EnrichedArticle:
    snippet = article.description_snippet or "Sem descrição disponível."
    engagement_score = compute_hype_score(article)
    prompt = UNIFIED_PROMPT.format(
        title=article.title,
        snippet=snippet[:500],
        source=article.source,
        reactions=article.positive_reactions,
        comments=article.comments_count,
        stars=article.stars,
        ups=article.ups,
        engagement_score=engagement_score,
    )
    raw = await ollama_generate(prompt, system=UNIFIED_SYSTEM, options=HYPE_OPTIONS, step_name="unified")

    relevance = "LIXO"
    title_pt = article.title
    desc_pt = snippet
    hype = 0
    novelty = 0
    practicality = 0
    community_signal = 0
    reasoning = None

    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            relevance = _parse_relevance(str(data.get("relevance", "LIXO")))
            if relevance == "RELEVANTE":
                title_pt = str(data.get("titulo_pt", "")).strip() or article.title
                desc_pt = str(data.get("descricao_pt", "")).strip() or snippet

                if article.source == "github_trends":
                    from app.services.obsidian_titles import prettify_github_title
                    title_pt = prettify_github_title(title_pt)

                hype = _clamp_score(data.get("hype", 0), default=0) or 0
                novelty = _clamp_score(data.get("novelty"))
                practicality = _clamp_score(data.get("practicality"))
                community_signal = _clamp_score(data.get("community_signal"))

                if novelty is None or practicality is None or community_signal is None:
                    inferred = _infer_hype_dims(hype)
                    novelty = novelty if novelty is not None else inferred[0]
                    practicality = practicality if practicality is not None else inferred[1]
                    community_signal = community_signal if community_signal is not None else inferred[2]

                reasoning = _format_hype_reasoning(
                    reasoning=str(data.get("reasoning", "")).strip(),
                    novelty=novelty,
                    practicality=practicality,
                    community_signal=community_signal,
                )
            else:
                desc_pt = "Conteúdo fora do escopo técnico."
        except Exception as exc:
            logger.warning("Erro ao decodificar JSON do agente_unificado: %s. Resposta: %s", exc, raw)
            relevance = "LIXO"
            desc_pt = "Falha no parse do agente unificado."
    else:
        logger.warning("Nenhum JSON encontrado na resposta do agente_unificado: %s", raw)
        if "RELEVANTE" in raw.upper():
            relevance = "RELEVANTE"
            title_pt = article.title
            desc_pt = snippet
            hype = 3
            novelty, practicality, community_signal = _infer_hype_dims(hype)
            reasoning = _format_hype_reasoning(
                reasoning="Analise unificada incompleta (formato inválido).",
                novelty=novelty,
                practicality=practicality,
                community_signal=community_signal,
            )
        else:
            relevance = "LIXO"
            desc_pt = "Conteúdo fora do escopo técnico."

    logger.info("[unified] %s → %s", article.url, relevance)
    return EnrichedArticle(
        ai_relevance=relevance,
        title_pt=title_pt,
        description_pt=desc_pt,
        hype_score=hype,
        ai_reasoning=reasoning,
    )


AgentProgressCallback = Callable[[str, str, str | None], None]


async def orquestrador_enriquecimento(
    article: RawArticle,
    on_agent_progress: AgentProgressCallback | None = None,
    *,
    skip_triador: bool = False,
) -> EnrichedArticle:
    def emit(step_id: str, status: str, detail: str | None = None) -> None:
        if on_agent_progress:
            on_agent_progress(step_id, status, detail)

    from app.services.settings import load_settings
    settings = load_settings()
    pipeline_mode = settings.get("pipeline_mode", "unified")

    from app.services.ingest import _is_cancelled
    if _is_cancelled():
        raise InterruptedError("Ingestão cancelada — conexão encerrada.")

    # GitHub Trends queries pre-filter by topic/language — triador adds no signal
    if pipeline_mode != "unified" and article.source == "github_trends":
        skip_triador = True

    if pipeline_mode == "unified" and not skip_triador:
        emit("unified", "active", article.title[:80])
        enriched = await agente_unificado(article)

        if enriched.ai_relevance == "LIXO":
            emit("unified", "done", f"LIXO — {article.title[:40]}")
        else:
            emit("unified", "done", f"RELEVANTE (Hype {enriched.hype_score}/5) — {enriched.title_pt[:40]}")

        return enriched

    if skip_triador:
        relevance = "RELEVANTE"
        emit("triador", "done", "RELEVANTE (pré-classificado)")
    else:
        if _is_cancelled():
            raise InterruptedError("Ingestão cancelada — conexão encerrada.")
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

    if _is_cancelled():
        raise InterruptedError("Ingestão cancelada — conexão encerrada.")
    emit("tradutor", "active", article.title[:80])
    title_pt, desc_pt = await agente_tradutor(article)
    emit("tradutor", "done", title_pt[:80])

    if _is_cancelled():
        raise InterruptedError("Ingestão cancelada — conexão encerrada.")
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
    on_agent_progress_factory: Callable[[int, int, str], AgentProgressCallback] | None = None,
    *,
    skip_triador: bool = False,
) -> list[tuple[int, RawArticle, EnrichedArticle | Exception]]:
    total = len(articles)

    async def enrich_one(index: int, article: RawArticle) -> tuple[int, RawArticle, EnrichedArticle | Exception]:
        callback = (
            on_agent_progress_factory(index, total, article.title)
            if on_agent_progress_factory
            else None
        )
        try:
            enriched = await orquestrador_enriquecimento(
                article, callback, skip_triador=skip_triador
            )
            return index, article, enriched
        except Exception as exc:
            return index, article, exc

    results = await asyncio.gather(
        *[enrich_one(index, article) for index, article in enumerate(articles, start=1)]
    )
    return list(results)


async def enrich_articles_as_completed(
    articles: list[RawArticle],
    on_agent_progress_factory: Callable[[int, int, str], AgentProgressCallback] | None = None,
    *,
    skip_triador: bool = False,
):
    from app.services.ingest import _is_cancelled
    from app.services.ollama_client import OLLAMA_CONCURRENCY, unload_ollama_model

    total = len(articles)
    if total == 0:
        return

    semaphore = asyncio.Semaphore(OLLAMA_CONCURRENCY)
    article_iter = iter(list(enumerate(articles, start=1)))
    in_flight: set[asyncio.Task] = set()

    async def enrich_one(
        index: int, article: RawArticle
    ) -> tuple[int, RawArticle, EnrichedArticle | Exception]:
        callback = (
            on_agent_progress_factory(index, total, article.title)
            if on_agent_progress_factory
            else None
        )
        async with semaphore:
            if _is_cancelled():
                raise InterruptedError("Ingestão cancelada — conexão encerrada.")
            try:
                enriched = await orquestrador_enriquecimento(
                    article, callback, skip_triador=skip_triador
                )
                return index, article, enriched
            except InterruptedError:
                raise
            except Exception as exc:
                return index, article, exc

    def schedule_next() -> None:
        if _is_cancelled():
            return
        try:
            index, article = next(article_iter)
        except StopIteration:
            return
        task = asyncio.create_task(enrich_one(index, article))
        in_flight.add(task)

    for _ in range(min(OLLAMA_CONCURRENCY, total)):
        schedule_next()

    try:
        while in_flight:
            done, _ = await asyncio.wait(
                in_flight, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                in_flight.discard(task)
                yield await task
                schedule_next()
            if _is_cancelled():
                break
    finally:
        for task in in_flight:
            task.cancel()
        if in_flight:
            await asyncio.gather(*in_flight, return_exceptions=True)
        if _is_cancelled():
            await unload_ollama_model()
            raise InterruptedError("Ingestão cancelada — conexão encerrada.")


def enrich_article_sync(
    article: RawArticle,
    on_agent_progress: AgentProgressCallback | None = None,
    *,
    skip_triador: bool = False,
) -> EnrichedArticle:
    return asyncio.run(
        orquestrador_enriquecimento(
            article, on_agent_progress, skip_triador=skip_triador
        )
    )
