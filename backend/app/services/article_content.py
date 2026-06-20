import logging
import re
from html.parser import HTMLParser

import httpx

from app.models import NewsItem
from app.services.scrapers.http_utils import BROWSER_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

DEVTO_ARTICLE_PATTERN = re.compile(r"dev\.to/([^/]+)/([^/?#]+)", re.IGNORECASE)
MAX_CONTEXT_CHARS = 10_000


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "nav", "footer", "header"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "header"}:
            self._skip = False
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "section", "article"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            text = data.strip()
            if text:
                self._chunks.append(text + " ")

    def get_text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", "".join(self._chunks))).strip()


def _truncate(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rsplit(" ", 1)[0] + "…"


def _strip_html_tags(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def _fetch_devto_api(username: str, slug: str) -> str:
    try:
        response = httpx.get(
            f"https://dev.to/api/articles/{username}/{slug}",
            headers=BROWSER_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return ""
        data = response.json()
        return (data.get("body_markdown") or data.get("description") or "").strip()
    except Exception as exc:
        logger.warning("Dev.to API fetch failed for %s/%s: %s", username, slug, exc)
        return ""


def _fetch_devto_html(url: str) -> str:
    try:
        response = httpx.get(
            url,
            headers=BROWSER_HEADERS,
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return ""

        body_match = re.search(
            r'class="crayons-article__body[^"]*"[^>]*>(.*?)</div>\s*<div class="crayons-article__bottom',
            response.text,
            re.DOTALL | re.IGNORECASE,
        )
        if body_match:
            return _strip_html_tags(body_match.group(1))

        return _strip_html_tags(response.text)
    except Exception as exc:
        logger.warning("Dev.to HTML fetch failed for %s: %s", url, exc)
        return ""


def _fetch_devto_body(url: str) -> str:
    match = DEVTO_ARTICLE_PATTERN.search(url)
    if match:
        body = _fetch_devto_api(match.group(1), match.group(2))
        if body:
            return body
    return _fetch_devto_html(url)


def _fetch_url_text(url: str) -> str:
    try:
        response = httpx.get(
            url,
            headers=BROWSER_HEADERS,
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return ""
        return _strip_html_tags(response.text)
    except Exception as exc:
        logger.warning("URL text fetch failed for %s: %s", url, exc)
        return ""


def fetch_article_body(item: NewsItem) -> str:
    cached = getattr(item, "content_cache", None)
    if cached:
        return cached
    body = ""
    if item.source == "dev.to" or "dev.to" in item.url:
        body = _fetch_devto_body(item.url)
    if not body:
        body = _fetch_url_text(item.url)
    return body.strip()


def fetch_article_context(item: NewsItem, max_chars: int = MAX_CONTEXT_CHARS) -> tuple[str, int, str]:
    body = fetch_article_body(item)

    parts = [
        f"Título: {item.title}",
        f"Título original: {item.title_original or item.title}",
        f"Resumo: {item.description or 'Sem resumo.'}",
    ]

    body_chars = len(body)
    if body:
        parts.append(f"Conteúdo do artigo:\n{_truncate(body, max_chars)}")
    else:
        parts.append("Conteúdo completo indisponível — extraia o máximo possível do título e resumo.")

    engagement_bits: list[str] = []
    if item.engagement_reactions:
        engagement_bits.append(f"reactions={item.engagement_reactions}")
    if item.engagement_comments:
        engagement_bits.append(f"comments={item.engagement_comments}")
    if item.engagement_stars:
        engagement_bits.append(f"stars={item.engagement_stars}")
    if item.engagement_ups:
        engagement_bits.append(f"ups={item.engagement_ups}")
    if engagement_bits:
        parts.append("Engajamento: " + ", ".join(engagement_bits))

    return "\n\n".join(parts), body_chars, body
