import datetime
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import NewsItem
from app.services.obsidian_titles import humanize_filename
from app.services.obsidian import write_file_to_obsidian, get_obsidian_config

logger = logging.getLogger(__name__)

def generate_weekly_digest(db: Session) -> str:
    """
    Gera um Digest Semanal com os top 5 artigos de maior hype da semana (últimos 7 dias),
    e lista todos os demais artigos relevantes da semana agrupados por área técnica.
    Grava o arquivo resultante na pasta '📚 Índices/Digest-YYYY-MM-DD.md' do Obsidian Vault.
    """
    # 1. Config check
    config = get_obsidian_config()
    if not config["configured"]:
        raise RuntimeError("Obsidian não está configurado no .env")

    # 2. Date query: last 7 days (UTC)
    today = datetime.datetime.now(datetime.timezone.utc)
    seven_days_ago = today - datetime.timedelta(days=7)

    # 3. Get Top 5 by hype
    top_query = (
        select(NewsItem)
        .where(NewsItem.created_at >= seven_days_ago)
        .where(NewsItem.ai_relevance == "RELEVANTE")
        .order_by(NewsItem.hype_score.desc(), NewsItem.created_at.desc())
        .limit(5)
    )
    top_items = db.scalars(top_query).all()

    # 4. Get all relevant items in the last 7 days grouped by area (folder)
    all_query = (
        select(NewsItem)
        .where(NewsItem.created_at >= seven_days_ago)
        .where(NewsItem.ai_relevance == "RELEVANTE")
        .order_by(NewsItem.hype_score.desc(), NewsItem.created_at.desc())
    )
    all_items = db.scalars(all_query).all()

    # Group by folder
    from collections import defaultdict
    grouped = defaultdict(list)
    for item in all_items:
        folder_name = item.folder.name if item.folder else "Geral / Sem Pasta"
        grouped[folder_name].append(item)

    # 5. Build markdown content
    date_str = today.strftime("%Y-%m-%d")
    md = []
    md.append(f"# Tech-Pulse — Digest Semanal ({date_str})")
    md.append(f"Resumo semanal curado pelo **Tech-Pulse** em {today.strftime('%d/%m/%Y %H:%M')} (UTC).")
    md.append("")
    md.append("## 🏆 Top 5 Hype da Semana")
    md.append("")

    if not top_items:
        md.append("*Nenhum artigo relevante encontrado nos últimos 7 dias.*")
    else:
        for idx, item in enumerate(top_items, start=1):
            stars = "★" * item.hype_score + "☆" * (5 - item.hype_score)
            source_label = item.source.replace("rss/", "RSS: ")
            
            if item.obsidian_exported_at:
                note_name = f"{item.id} - {humanize_filename(item.title)}"
                link = f"[[{note_name}|{item.title}]]"
            else:
                link = f"[{item.title}]({item.url})"
                
            md.append(f"{idx}. {link} ({stars})")
            md.append(f"   - **Fonte**: `{source_label}`")
            if item.ai_reasoning:
                # Obter apenas a explicação (tirando as dimensões se presentes)
                parts = item.ai_reasoning.split(" — ")
                explanation = parts[1] if len(parts) > 1 else item.ai_reasoning
                md.append(f"   - **Análise**: *{explanation}*")
            md.append("")

    md.append("## 📚 Artigos da Semana por Área")
    md.append("")

    if not grouped:
        md.append("*Nenhum artigo classificado nesta semana.*")
    else:
        # Ordenar pastas, jogando "Geral / Sem Pasta" para o fim se existir
        sorted_folders = sorted([k for k in grouped.keys() if k != "Geral / Sem Pasta"])
        if "Geral / Sem Pasta" in grouped:
            sorted_folders.append("Geral / Sem Pasta")
            
        for folder_name in sorted_folders:
            md.append(f"### {folder_name}")
            md.append("")
            for item in grouped[folder_name]:
                stars = "★" * item.hype_score
                
                if item.obsidian_exported_at:
                    note_name = f"{item.id} - {humanize_filename(item.title)}"
                    link = f"[[{note_name}|{item.title}]]"
                else:
                    link = f"[{item.title}]({item.url})"
                
                md.append(f"- {link} ({stars}) — `{item.source}`")
            md.append("")

    content = "\n".join(md)

    # 6. Write to Obsidian
    relative_path = f"📚 Índices/Digest-{date_str}.md"
    write_file_to_obsidian(relative_path, content)

    logger.info("Weekly digest created successfully at %s", relative_path)
    return relative_path
