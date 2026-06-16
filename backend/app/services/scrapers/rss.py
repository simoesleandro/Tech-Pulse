import logging
import xml.etree.ElementTree as ET

import requests

from app.services.scrapers.base import RawArticle
from app.services.scrapers.http_utils import BROWSER_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# Plug future feeds here, e.g. ("https://tldr.tech/rss", "tldr_tech")
DEFAULT_RSS_FEEDS = {
    "tldr_tech": "https://tldr.tech/tech/rss",
    "real_python": "https://realpython.com/atom.xml",
    "pragmatic_engineer": "https://blog.pragmaticengineer.com/rss/",
    "netflix_tech": "https://netflixtechblog.com/feed",
    "pycoders": "https://pycoders.com/archive/latest.rss"
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
    feeds: tuple[tuple[str, str], ...] | None = None,
) -> list[RawArticle]:
    feed_list = DEFAULT_RSS_FEEDS if feeds is None else feeds
    articles: list[RawArticle] = []
    seen_urls: set[str] = set()

    for feed_url, feed_name in feed_list:
        try:
            batch = parse_rss_feed(feed_url, source=f"rss/{feed_name}")
        except (requests.RequestException, ET.ParseError) as exc:
            logger.warning("RSS fetch failed for %s: %s", feed_url, exc)
            continue

        for article in batch:
            if article.url in seen_urls:
                continue
            seen_urls.add(article.url)
            articles.append(article)

    return articles
