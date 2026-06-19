import json
import logging
import re

from app.models import NewsItem
from app.services.ollama_client import ollama_generate

logger = logging.getLogger(__name__)

KNOWLEDGE_FOLDERS: dict[str, str] = {
    "ia-llms": "IA & LLMs",
    "python-backend": "Python & Backend",
    "devops-infra": "DevOps & Infra",
    "frontend-web": "Frontend & Web",
    "dados-bancos": "Dados & Bancos",
    "seguranca": "Segurança",
    "carreira": "Carreira & Mercado",
    "produtividade": "Ferramentas & Produtividade",
    "geral": "Geral",
}

# Nomes legíveis no explorer do Obsidian (emoji + rótulo)
FOLDER_DISPLAY: dict[str, str] = {
    "ia-llms": "🤖 IA & LLMs",
    "python-backend": "🐍 Python & Backend",
    "devops-infra": "☁️ DevOps & Infra",
    "frontend-web": "🎨 Frontend & Web",
    "dados-bancos": "🗄️ Dados & Bancos",
    "seguranca": "🔒 Segurança",
    "carreira": "💼 Carreira & Mercado",
    "produtividade": "⚡ Ferramentas & Produtividade",
    "geral": "📚 Geral",
}


def folder_display_name(slug: str) -> str:
    return FOLDER_DISPLAY.get(slug, KNOWLEDGE_FOLDERS.get(slug, slug))


def folder_emoji(slug: str) -> str:
    display = folder_display_name(slug)
    if display and not display[0].isalnum():
        return display.split(" ", 1)[0]
    return ""

ORCHESTRATE_SYSTEM = (
    "Você é um bibliotecário técnico para um vault Obsidian em português do Brasil. "
    "Organize notas com títulos claros, pastas por assunto e wikilinks para grafo de conhecimento. "
    "Responda SOMENTE JSON válido."
)

ORCHESTRATE_PROMPT = """Organize esta nota técnica para o vault Obsidian.

Título atual (feed): {title}
Fonte: {source}
Hype: {hype}/5
Tema: {tema}

Tópicos: {topicos_resumo}
Termos: {termos_resumo}

Pastas permitidas (use exatamente o slug):
- ia-llms — modelos, agentes, RAG, prompt, LLM
- python-backend — Python, APIs, asyncio, frameworks backend
- devops-infra — cloud, K8s, CI/CD, Docker, AWS
- frontend-web — React, Next.js, CSS, UX, browsers
- dados-bancos — SQL, Postgres, Redis, analytics
- seguranca — auth, vulnerabilidades, compliance
- carreira — mercado, entrevistas, soft skills
- produtividade — Obsidian, workflows, tooling pessoal
- geral — não encaixa claramente nas anteriores

JSON obrigatório:
{{
  "titulo_nota": "Título Claro em PT-BR com Espaços (máx. 80 caracteres, capitalização natural)",
  "pasta": "slug da pasta",
  "moc": "MOC-IA-LLMs ou MOC-Python etc. (CamelCase, prefixo MOC-)",
  "wikilinks": ["ConceitoA", "ConceitoB", "ConceitoC", "ConceitoD", "ConceitoE"],
  "conexoes": ["[[ConceitoRelacionado]]", "[[OutroConceito]]"],
  "tags_extra": ["tag1", "tag2"]
}}

Regras:
- titulo_nota deve ser mais informativo que o título do feed
- titulo_nota com palavras separadas por ESPAÇO e capitalização natural (ex: "Deploy do Gemma 12B no AWS EC2")
- NUNCA use kebab-case, snake_case ou tudo minúsculo em titulo_nota
- mínimo 5 wikilinks CamelCase (sem espaços)
- conexoes: 2-4 links wiki para conceitos do grafo, não repetir wikilinks
- tags_extra: 2-4 tags kebab-case em português
"""

ORCHESTRATE_OPTIONS = {"temperature": 0.2, "num_predict": 768}


def _wikilink_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name.strip())
    parts = re.split(r"[\s_-]+", cleaned)
    return "".join(part[:1].upper() + part[1:] for part in parts if part)


def _slug_folder(value: str) -> str:
    slug = re.sub(r"[^\w-]+", "-", value.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug if slug in KNOWLEDGE_FOLDERS else "geral"


def moc_for_folder(folder: str) -> str:
    mapping = {
        "ia-llms": "MOC-IA-LLMs",
        "python-backend": "MOC-Python",
        "devops-infra": "MOC-DevOps",
        "frontend-web": "MOC-Frontend",
        "dados-bancos": "MOC-Dados",
        "seguranca": "MOC-Seguranca",
        "carreira": "MOC-Carreira",
        "produtividade": "MOC-Produtividade",
        "geral": "MOC-Tech-Pulse",
    }
    return mapping.get(folder, "MOC-Tech-Pulse")


def folder_slug_from_moc(moc: str) -> str | None:
    for slug in KNOWLEDGE_FOLDERS:
        if moc_for_folder(slug) == moc.strip():
            return slug
    return None


def folder_slug_from_area_label(label: str) -> str | None:
    cleaned = label.strip()
    for slug, display in FOLDER_DISPLAY.items():
        if display == cleaned:
            return slug
    return None


def infer_folder_from_text(text: str, fallback: str = "geral") -> str:
    combined = text.lower()
    keywords: list[tuple[str, list[str]]] = [
        ("ia-llms", ["llm", "gpt", "agente", "rag", "ollama", "gemma", " ia", "inteligência", "cursor", "openai"]),
        ("python-backend", ["python", "fastapi", "django", "asyncio", "linux"]),
        ("devops-infra", ["docker", "kubernetes", "aws", "devops", "ci/cd", "infra", "gateway"]),
        ("frontend-web", ["react", "next.js", "frontend", "css", "browser", "chrome extension"]),
        ("dados-bancos", ["postgres", "sql", "redis", "banco", "dados"]),
        ("seguranca", ["security", "segurança", "auth", "vulnerab", "falha"]),
        ("carreira", ["carreira", "entrevista", "mercado", "adquire", "bilhões"]),
        ("produtividade", ["obsidian", "produtiv", "workflow", "slay the spire", "self-hosted", "selfhosted"]),
    ]
    for slug, terms in keywords:
        if any(term in combined for term in terms):
            return slug
    return fallback


def _parse_orchestration(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("titulo_nota"):
        return None
    return data


def fallback_orchestration(item: NewsItem, analysis: dict) -> dict:
    tema = str(analysis.get("tema", "")).lower()
    title_lower = item.title.lower()
    combined = f"{tema} {title_lower} {item.description or ''}".lower()

    folder = "geral"
    keywords: list[tuple[str, list[str]]] = [
        ("ia-llms", ["llm", "gpt", "agente", "rag", "ollama", "gemma", "ia ", "inteligência"]),
        ("python-backend", ["python", "fastapi", "django", "asyncio", "api"]),
        ("devops-infra", ["docker", "kubernetes", "aws", "devops", "ci/cd", "infra"]),
        ("frontend-web", ["react", "next.js", "frontend", "css", "browser"]),
        ("dados-bancos", ["postgres", "sql", "redis", "banco", "dados"]),
        ("seguranca", ["security", "segurança", "auth", "vulnerab"]),
        ("carreira", ["carreira", "entrevista", "salário", "mercado"]),
        ("produtividade", ["obsidian", "produtiv", "workflow", "notion"]),
    ]
    for slug, terms in keywords:
        if any(term in combined for term in terms):
            folder = slug
            break

    terms = analysis.get("termos") or []
    wikilinks = [
        _wikilink_name(str(t.get("termo", "")))
        for t in terms[:6]
        if isinstance(t, dict) and t.get("termo")
    ]
    wikilinks.extend(_wikilink_name(w) for w in (analysis.get("wikilinks") or [])[:4])
    seen: set[str] = set()
    unique_links: list[str] = []
    for link in wikilinks:
        if link and link not in seen:
            seen.add(link)
            unique_links.append(link)

    titulo = str(analysis.get("titulo_nota") or item.title).strip()[:80]
    moc = moc_for_folder(folder)

    return {
        "titulo_nota": titulo,
        "pasta": folder,
        "moc": moc,
        "wikilinks": unique_links[:8] or ["TechPulse"],
        "conexoes": [f"[[{unique_links[0]}]]"] if unique_links else [f"[[{moc}]]"],
        "tags_extra": [folder, item.source.replace(".", "-")],
    }


def merge_orchestration(analysis: dict, orchestration: dict) -> dict:
    merged = dict(analysis)
    folder = _slug_folder(str(orchestration.get("pasta", "geral")))
    titulo = str(orchestration.get("titulo_nota", merged.get("titulo_nota") or "")).strip()[:80]

    existing_links = [_wikilink_name(w) for w in (merged.get("wikilinks") or []) if str(w).strip()]
    new_links = [_wikilink_name(w) for w in (orchestration.get("wikilinks") or []) if str(w).strip()]
    seen: set[str] = set()
    wikilinks: list[str] = []
    for name in new_links + existing_links:
        if name and name not in seen:
            seen.add(name)
            wikilinks.append(name)

    conexoes = [str(c).strip() for c in (orchestration.get("conexoes") or []) if str(c).strip()]
    tags_extra = [str(t).strip() for t in (orchestration.get("tags_extra") or []) if str(t).strip()]

    merged.update(
        {
            "titulo_nota": titulo or merged.get("tema", "")[:80],
            "pasta": folder,
            "area_label": folder_display_name(folder),
            "moc": str(orchestration.get("moc") or moc_for_folder(folder)).strip(),
            "wikilinks": wikilinks,
            "conexoes": conexoes,
            "tags_extra": tags_extra,
        }
    )
    return merged


async def agente_orquestrador_obsidian(item: NewsItem, analysis: dict) -> dict:
    topics = analysis.get("topicos") or []
    topic_summary = ", ".join(
        str(t.get("titulo", "")) for t in topics[:5] if isinstance(t, dict)
    )[:300]
    terms = analysis.get("termos") or []
    term_summary = ", ".join(
        str(t.get("termo", "")) for t in terms[:8] if isinstance(t, dict)
    )[:300]

    prompt = ORCHESTRATE_PROMPT.format(
        title=item.title,
        source=item.source,
        hype=item.hype_score,
        tema=str(analysis.get("tema", ""))[:400],
        topicos_resumo=topic_summary or "n/d",
        termos_resumo=term_summary or "n/d",
    )

    try:
        raw = await ollama_generate(
            prompt,
            system=ORCHESTRATE_SYSTEM,
            options={**ORCHESTRATE_OPTIONS, "format": "json"},
            step_name="orchestrate",
        )
        parsed = _parse_orchestration(raw)
        if parsed:
            return merge_orchestration(analysis, parsed)
    except Exception as exc:
        logger.warning("[obsidian-orchestrator] LLM failed for %s: %s", item.url, exc)

    return merge_orchestration(analysis, fallback_orchestration(item, analysis))
