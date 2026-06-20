import asyncio
import functools
import logging
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlunparse

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_app_config
from app.models import NewsItem
from app.services.ai_agent import (
    AgentProgressCallback,
    enrich_article_sync,
    enrich_articles_as_completed,
)
from app.services.hype_backfill import (
    apply_engagement_from_article,
    item_to_raw_article,
    refresh_item_hype,
    resolve_hype_score,
)
from app.services.pipeline_progress import ProgressEmitter, emit_step
from app.pipeline.job import PipelineJob
from app.services.scrapers.base import EnrichedArticle, RawArticle


def resolve_persist_title(article: RawArticle, title_pt: str) -> str:
    """Garante títulos legíveis de GitHub Trends ao persistir no SQLite."""
    if article.source == "github_trends":
        from app.services.obsidian_titles import prettify_github_title

        return prettify_github_title(title_pt)
    return title_pt


from app.services.scrapers import (
    fetch_devto,
    fetch_github_trends,
    fetch_hacker_news,
    fetch_reddit,
    fetch_rss_feeds,
)

logger = logging.getLogger(__name__)

# Padrões que descartam artigos óbvios sem gastar LLM
_NOISE_PATTERNS = (
    re.compile(r"\b(we.?re hiring|open position|join our team|h1.?b|work with us)\b", re.I),
    re.compile(r"\bnewsletter\s+(issue|#\s*\d|vol\.?\s*\d)", re.I),
    re.compile(r"\b(giveaway|sweepstakes?|win a)\b", re.I),
)


def _quick_reject(article: RawArticle) -> bool:
    text = f"{article.title} {article.description_snippet or ''}"
    return any(p.search(text) for p in _NOISE_PATTERNS)


def _title_bigrams(title: str) -> frozenset[str]:
    words = re.sub(r"[^\w\s]", "", title.lower()).split()
    return frozenset(f"{a}_{b}" for a, b in zip(words, words[1:]))


def _titles_are_similar(a: str, b: str, threshold: float = 0.65) -> bool:
    bg_a = _title_bigrams(a)
    bg_b = _title_bigrams(b)
    if not bg_a or not bg_b:
        return False
    union = len(bg_a | bg_b)
    return union > 0 and len(bg_a & bg_b) / union >= threshold


CancelCheck = Callable[[], bool]

_ingest_cancel_event: threading.Event | None = None
_cancel_event_lock = threading.Lock()


def set_ingest_cancel_event(event: threading.Event | None) -> None:
    global _ingest_cancel_event
    with _cancel_event_lock:
        _ingest_cancel_event = event


def _is_cancelled() -> bool:
    global _ingest_cancel_event
    with _cancel_event_lock:
        event = _ingest_cancel_event
    return bool(event and event.is_set())


def _raise_if_cancelled() -> None:
    if _is_cancelled():
        raise InterruptedError("Ingestão cancelada — conexão encerrada.")


Fetcher = Callable[[], list[RawArticle]]


def _fetcher_name(fetcher: Fetcher) -> str:
    if isinstance(fetcher, functools.partial):
        return getattr(fetcher.func, "__name__", "partial_fetcher")
    return getattr(fetcher, "__name__", "fetcher")


DEFAULT_FETCHERS: list[Fetcher] = [
    fetch_devto,
    fetch_reddit,
    fetch_github_trends,
    fetch_hacker_news,
    fetch_rss_feeds,
]


def normalize_url(url: str) -> str:
    """Normaliza URL para deduplicação consistente (trailing slash, host, etc.)."""
    raw = (url or "").strip()
    if not raw:
        return raw

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", "", ""))


def _load_existing_urls(db: Session) -> set[str]:
    return {
        normalize_url(url)
        for url in db.scalars(select(NewsItem.url)).all()
        if url
    }


FETCHER_LABELS: dict[str, str] = {
    "fetch_devto": "dev.to",
    "fetch_reddit": "Reddit",
    "fetch_github_trends": "GitHub Trends",
    "fetch_hacker_news": "Hacker News",
    "fetch_rss_feeds": "RSS",
}


def _fetch_all_articles(
    fetchers: list[Fetcher],
    on_progress: ProgressEmitter | None = None,
) -> tuple[list[RawArticle], list[str]]:
    articles: list[RawArticle] = []
    errors: list[str] = []

    if not fetchers:
        return articles, errors

    def run_fetcher(fetcher: Fetcher) -> tuple[list[RawArticle], str | None]:
        name = _fetcher_name(fetcher)
        label = FETCHER_LABELS.get(name, name)
        emit_step(on_progress, "fetch", "active", f"Buscando {label}…")
        try:
            batch = fetcher()
            emit_step(
                on_progress,
                "fetch",
                "active",
                f"{label}: {len(batch)} artigo(s)",
            )
            return batch, None
        except Exception as exc:
            message = f"{label}: {exc}"
            logger.warning("Scraper failed %s", message)
            emit_step(on_progress, "fetch", "active", f"{label}: falhou")
            return [], message

    max_workers = min(len(fetchers), 5)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(run_fetcher, fetcher) for fetcher in fetchers]
        for future in as_completed(futures):
            batch, error = future.result()
            articles.extend(batch)
            if error:
                errors.append(error)

    return articles, errors


def _count_pending(db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(NewsItem)
            .where(
                or_(
                    NewsItem.is_enriched.is_(False),
                    NewsItem.hype_score == 0,
                )
            )
        )
        or 0
    )


def needs_agent_refresh(item: NewsItem) -> bool:
    if not item.is_enriched or item.ai_relevance != "RELEVANTE":
        return False
    reasoning = (item.ai_reasoning or "").strip()
    if not reasoning:
        return True
    return "Novidade" not in reasoning or "Utilidade" not in reasoning


def _count_legacy_enrichment(db: Session) -> int:
    items = db.scalars(
        select(NewsItem)
        .where(NewsItem.is_enriched.is_(True))
        .where(NewsItem.ai_relevance == "RELEVANTE")
    ).all()
    return sum(1 for item in items if needs_agent_refresh(item))


def get_backfill_status(db: Session) -> dict[str, int]:
    obsidian_unmarked = (
        db.scalar(
            select(func.count())
            .select_from(NewsItem)
            .where(NewsItem.obsidian_exported_at.is_(None))
            .where(NewsItem.ai_relevance == "RELEVANTE")
        )
        or 0
    )
    return {
        "obsidian_unmarked": obsidian_unmarked,
        "legacy_enrichment_pending": _count_legacy_enrichment(db),
    }


def _persist_article(
    db: Session,
    article: RawArticle,
    enriched: EnrichedArticle,
    *,
    commit: bool = True,
) -> NewsItem:
    hype_score = resolve_hype_score(enriched.hype_score, article)
    db_item = NewsItem(
        title=resolve_persist_title(article, enriched.title_pt),
        title_original=article.title,
        description=enriched.description_pt,
        url=article.url,
        source=article.source,
        ai_relevance=enriched.ai_relevance,
        hype_score=hype_score,
        ai_reasoning=enriched.ai_reasoning,
        engagement_reactions=article.positive_reactions,
        engagement_comments=article.comments_count,
        engagement_stars=article.stars,
        engagement_ups=article.ups,
        is_enriched=True,
    )
    db.add(db_item)
    if commit:
        db.commit()
        db.refresh(db_item)
    else:
        db.flush()
    return db_item


class _BatchPersister:
    """Acumula inserts e faz commit a cada N artigos."""

    def __init__(self, db: Session, batch_size: int | None = None):
        if batch_size is None:
            batch_size = get_app_config().ingest_batch_size
        self.db = db
        self.batch_size = batch_size
        self._pending = 0

    def persist(self, article: RawArticle, enriched: EnrichedArticle) -> NewsItem:
        item = _persist_article(self.db, article, enriched, commit=False)
        self._pending += 1
        if self._pending >= self.batch_size:
            self.flush()
        return item

    def flush(self) -> None:
        if self._pending:
            self.db.commit()
            self._pending = 0


def _agent_progress_factory(
    on_progress: ProgressEmitter | None,
    article_index: int,
    article_total: int,
    title: str,
) -> AgentProgressCallback:
    def on_agent_progress(step_id: str, status: str, detail: str | None = None) -> None:
        label = detail or f"artigo {article_index}/{article_total}"
        emit_step(
            on_progress,
            step_id,
            status,
            label,
            article_index=article_index,
            article_total=article_total,
            title=title,
        )

    return on_agent_progress


async def _background_obsidian_export(item_id: int) -> None:
    from app.database import SessionLocal
    from app.services.obsidian import export_items_to_obsidian, mark_items_obsidian_exported

    await asyncio.sleep(0.5)

    db = SessionLocal()
    try:
        from app.models import NewsItem
        from sqlalchemy import select

        item = db.scalar(select(NewsItem).where(NewsItem.id == item_id))
        if item and item.ai_relevance == "RELEVANTE" and item.obsidian_exported_at is None:
            logger.info("Auto-exporting item %d to Obsidian...", item_id)
            result = await export_items_to_obsidian([item])
            if result.get("exported", 0) > 0:
                mark_items_obsidian_exported(db, [item_id])
                logger.info("Item %d auto-exported to Obsidian successfully.", item_id)
            else:
                logger.error("Failed to auto-export item %d: %s", item_id, result.get("errors"))
    except Exception as exc:
        logger.exception("Error during auto-export of item %d to Obsidian: %s", item_id, exc)
    finally:
        db.close()


def trigger_obsidian_auto_export(item_id: int) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_background_obsidian_export(item_id))
    except RuntimeError:
        import threading
        threading.Thread(
            target=lambda: asyncio.run(_background_obsidian_export(item_id)),
            daemon=True
        ).start()


def _persist_raw_articles(
    db: Session,
    pending: list[RawArticle],
    existing_urls: set[str],
) -> dict[str, int]:
    """Phase 1: insert all pending articles immediately as PENDING before LLM."""
    id_by_url: dict[str, int] = {}
    for article in pending:
        try:
            item = NewsItem(
                title=article.title,
                title_original=article.title,
                description=article.description_snippet or "",
                url=article.url,
                source=article.source,
                ai_relevance="PENDING",
                is_enriched=False,
                engagement_reactions=article.positive_reactions,
                engagement_comments=article.comments_count,
                engagement_stars=article.stars,
                engagement_ups=article.ups,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            id_by_url[article.url] = item.id
            existing_urls.add(normalize_url(article.url))
        except IntegrityError:
            db.rollback()
            existing_urls.add(normalize_url(article.url))
    return id_by_url


def _persist_enriched_result(
    db: Session,
    index: int,
    article: RawArticle,
    enriched: EnrichedArticle,
    on_progress: ProgressEmitter | None,
    total_pending: int,
    existing_urls: set[str],
    stats: dict,
    *,
    batch: _BatchPersister | None = None,
    job: PipelineJob | None = None,
    obsidian_auto_export: bool = False,
    raw_item: NewsItem | None = None,
) -> None:
    stats["classified"] += 1

    if job:
        job.raise_if_cancelled()
        job.emit_step(
            on_progress,
            "save",
            "active",
            f"salvando artigo {index}/{total_pending} no SQLite…",
            article_index=index,
            article_total=total_pending,
            title=article.title,
        )
    else:
        emit_step(
            on_progress,
            "save",
            "active",
            f"salvando artigo {index}/{total_pending} no SQLite…",
            article_index=index,
            article_total=total_pending,
            title=article.title,
        )

    if raw_item is not None:
        _apply_enriched_to_item(raw_item, article, enriched)
        db.commit()
        db_item = raw_item
    elif batch is not None:
        db_item = batch.persist(article, enriched)
    else:
        db_item = _persist_article(db, article, enriched)

    done_detail = f"artigo {index}/{total_pending} salvo · {enriched.title_pt[:60]}"
    if job:
        job.emit_step(
            on_progress,
            "save",
            "done",
            done_detail,
            article_index=index,
            article_total=total_pending,
            title=article.title,
        )
    else:
        emit_step(
            on_progress,
            "save",
            "done",
            done_detail,
            article_index=index,
            article_total=total_pending,
            title=article.title,
        )

    existing_urls.add(normalize_url(article.url))
    stats["saved"] += 1
    if enriched.ai_relevance == "RELEVANTE":
        stats["relevante"] += 1
        if obsidian_auto_export:
            trigger_obsidian_auto_export(db_item.id)
    else:
        stats["lixo"] += 1


async def _enrich_and_persist_streaming(
    db: Session,
    pending: list[RawArticle],
    on_progress: ProgressEmitter | None,
    total_pending: int,
    existing_urls: set[str],
    stats: dict,
    *,
    batch: _BatchPersister,
    job: PipelineJob | None = None,
    obsidian_auto_export: bool = False,
    raw_id_by_url: dict[str, int] | None = None,
) -> None:
    def factory(index: int, total: int, title: str) -> AgentProgressCallback:
        return _agent_progress_factory(on_progress, index, total, title)

    async for index, article, outcome in enrich_articles_as_completed(pending, factory):
        if job:
            job.raise_if_cancelled()
        else:
            _raise_if_cancelled()

        if isinstance(outcome, Exception):
            if isinstance(outcome, InterruptedError):
                raise outcome
            stats["errors"].append(f"{article.url}: {outcome}")
            continue

        raw_item: NewsItem | None = None
        if raw_id_by_url and article.url in raw_id_by_url:
            raw_item = db.get(NewsItem, raw_id_by_url[article.url])

        try:
            _persist_enriched_result(
                db,
                index,
                article,
                outcome,
                on_progress,
                total_pending,
                existing_urls,
                stats,
                batch=batch if raw_item is None else None,
                job=job,
                obsidian_auto_export=obsidian_auto_export,
                raw_item=raw_item,
            )
        except IntegrityError:
            db.rollback()
            if raw_item is None:
                batch._pending = 0
            existing_urls.add(normalize_url(article.url))
            stats["skipped_duplicate"] += 1
        except InterruptedError:
            raise
        except Exception as exc:
            db.rollback()
            stats["errors"].append(f"{article.url}: {exc}")


def _run_streaming_enrich(
    db: Session,
    pending: list[RawArticle],
    on_progress: ProgressEmitter | None,
    total_pending: int,
    existing_urls: set[str],
    stats: dict,
    *,
    batch: _BatchPersister,
    job: PipelineJob | None = None,
    obsidian_auto_export: bool = False,
    raw_id_by_url: dict[str, int] | None = None,
) -> None:
    asyncio.run(
        _enrich_and_persist_streaming(
            db,
            pending,
            on_progress,
            total_pending,
            existing_urls,
            stats,
            batch=batch,
            job=job,
            obsidian_auto_export=obsidian_auto_export,
            raw_id_by_url=raw_id_by_url,
        )
    )


def _enrich_with_progress(
    article: RawArticle,
    on_progress: ProgressEmitter | None,
    article_index: int,
    article_total: int,
) -> EnrichedArticle:
    return enrich_article_sync(
        article,
        on_agent_progress=_agent_progress_factory(on_progress, article_index, article_total, article.title),
    )


def run_ingest(
    db: Session,
    fetchers: list[Fetcher] | None = None,
    enricher: Callable[[RawArticle], object] | None = None,
    on_progress: ProgressEmitter | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:
    job = PipelineJob("ingest", cancel_event)
    set_ingest_cancel_event(job.cancel_event)

    def _check_cancel() -> None:
        job.raise_if_cancelled()

    batch = _BatchPersister(db)
    from app.services.settings import load_settings
    settings = load_settings()
    obsidian_auto_export: bool = bool(settings.get("obsidian_auto_export", False))
    if fetchers is None:
        sources = settings.get("sources", {})
        fetchers = []
        if sources.get("dev_to", True):
            fetchers.append(fetch_devto)
        if sources.get("reddit", True):
            fetchers.append(fetch_reddit)
        if sources.get("github_trends", True):
            fetchers.append(fetch_github_trends)
        if sources.get("hacker_news", True):
            fetchers.append(fetch_hacker_news)
        if sources.get("rss_feeds", True):
            fetchers.append(fetch_rss_feeds)

    job.emit_step(on_progress, "fetch", "active", "Iniciando busca nas fontes…")
    existing_urls = _load_existing_urls(db)
    articles, scraper_errors = _fetch_all_articles(fetchers, on_progress)
    job.emit_step(on_progress, "fetch", "done", f"{len(articles)} artigos capturados")

    job.emit_step(on_progress, "dedup", "active", "Removendo duplicatas…")
    noise_rejected = sum(1 for a in articles if _quick_reject(a))
    url_deduped = [
        article
        for article in articles
        if normalize_url(article.url) not in existing_urls and not _quick_reject(article)
    ]

    # Semantic dedup: drop articles whose title is very similar to one already in DB
    existing_titles = list(
        db.scalars(
            select(NewsItem.title_original).where(NewsItem.title_original != "")
        ).all()
    )
    seen_titles: list[str] = list(existing_titles)
    title_rejected = 0
    pending: list[RawArticle] = []
    for article in url_deduped:
        if any(_titles_are_similar(article.title, t) for t in seen_titles):
            title_rejected += 1
        else:
            pending.append(article)
            seen_titles.append(article.title)

    skipped = len(articles) - len(url_deduped) - noise_rejected
    reject_detail = f"{skipped} já no feed · {noise_rejected} ruído · {title_rejected} similar · {len(pending)} novos"
    job.emit_step(on_progress, "dedup", "done", reject_detail)

    stats = {
        "fetched": len(articles),
        "skipped_duplicate": skipped + title_rejected,
        "classified": 0,
        "saved": 0,
        "relevante": 0,
        "lixo": 0,
        "errors": list(scraper_errors),
    }

    total_pending = len(pending)

    _check_cancel()

    # Phase 1: persist all pending articles immediately (ai_relevance="PENDING")
    # This makes them visible/countable while LLM enrichment runs in Phase 2
    raw_id_by_url = _persist_raw_articles(db, pending, existing_urls)

    try:
        if enricher is not None:
            for index, article in enumerate(pending, start=1):
                _check_cancel()
                raw_item = db.get(NewsItem, raw_id_by_url.get(article.url)) if raw_id_by_url.get(article.url) else None
                try:
                    enriched = enricher(article)
                    _persist_enriched_result(
                        db,
                        index,
                        article,
                        enriched,
                        on_progress,
                        total_pending,
                        existing_urls,
                        stats,
                        batch=batch if raw_item is None else None,
                        job=job,
                        obsidian_auto_export=obsidian_auto_export,
                        raw_item=raw_item,
                    )
                except IntegrityError:
                    db.rollback()
                    if raw_item is None:
                        batch._pending = 0
                    existing_urls.add(normalize_url(article.url))
                    stats["skipped_duplicate"] += 1
                except InterruptedError:
                    raise
                except Exception as exc:
                    db.rollback()
                    if raw_item is None:
                        batch._pending = 0
                    stats["errors"].append(f"{article.url}: {exc}")
        else:
            _run_streaming_enrich(
                db,
                pending,
                on_progress,
                total_pending,
                existing_urls,
                stats,
                batch=batch,
                job=job,
                obsidian_auto_export=obsidian_auto_export,
                raw_id_by_url=raw_id_by_url,
            )
    finally:
        batch.flush()

    return stats


def _prepare_raw_article(item: NewsItem) -> RawArticle:
    raw = item_to_raw_article(item)
    if not raw.description_snippet and item.description:
        return RawArticle(
            title=raw.title,
            url=raw.url,
            source=raw.source,
            description_snippet=item.description,
            positive_reactions=item.engagement_reactions,
            comments_count=item.engagement_comments,
            stars=item.engagement_stars,
            ups=item.engagement_ups,
        )
    return raw


def _apply_enriched_to_item(
    item: NewsItem,
    raw: RawArticle,
    enriched: EnrichedArticle,
) -> None:
    item.title = resolve_persist_title(raw, enriched.title_pt)
    item.title_original = raw.title
    item.description = enriched.description_pt
    item.ai_relevance = enriched.ai_relevance
    item.ai_reasoning = enriched.ai_reasoning
    apply_engagement_from_article(item, raw)
    item.hype_score = resolve_hype_score(enriched.hype_score, raw)
    if item.hype_score == 0:
        refresh_item_hype(item)
    item.is_enriched = True


async def _parallel_enrich_items(
    pairs: list[tuple[NewsItem, RawArticle]],
    on_progress: ProgressEmitter | None,
    *,
    skip_triador: bool = False,
) -> list[tuple[NewsItem, RawArticle, EnrichedArticle | Exception]]:
    if not pairs:
        return []

    articles = [raw for _, raw in pairs]
    item_by_url = {item.url: item for item, _ in pairs}
    total = len(pairs)

    emit_step(on_progress, "pick", "active", f"{total} selecionado(s)")

    def factory(index: int, count: int, title: str) -> AgentProgressCallback:
        return _agent_progress_factory(on_progress, index, count, title)

    outcomes: list[tuple[NewsItem, RawArticle, EnrichedArticle | Exception]] = []
    async for _index, article, outcome in enrich_articles_as_completed(
        articles,
        factory,
        skip_triador=skip_triador,
    ):
        _raise_if_cancelled()
        item = item_by_url[article.url]
        emit_step(on_progress, "pick", "done", article.title[:80])
        outcomes.append((item, article, outcome))

    return outcomes


def _run_parallel_item_enrichment(
    db: Session,
    pairs: list[tuple[NewsItem, RawArticle]],
    on_progress: ProgressEmitter | None,
    *,
    skip_triador: bool = False,
) -> tuple[int, int, list[str]]:
    processed = 0
    errors = 0
    error_messages: list[str] = []

    async def _run() -> None:
        nonlocal processed, errors
        outcomes = await _parallel_enrich_items(
            pairs,
            on_progress,
            skip_triador=skip_triador,
        )
        for item, article, outcome in outcomes:
            if isinstance(outcome, Exception):
                errors += 1
                detail = outcome if str(outcome).strip() else repr(outcome)
                error_messages.append(f"{article.url}: {detail}")
                logger.warning("Backfill enrich failed for %s: %s", article.url, detail)
                continue

            try:
                emit_step(on_progress, "save", "active", article.title[:80], title=article.title)
                _apply_enriched_to_item(item, article, outcome)
                db.commit()
                emit_step(on_progress, "save", "done", outcome.title_pt[:80], title=article.title)
                processed += 1
            except Exception as exc:
                db.rollback()
                errors += 1
                error_messages.append(f"{article.url}: {exc}")
                logger.warning("Backfill persist failed for %s: %s", article.url, exc)

    asyncio.run(_run())
    return processed, errors, error_messages


def enrich_missing_items(
    db: Session,
    limit: int = 1,
    on_progress: ProgressEmitter | None = None,
) -> dict[str, int]:
    pending_before = _count_pending(db)
    items = db.scalars(
        select(NewsItem)
        .where(
            or_(
                NewsItem.is_enriched.is_(False),
                NewsItem.hype_score == 0,
            )
        )
        .order_by(NewsItem.created_at.desc())
        .limit(limit)
    ).all()

    hype_only = [item for item in items if item.is_enriched and item.hype_score == 0]
    enrich_pairs = [
        (item, _prepare_raw_article(item))
        for item in items
        if not (item.is_enriched and item.hype_score == 0)
    ]

    processed = 0
    errors = 0
    error_messages: list[str] = []

    for item in hype_only:
        try:
            emit_step(on_progress, "hype", "active", "recalculando hype")
            refresh_item_hype(item)
            db.commit()
            emit_step(on_progress, "hype", "done", f"{item.hype_score} estrelas")
            processed += 1
        except Exception as exc:
            db.rollback()
            errors += 1
            error_messages.append(f"{item.url}: {exc}")

    batch_processed, batch_errors, batch_messages = _run_parallel_item_enrichment(
        db,
        enrich_pairs,
        on_progress,
        skip_triador=False,
    )
    processed += batch_processed
    errors += batch_errors
    error_messages.extend(batch_messages)

    remaining = _count_pending(db)

    return {
        "processed": processed,
        "errors": errors,
        "candidates": pending_before,
        "remaining": remaining,
        "error_messages": error_messages,
    }


def re_enrich_legacy_items(
    db: Session,
    limit: int = 10,
    on_progress: ProgressEmitter | None = None,
) -> dict[str, int]:
    candidates_before = _count_legacy_enrichment(db)
    all_candidates = db.scalars(
        select(NewsItem)
        .where(NewsItem.is_enriched.is_(True))
        .where(NewsItem.ai_relevance == "RELEVANTE")
        .order_by(NewsItem.created_at.desc())
    ).all()
    items = [item for item in all_candidates if needs_agent_refresh(item)][:limit]

    enrich_pairs = [(item, _prepare_raw_article(item)) for item in items]
    processed, errors, error_messages = _run_parallel_item_enrichment(
        db,
        enrich_pairs,
        on_progress,
        skip_triador=True,
    )

    remaining = _count_legacy_enrichment(db)

    return {
        "processed": processed,
        "errors": errors,
        "candidates": candidates_before,
        "remaining": remaining,
        "error_messages": error_messages,
    }
