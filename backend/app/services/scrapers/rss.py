import logging
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from app.services.scrapers.base import RawArticle
from app.services.scrapers.http_utils import BROWSER_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# Plug future feeds here, e.g. ("https://tldr.tech/rss", "tldr_tech")
DEFAULT_RSS_FEEDS = {
    "real_python": "https://realpython.com/atom.xml",
    "pragmatic_engineer": "https://blog.pragmaticengineer.com/rss/",
}


def _strip_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _item_text(item: ET.Element, tag: str) -> str:
    for child in item:
        if _strip_tag(child.tag) == tag and child.text:
            return child.text.strip()
    return ""


def _item_link(item: ET.Element) -> str:
    for child in item:
        if _strip_tag(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href.strip()
            if child.text:
                return child.text.strip()
    return ""


def parse_rss_feed(feed_url: str, source: str = "rss") -> list[RawArticle]:
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
            )
        )

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
        feed_items = list((name, url) for url, name in feed_map)

    def fetch_one(feed_name: str, feed_url: str) -> list[RawArticle]:
        return parse_rss_feed(feed_url, source=f"rss/{feed_name}")

    batches: list[list[RawArticle]] = []
    workers = min(len(feed_items), 4) or 1
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
