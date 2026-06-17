import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

from app.models import NewsItem
from app.services.obsidian_titles import prettify_note_title
from app.services.article_content import fetch_article_context
from app.services.obsidian_orchestrator import agente_orquestrador_obsidian, fallback_orchestration, folder_display_name, folder_emoji
from app.services.ollama_client import ollama_generate

logger = logging.getLogger(__name__)

ObsidianProgressCallback = Callable[[str, str, str | None], None]


@dataclass(frozen=True)
class ObsidianNoteResult:
    body: str
    note_title: str
    folder: str
    moc: str

OBSIDIAN_SUMMARIZE_SYSTEM = (
    "Você é um analista técnico sênior. Extraia conhecimento denso e concreto de artigos de tecnologia. "
    "Escreva em português do Brasil. Cite tecnologias, padrões, arquiteturas e trade-offs explicitamente."
)

OBSIDIAN_SUMMARIZE_PROMPT = """Analise este material e produza um resumo técnico DETALHADO.

{context}

Estruture em seções com bullets (markdown, NÃO JSON):

## Tese central
- [2-3 bullets com a ideia principal]

## Tecnologias e ferramentas
- [liste cada tech citada com contexto de uso]

## Arquitetura e fluxo
- [como funciona, camadas, componentes]

## Benefícios e trade-offs
- [prós e contras mencionados ou inferíveis]

## Passos práticos / recomendações
- [ações concretas para um dev]

## Termos-chave
- **Termo** — definição curta (mínimo 6 termos)

Mínimo 25 bullets no total. Seja específico — evite frases genéricas.
"""

OBSIDIAN_ANALYZE_SYSTEM = (
    "Você estrutura conhecimento técnico em JSON válido para notas Obsidian. "
    "Responda SOMENTE JSON. Use os bullets do resumo técnico — não seja genérico."
)

OBSIDIAN_ANALYZE_PROMPT = """Com base no resumo técnico abaixo, produza JSON para uma nota de conhecimento Obsidian.

Título: {title}
Fonte: {source}
Hype: {hype}/5

Resumo técnico extraído:
{summary}

JSON obrigatório:
{{
  "tema": "1-2 frases concretas",
  "problema": "dor técnica específica abordada",
  "solucao": "abordagem concreta proposta no artigo",
  "publico": "perfil de dev mais beneficiado",
  "topicos": [
    {{"titulo": "subtópico", "pontos": ["detalhe 1", "detalhe 2", "detalhe 3"]}}
  ],
  "termos": [{{"termo": "Nome", "definicao": "explicação"}}],
  "takeaways": ["insight prático 1", "insight 2", "insight 3"],
  "quando_aplicar": ["cenário 1", "cenário 2"],
  "quando_evitar": ["risco ou limitação 1"],
  "perguntas": ["pergunta de estudo 1", "pergunta 2", "pergunta 3"],
  "wikilinks": ["ConceitoA", "ConceitoB", "ConceitoC", "ConceitoD"]
}}

Regras: 3-5 topicos com 3-4 pontos cada; mínimo 5 termos; mínimo 4 wikilinks CamelCase.
"""

SUMMARIZE_OPTIONS = {"temperature": 0.25, "num_predict": 2048}
ANALYZE_OPTIONS = {"temperature": 0.15, "num_predict": 3072}


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json|markdown|md)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _repair_json(raw: str) -> str:
    text = _strip_code_fences(raw)
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)
    return text


def _parse_analysis(raw: str) -> dict | None:
    candidates = [_strip_code_fences(raw), _repair_json(raw)]
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        candidates.append(json_match.group(0))
        candidates.append(_repair_json(json_match.group(0)))

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("tema") and data.get("topicos"):
            return data
    return None


def _as_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _as_topics(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    topics: list[dict] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("titulo", "")).strip()
        points = _as_list(entry.get("pontos"))
        if title and points:
            topics.append({"titulo": title, "pontos": points[:5]})
    return topics


def _as_terms(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    terms: list[dict] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        term = str(entry.get("termo", "")).strip()
        definition = str(entry.get("definicao", "")).strip()
        if term and definition:
            terms.append({"termo": term, "definicao": definition})
    return terms


def _wikilink_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", name.strip())
    parts = re.split(r"[\s_-]+", cleaned)
    return "".join(part[:1].upper() + part[1:] for part in parts if part)


def _analysis_is_rich(analysis: dict) -> bool:
    topics = _as_topics(analysis.get("topicos"))
    terms = _as_terms(analysis.get("termos"))
    return len(topics) >= 3 and sum(len(t["pontos"]) for t in topics) >= 9 and len(terms) >= 3


def _topics_from_summary(summary: str) -> list[dict]:
    topics: list[dict] = []
    current_title = "Detalhes"
    current_points: list[str] = []

    for line in summary.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_points:
                topics.append({"titulo": current_title, "pontos": current_points[:5]})
            current_title = stripped[3:].strip()
            current_points = []
            continue
        if stripped.startswith(("- ", "* ", "• ")):
            current_points.append(stripped[2:].strip())
        elif stripped.startswith("**") and "—" in stripped:
            current_points.append(stripped)

    if current_points:
        topics.append({"titulo": current_title, "pontos": current_points[:5]})
    return topics[:5]


def _analysis_from_summary(summary: str, item: NewsItem) -> dict:
    topics = _topics_from_summary(summary)
    if len(topics) < 2:
        topics = [
            {
                "titulo": "Análise técnica",
                "pontos": [line.strip("-• ") for line in summary.splitlines() if line.strip().startswith(("-", "*", "•"))][:6],
            }
        ]

    term_lines = [
        line for line in summary.splitlines() if "**" in line and ("—" in line or "-" in line)
    ]
    terms = []
    for line in term_lines[:8]:
        match = re.match(r"\*\*([^*]+)\*\*\s*[—-]\s*(.+)", line.strip("-• "))
        if match:
            terms.append({"termo": match.group(1).strip(), "definicao": match.group(2).strip()})

    first_point = topics[0]["pontos"][0] if topics and topics[0].get("pontos") else item.description
    return {
        "tema": item.description.strip() or item.title,
        "problema": first_point,
        "solucao": topics[1]["pontos"][0] if len(topics) > 1 and topics[1].get("pontos") else first_point,
        "publico": "Engenheiros de software e MLOps",
        "topicos": topics,
        "termos": terms,
        "takeaways": [p for t in topics for p in t["pontos"][:2]][:4],
        "quando_aplicar": ["Ao planejar infraestrutura de IA on-premise ou híbrida"],
        "quando_evitar": ["Quando simplicidade operacional é prioridade sobre controle"],
        "perguntas": ["Quais componentes da stack atual seriam substituídos?", "Qual o custo de migração?"],
        "wikilinks": [t["termo"] for t in terms[:6]] or ["InteligenciaArtificial", "DevOps"],
    }


def render_obsidian_body(item: NewsItem, analysis: dict) -> str:
    note_title = prettify_note_title(
        str(analysis.get("titulo_nota", "")).strip() or item.title
    )
    tema = str(analysis.get("tema", "")).strip() or item.description.strip()
    problema = str(analysis.get("problema", "")).strip()
    solucao = str(analysis.get("solucao", "")).strip()
    publico = str(analysis.get("publico", "")).strip()

    topics = _as_topics(analysis.get("topicos"))
    terms = _as_terms(analysis.get("termos"))
    takeaways = _as_list(analysis.get("takeaways"))
    when_apply = _as_list(analysis.get("quando_aplicar"))
    when_avoid = _as_list(analysis.get("quando_evitar"))
    questions = _as_list(analysis.get("perguntas"))
    wikilinks = [_wikilink_name(name) for name in _as_list(analysis.get("wikilinks"))]
    conexoes = _as_list(analysis.get("conexoes"))
    moc = str(analysis.get("moc", "")).strip()
    folder_slug = str(analysis.get("pasta", "")).strip()
    area_label = str(analysis.get("area_label", "")).strip() or folder_display_name(folder_slug)
    emoji = folder_emoji(folder_slug)
    hype_filled = "★" * item.hype_score
    hype_empty = "☆" * max(0, 5 - item.hype_score)

    heading = f"# {emoji} {note_title}" if emoji else f"# {note_title}"
    lines = [
        heading,
        "",
        f"**{area_label}** · Hype {hype_filled}{hype_empty} ({item.hype_score}/5) · `{item.source}`",
        "",
        "> [!abstract] O que é",
        f"> {tema}",
        "",
    ]

    if problema:
        lines.extend(["> [!question] Problema que aborda", f"> {problema}", ""])
    if solucao:
        lines.extend(["> [!example] Solução / abordagem", f"> {solucao}", ""])
    if publico:
        lines.extend(["> [!note] Público-alvo", f"> {publico}", ""])

    lines.extend(["## Desenvolvimento", ""])
    for topic in topics[:5]:
        lines.append(f"### {topic['titulo']}")
        for point in topic["pontos"]:
            lines.append(f"- {point}")
        lines.append("")

    if terms:
        lines.extend(["## Glossário", "", "| Termo | Significado |", "| --- | --- |"])
        for entry in terms[:10]:
            term = _wikilink_name(entry["termo"])
            lines.append(f"| [[{term}]] | {entry['definicao']} |")
        lines.append("")

    if takeaways:
        lines.extend(["> [!tip] Takeaways práticos", ""])
        for takeaway in takeaways[:6]:
            lines.append(f"> - {takeaway}")
        lines.append("")

    if when_apply:
        lines.extend(["> [!important] Quando aplicar", ""])
        for entry in when_apply[:4]:
            lines.append(f"> - {entry}")
        lines.append("")

    if when_avoid:
        lines.extend(["> [!warning] Quando evitar / riscos", ""])
        for entry in when_avoid[:4]:
            lines.append(f"> - {entry}")
        lines.append("")

    if questions:
        lines.extend(["## Perguntas para aprofundar", ""])
        for question in questions[:6]:
            lines.append(f"- [ ] {question}")
        lines.append("")

    link_entries = wikilinks or [_wikilink_name(t["termo"]) for t in terms[:8]]
    if link_entries:
        lines.extend(["## Conceitos para linkar", ""])
        seen: set[str] = set()
        for name in link_entries:
            if name in seen:
                continue
            seen.add(name)
            lines.append(f"- [[{name}]]")
        lines.append("")

    if conexoes or moc:
        lines.extend(["## Mapa de conhecimento", ""])
        if moc:
            lines.append(f"- Índice da área: [[{moc}]]")
        for link in conexoes[:6]:
            if link.startswith("[[") and link.endswith("]]"):
                lines.append(f"- Relacionado: {link}")
            else:
                lines.append(f"- Relacionado: [[{_wikilink_name(link)}]]")
        lines.append("")

    reasoning = (item.ai_reasoning or "").strip()
    lines.extend(["> [!info] Avaliação Tech-Pulse", f"> **Hype:** {item.hype_score}/5"])
    if reasoning:
        lines.append(f"> {reasoning}")
    lines.extend(["", "---", "", f"[Fonte original]({item.url})", ""])

    return "\n".join(lines)


async def _ollama_with_json_fallback(
    prompt: str,
    system: str,
    options: dict,
) -> str:
    try:
        return await ollama_generate(
            prompt,
            system=system,
            options={**options, "format": "json"},
        )
    except Exception:
        return await ollama_generate(prompt, system=system, options=options)


def _emit(callback: ObsidianProgressCallback | None, step_id: str, status: str, detail: str | None = None) -> None:
    if callback:
        callback(step_id, status, detail)


async def agente_obsidian(
    item: NewsItem,
    on_progress: ObsidianProgressCallback | None = None,
) -> ObsidianNoteResult:
    _emit(on_progress, "fetch", "active", "Buscando artigo na fonte…")
    context, body_chars = fetch_article_context(item)
    if body_chars > 0:
        _emit(on_progress, "fetch", "done", f"{body_chars:,} caracteres do artigo")
    else:
        _emit(on_progress, "fetch", "done", "Usando título e resumo (conteúdo completo indisponível)")

    reasoning = (item.ai_reasoning or "").strip() or "Não avaliado."

    _emit(on_progress, "summarize", "active", "Extraindo pontos técnicos concretos…")
    try:
        summary = await ollama_generate(
            OBSIDIAN_SUMMARIZE_PROMPT.format(context=context),
            system=OBSIDIAN_SUMMARIZE_SYSTEM,
            options=SUMMARIZE_OPTIONS,
        )
        summary = _strip_code_fences(summary)
        _emit(on_progress, "summarize", "done", f"{len(summary.splitlines())} linhas extraídas")
    except Exception as exc:
        logger.warning("[obsidian-agent] summarize failed for %s: %s", item.url, exc)
        summary = context
        _emit(on_progress, "summarize", "done", "Resumo simplificado")

    _emit(on_progress, "analyze", "active", "Estruturando conhecimento em tópicos…")
    analysis: dict | None = None
    analyze_prompt = OBSIDIAN_ANALYZE_PROMPT.format(
        title=item.title,
        source=item.source,
        hype=item.hype_score,
        summary=summary[:6000],
    )

    try:
        for attempt in range(2):
            raw = await _ollama_with_json_fallback(
                analyze_prompt if attempt == 0 else analyze_prompt + "\n\nSeja MAIS específico e técnico. Não repita o título.",
                OBSIDIAN_ANALYZE_SYSTEM,
                ANALYZE_OPTIONS,
            )
            parsed = _parse_analysis(raw)
            if parsed and (attempt == 1 or _analysis_is_rich(parsed)):
                analysis = parsed
                break
            if parsed and analysis is None:
                analysis = parsed
            logger.info("[obsidian-agent] analyze attempt %d for %s", attempt + 1, item.url)

        if analysis and not _analysis_is_rich(analysis):
            logger.info("[obsidian-agent] enriching thin analysis from summary for %s", item.url)
            enriched = _analysis_from_summary(summary, item)
            for key, value in enriched.items():
                if not analysis.get(key) or (isinstance(value, list) and len(value) > len(analysis.get(key, []))):
                    analysis[key] = value

        if analysis:
            _emit(on_progress, "analyze", "done", f"{len(_as_topics(analysis.get('topicos')))} tópicos estruturados")
            _emit(on_progress, "orchestrate", "active", "Organizando título, pasta e links…")
            analysis = await agente_orquestrador_obsidian(item, analysis)
            _emit(
                on_progress,
                "orchestrate",
                "done",
                f"{analysis.get('pasta')} · {analysis.get('titulo_nota', '')[:50]}",
            )
            _emit(on_progress, "render", "active", "Montando nota Obsidian…")
            body = render_obsidian_body(item, analysis)
            _emit(on_progress, "render", "done", f"{len(body):,} caracteres")
            logger.info("[obsidian-agent] %s → nota rica (%d chars)", item.url, len(body))
            return ObsidianNoteResult(
                body=body,
                note_title=prettify_note_title(str(analysis.get("titulo_nota", item.title))),
                folder=str(analysis.get("pasta", "geral")),
                moc=str(analysis.get("moc", "MOC-Tech-Pulse")),
            )

        logger.warning("[obsidian-agent] JSON inválido para %s — usando resumo direto", item.url)
    except Exception as exc:
        logger.warning("[obsidian-agent] analyze failed for %s: %s", item.url, exc)

    _emit(on_progress, "analyze", "done", "Fallback a partir do resumo técnico")
    fallback_analysis = _analysis_from_summary(summary, item)
    _emit(on_progress, "orchestrate", "active", "Organizando título, pasta e links…")
    fallback_analysis = await agente_orquestrador_obsidian(item, fallback_analysis)
    _emit(on_progress, "orchestrate", "done", str(fallback_analysis.get("pasta", "geral")))
    _emit(on_progress, "render", "active", "Montando nota Obsidian…")
    body = render_obsidian_body(item, fallback_analysis)
    _emit(on_progress, "render", "done", f"{len(body):,} caracteres")
    return ObsidianNoteResult(
        body=body,
        note_title=prettify_note_title(str(fallback_analysis.get("titulo_nota", item.title))),
        folder=str(fallback_analysis.get("pasta", "geral")),
        moc=str(fallback_analysis.get("moc", "MOC-Tech-Pulse")),
    )


def fallback_obsidian_body(item: NewsItem) -> ObsidianNoteResult:
    context, _ = fetch_article_context(item)
    analysis = _analysis_from_summary(context, item)
    orchestrated = fallback_orchestration(item, analysis)
    from app.services.obsidian_orchestrator import merge_orchestration

    merged = merge_orchestration(analysis, orchestrated)
    body = render_obsidian_body(item, merged)
    return ObsidianNoteResult(
        body=body,
        note_title=prettify_note_title(str(merged.get("titulo_nota", item.title))),
        folder=str(merged.get("pasta", "geral")),
        moc=str(merged.get("moc", "MOC-Tech-Pulse")),
    )
