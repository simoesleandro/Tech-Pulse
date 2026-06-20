import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import NewsItem
from app.schemas import ObsidianConceptResponse

TECH_KEYWORDS = {
    "python": "Python",
    "rust": "Rust",
    "go": "Go",
    "golang": "Go",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "react": "React",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "sqlite": "SQLite",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "llm": "LLM",
    "gpt": "GPT",
    "openai": "OpenAI",
    "gemma": "Gemma",
    "llama": "Llama",
    "ai": "IA / AI",
    "ia": "IA / AI",
    "devops": "DevOps",
    "git": "Git",
    "github": "GitHub",
    "api": "API",
    "rest": "REST",
    "graphql": "GraphQL",
    "linux": "Linux",
    "tailwind": "Tailwind CSS",
    "css": "CSS",
    "html": "HTML",
    "serverless": "Serverless",
    "security": "Segurança",
    "rustlang": "Rust",
    "ollama": "Ollama",
    "claude": "Claude",
    "deepseek": "DeepSeek",
}


def extract_obsidian_concepts(db: Session, limit: int = 20) -> list[ObsidianConceptResponse]:
    items = db.scalars(
        select(NewsItem)
        .where(NewsItem.obsidian_exported_at.isnot(None))
        .options(joinedload(NewsItem.folder))
    ).all()

    counts: Counter[str] = Counter()
    for item in items:
        text = f"{item.title} {item.title_original or ''} {item.description or ''}"
        tokens = re.split(r"[^\w\.\-]+", text.lower())
        seen_in_item: set[str] = set()

        for token in tokens:
            if token in TECH_KEYWORDS:
                canonical = TECH_KEYWORDS[token]
                if canonical not in seen_in_item:
                    counts[canonical] += 1
                    seen_in_item.add(canonical)

        if item.folder and item.folder.name:
            clean_folder = re.sub(r"[^\w\s&]", "", item.folder.name).strip()
            if clean_folder and clean_folder not in seen_in_item:
                counts[clean_folder] += 1

    return [
        ObsidianConceptResponse(concept=concept, count=count)
        for concept, count in counts.most_common(limit)
    ]


# Padrão para extrair termos capitalizados do ai_reasoning:
# Captura palavras com letra maiúscula (ex: "FastAPI", "PostgreSQL", "tRPC")
# e siglas (ex: "FTS5", "CI/CD", "API")
_REASONING_TERM_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9+#.]{2,}|[A-Z]{2,}[0-9]*)\b"
)

# Termos que aparecem frequentemente mas não são tecnologias
_REASONING_STOPWORDS = frozenset({
    "Com", "Para", "Esse", "Esta", "Este", "Que", "Uma", "Uso", "Novo",
    "API", "URL", "HTTP", "HTML", "JSON", "YAML", "SQL", "OS", "CLI",
    "PR", "CI", "CD", "MVP", "SaaS", "The", "And", "For", "With",
})


def extract_feed_concepts(db: Session, limit: int = 30) -> list[ObsidianConceptResponse]:
    """Extrai conceitos técnicos de TODOS os itens relevantes (não apenas Obsidian).

    Combina TECH_KEYWORDS (para termos conhecidos) com extração de tokens
    capitalizados do ai_reasoning (para tecnologias emergentes não listadas).
    """
    items = db.scalars(
        select(NewsItem)
        .where(NewsItem.ai_relevance == "RELEVANTE")
        .where(NewsItem.is_enriched.is_(True))
    ).all()

    counts: Counter[str] = Counter()

    for item in items:
        seen_in_item: set[str] = set()

        # 1. Extração por TECH_KEYWORDS (mesmo padrão do extract_obsidian_concepts)
        text_lower = f"{item.title} {item.title_original or ''} {item.description or ''}".lower()
        for token in re.split(r"[^\w\.\-]+", text_lower):
            if token in TECH_KEYWORDS:
                canonical = TECH_KEYWORDS[token]
                if canonical not in seen_in_item:
                    counts[canonical] += 1
                    seen_in_item.add(canonical)

        # 2. Extração de termos capitalizados do ai_reasoning
        if item.ai_reasoning:
            for match in _REASONING_TERM_RE.finditer(item.ai_reasoning):
                term = match.group(1)
                if term in _REASONING_STOPWORDS:
                    continue
                # Normaliza: se já temos esse termo via TECH_KEYWORDS, usa o canônico
                canonical = TECH_KEYWORDS.get(term.lower(), term)
                if canonical not in seen_in_item:
                    counts[canonical] += 1
                    seen_in_item.add(canonical)

    return [
        ObsidianConceptResponse(concept=concept, count=count)
        for concept, count in counts.most_common(limit)
    ]
