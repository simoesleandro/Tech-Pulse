import logging
import defusedxml.ElementTree as ET
from xml.etree.ElementTree import Element  # type annotation only; parsing uses defusedxml
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from app.services.scrapers.base import RawArticle
from app.services.scrapers.http_utils import BROWSER_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

MAX_ITEMS_PER_FEED = 12

# Curadoria: programação, web (JS/React/Node/CSS), IA/LLM e releases de linguagens.
DEFAULT_RSS_FEEDS = {
    # Curadoria / notícias tech — alto sinal
    "tldr_tech": "https://tldr.tech/rss",
    "lobsters": "https://lobste.rs/rss",
    "github_blog": "https://github.blog/feed/",
    # IA / LLM
    "simon_willison": "https://simonwillison.net/atom/everything/",
    "huggingface": "https://huggingface.co/blog/feed.xml",
    # Linguagens / runtimes
    "python_insider": "https://blog.python.org/feeds/posts/default",
    "real_python": "https://realpython.com/atom.xml",
    "nodejs_blog": "https://nodejs.org/en/feed/blog.xml",
    "react_blog": "https://react.dev/rss.xml",
    "typescript_blog": "https://devblogs.microsoft.com/typescript/feed/",
    "deno_blog": "https://deno.com/feed",
    # Engenharia
    "pragmatic_engineer": "https://blog.pragmaticengineer.com/rss/",
}


def _strip_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _item_text(item: Element, tag: str) -> str:
    for child in item:
        if _strip_tag(child.tag) == tag and child.text:
            return child.text.strip()
    return ""


def _item_link(item: Element) -> str:
    for child in item:
        if _strip_tag(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href.strip()
            if child.text:
                return child.text.strip()
    return ""


def _parse_pub_date(item: ET.Element) -> "datetime | None":
    """Extrai pub_date de um item/entry XML. Suporta RSS 2.0 (pubDate) e Atom (published/updated)."""
    for tag in ("pubDate", "published", "updated"):
        text = _item_text(item, tag)
        if not text:
            continue
        # Tentar RFC 2822 (RSS 2.0: "Mon, 01 Jan 2024 12:00:00 +0000")
        try:
            dt = parsedate_to_datetime(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
        # Tentar ISO 8601 (Atom: "2024-01-01T12:00:00Z" ou "2024-01-01T12:00:00+00:00")
        try:
            text_clean = text.rstrip("Z") + "+00:00" if text.endswith("Z") else text
            dt = datetime.fromisoformat(text_clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return None


def _item_content_length(item: ET.Element, description: str) -> int:
    """Retorna o tamanho do conteúdo disponível no feed (content > summary > description)."""
    for tag in ("content", "content:encoded", "summary"):
        text = _item_text(item, tag)
        if text:
            return len(text)
    return len(description)


def parse_rss_feed(
    feed_url: str,
    source: str = "rss",
    max_items: int = MAX_ITEMS_PER_FEED,
) -> list[RawArticle]:
    response = requests.get(
        feed_url,
        headers=BROWSER_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    articles: list[RawArticle] = []

    for element in root.iter():
        if _strip_tag(element.tag) not in {"item", "entry"}:
            continue

        title = _item_text(element, "title")
        link = _item_link(element)
        if not title or not link:
            continue

        description = _item_text(element, "description") or _item_text(
            element, "summary"
        )

        articles.append(
            RawArticle(
                title=title,
                url=link,
                source=source,
                description_snippet=description[:280],
                pub_date=_parse_pub_date(element),
                content_length=_item_content_length(element, description),
            )
        )
        if len(articles) >= max_items:
            break

    return articles


def fetch_rss_feeds(
    feeds: dict[str, str] | tuple[tuple[str, str], ...] | None = None,
) -> list[RawArticle]:
    feed_map = DEFAULT_RSS_FEEDS if feeds is None else feeds
    articles: list[RawArticle] = []
    seen_urls: set[str] = set()

    if isinstance(feed_map, dict):
        feed_items = list(feed_map.items())
    else:
        feed_items = list(feed_map)

    def fetch_one(feed_name: str, feed_url: str) -> list[RawArticle]:
        return parse_rss_feed(feed_url, source=f"rss/{feed_name}")

    batches: list[list[RawArticle]] = []
    workers = min(len(feed_items), 8) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(fetch_one, feed_name, feed_url): feed_name
            for feed_name, feed_url in feed_items
        }
        for future in as_completed(futures):
            feed_name = futures[future]
            try:
                batches.append(future.result())
            except (requests.RequestException, ET.ParseError) as exc:
                logger.warning("RSS fetch failed for %s: %s", feed_name, exc)

    for batch in batches:
        for article in batch:
            if article.url in seen_urls:
                continue
            seen_urls.add(article.url)
            articles.append(article)

    return articles
