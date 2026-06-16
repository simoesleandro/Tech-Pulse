import logging
import os
import re

import requests

from app.services.hype_backfill import resolve_hype_score
from app.services.scrapers.base import EnrichedArticle, RawArticle

logger = logging.getLogger(__name__)

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_URL = os.getenv("OLLAMA_URL", f"{OLLAMA_BASE}/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

SYSTEM_PROMPT = (
    "Você é um editor técnico bilíngue para engenheiros de software brasileiros. "
    "Traduza títulos para português do Brasil, resuma o conteúdo e avalie o hype da "
    "comunidade (0 a 5 estrelas) com base nos sinais de engajamento fornecidos. "
    "Siga o formato de resposta com rigor."
)

ENRICH_PROMPT_TEMPLATE = """Analise o item abaixo.

Título original: {title}
Fonte: {source}
Resumo da fonte: {snippet}

Sinais de engajamento da comunidade:
- Reações positivas (dev.to): {reactions}
- Comentários (dev.to): {comments}
- Stars (GitHub): {stars}
- Upvotes (Reddit): {ups}

O HYPE (0 a 5) deve refletir o burburinho real da comunidade usando os sinais acima.
0 = silêncio total · 3 = discussão moderada · 5 = hype altíssimo na comunidade técnica.

Responda EXATAMENTE neste formato (5 linhas, sem texto extra):
RELEVANCIA: RELEVANTE ou LIXO
TITULO: título traduzido para português do Brasil
DESCRICAO: resumo objetivo em 1 ou 2 frases em português do Brasil
HYPE: número inteiro de 0 a 5
"""

CLASSIFY_ONLY_TEMPLATE = (
    "Analise o título do artigo: '{title}'. "
    "Responda exclusivamente com 'RELEVANTE' se o assunto abordar Engenharia de Software, "
    "IA, Python, DevOps ou Bancos de Dados. "
    "Responda 'LIXO' se for clickbait comercial, vagas de emprego, memes ou notícias corporativas. "
    "Resposta:"
)

_resolved_model: str | None = None
PREFERRED_MODEL_PREFIXES = ("gemma4", "gemma3", "gemma2", "gemma", "llama3", "mistral")


def resolve_ollama_model() -> str:
    global _resolved_model

    if _resolved_model:
        return _resolved_model

    if OLLAMA_MODEL:
        _resolved_model = OLLAMA_MODEL
        return _resolved_model

    try:
        response = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        response.raise_for_status()
        model_names = [item["name"] for item in response.json().get("models", [])]

        for prefix in PREFERRED_MODEL_PREFIXES:
            for name in model_names:
                if name.split(":")[0] == prefix or name.startswith(f"{prefix}:"):
                    _resolved_model = name
                    logger.info("Ollama model auto-detected: %s", name)
                    return name

        if model_names:
            _resolved_model = model_names[0]
            return model_names[0]
    except Exception as exc:
        logger.warning("Could not auto-detect Ollama model: %s", exc)

    _resolved_model = "gemma4:12b"
    return _resolved_model


def _ollama_generate(prompt: str, system: str | None = None) -> str:
    payload = {
        "model": resolve_ollama_model(),
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    response = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json().get("response", "").strip()


def _parse_hype(raw: str, article: RawArticle) -> int:
    hype_match = re.search(r"HYPE:\s*(\d)", raw, re.IGNORECASE)
    parsed = 0
    if hype_match:
        parsed = min(5, max(0, int(hype_match.group(1))))
    return resolve_hype_score(parsed, article)


def _parse_enriched_response(raw: str, article: RawArticle) -> EnrichedArticle:
    relevance_match = re.search(r"RELEVANCIA:\s*(RELEVANTE|LIXO)", raw, re.IGNORECASE)
    title_match = re.search(r"TITULO:\s*(.+)", raw, re.IGNORECASE)
    description_match = re.search(r"DESCRICAO:\s*(.+)", raw, re.IGNORECASE | re.DOTALL)

    relevance = (
        relevance_match.group(1).upper() if relevance_match else "RELEVANTE"
    )
    title_pt = title_match.group(1).strip() if title_match else article.title
    description_pt = (
        description_match.group(1).strip().split("\n")[0] if description_match else ""
    )

    if not description_pt:
        description_pt = "Resumo indisponível no momento."

    return EnrichedArticle(
        ai_relevance=relevance,
        title_pt=title_pt,
        description_pt=description_pt,
        hype_score=_parse_hype(raw, article),
    )


def enrich_article(article: RawArticle) -> EnrichedArticle:
    snippet = article.description_snippet or "Sem resumo disponível na fonte."
    prompt = ENRICH_PROMPT_TEMPLATE.format(
        title=article.title,
        source=article.source,
        snippet=snippet[:500],
        reactions=article.positive_reactions,
        comments=article.comments_count,
        stars=article.stars,
        ups=article.ups,
    )

    raw = _ollama_generate(prompt, system=SYSTEM_PROMPT)
    return _parse_enriched_response(raw, article)


def classify_title(title: str) -> str:
    raw = _ollama_generate(CLASSIFY_ONLY_TEMPLATE.format(title=title), system=SYSTEM_PROMPT)
    if "RELEVANTE" in raw.upper():
        return "RELEVANTE"
    return "LIXO"
