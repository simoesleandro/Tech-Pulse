from unittest.mock import MagicMock, patch

from app.services.scrapers.devto import fetch_devto_by_tag
from app.services.scrapers.github_trends import fetch_github_trends
from app.services.scrapers.hacker_news import fetch_hacker_news
from app.services.scrapers.reddit import fetch_reddit_subreddit
from app.services.scrapers.rss import fetch_rss_feeds, parse_rss_feed


def test_fetch_reddit_subreddit_uses_browser_headers():
    payload = {
        "data": {
            "children": [
                {
                    "data": {
                        "title": "Async Python patterns",
                        "url": "https://example.com/async-python",
                        "permalink": "/r/Python/comments/abc/async_python/",
                        "selftext": "Discussion about asyncio",
                        "ups": 120,
                        "num_comments": 18,
                        "stickied": False,
                        "is_self": False,
                    }
                }
            ]
        }
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload

    with patch("app.services.scrapers.reddit.requests.get", return_value=mock_response) as mock_get:
        articles = fetch_reddit_subreddit("Python", limit=5)

    assert len(articles) == 1
    assert articles[0].title == "Async Python patterns"
    assert articles[0].url == "https://example.com/async-python"
    assert articles[0].ups == 120
    assert mock_get.call_args.kwargs["headers"]["User-Agent"].startswith("Mozilla/5.0")


def test_fetch_reddit_subreddit_returns_empty_on_403():
    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch("app.services.scrapers.reddit.requests.get", return_value=mock_response):
        articles = fetch_reddit_subreddit("Python", limit=5)

    assert articles == []


def test_fetch_hacker_news_loads_top_items():
    top_ids = [1, 2]
    item_payloads = {
        1: {
            "id": 1,
            "title": "Show HN: TechPulse",
            "url": "https://example.com/techpulse",
            "score": 200,
            "descendants": 44,
        },
        2: {
            "id": 2,
            "title": "Ask HN: Best practices",
            "score": 90,
            "descendants": 12,
        },
    }

    def fake_get(url, timeout=15):
        response = MagicMock()
        if url.endswith("topstories.json"):
            response.json.return_value = top_ids
            response.raise_for_status = MagicMock()
            return response

        item_id = int(url.rsplit("/", 1)[-1].replace(".json", ""))
        response.json.return_value = item_payloads[item_id]
        response.raise_for_status = MagicMock()
        return response

    with patch("app.services.scrapers.hacker_news.requests.get", side_effect=fake_get):
        articles = fetch_hacker_news(limit=2)

    assert len(articles) == 2
    assert articles[0].source == "hacker_news"
    assert articles[0].ups == 200
    assert articles[1].url.endswith("item?id=2")


def test_fetch_devto_by_tag_passes_tag_param():
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "title": "Python tips",
            "url": "https://dev.to/example/python-tips",
            "description": "Useful patterns",
            "positive_reactions_count": 10,
            "comments_count": 2,
        }
    ]
    mock_response.raise_for_status = MagicMock()

    with patch("app.services.scrapers.devto.requests.get", return_value=mock_response) as mock_get:
        articles = fetch_devto_by_tag("python", limit=10)

    assert len(articles) == 1
    assert mock_get.call_args.kwargs["params"]["tag"] == "python"


def test_parse_rss_feed_extracts_items():
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>TLDR AI headline</title>
        <link>https://example.com/tldr-ai</link>
        <description>Short summary</description>
      </item>
    </channel></rss>
    """

    with patch("app.services.scrapers.rss.requests.get") as mock_get:
        mock_get.return_value.content = xml.encode("utf-8")
        mock_get.return_value.raise_for_status = MagicMock()
        articles = parse_rss_feed("https://example.com/feed.xml", source="rss/tldr")

    assert len(articles) == 1
    assert articles[0].title == "TLDR AI headline"
    assert articles[0].source == "rss/tldr"


def test_fetch_rss_feeds_iterates_dict_feeds():
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Dict feed item</title>
        <link>https://example.com/dict-feed</link>
        <description>Summary</description>
      </item>
    </channel></rss>
  """

    feeds = {"custom_feed": "https://example.com/feed.xml"}

    with patch("app.services.scrapers.rss.requests.get") as mock_get:
        mock_get.return_value.content = xml.encode("utf-8")
        mock_get.return_value.raise_for_status = MagicMock()
        articles = fetch_rss_feeds(feeds)

    assert len(articles) == 1
    assert articles[0].source == "rss/custom_feed"


def test_parse_rss_feed_respects_max_items():
    items = "".join(
        f"<item><title>Post {index}</title>"
        f"<link>https://example.com/{index}</link>"
        f"<description>Summary {index}</description></item>"
        for index in range(20)
    )
    xml = f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'

    with patch("app.services.scrapers.rss.requests.get") as mock_get:
        mock_get.return_value.content = xml.encode("utf-8")
        mock_get.return_value.raise_for_status = MagicMock()
        articles = parse_rss_feed("https://example.com/feed.xml", max_items=5)

    assert len(articles) == 5


def test_fetch_github_trends_deduplicates_across_queries():
    payload = {
        "items": [
            {
                "full_name": "acme/llm-kit",
                "html_url": "https://github.com/acme/llm-kit",
                "description": "MCP server for agents",
                "stargazers_count": 120,
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = payload
    mock_response.raise_for_status = MagicMock()

    with patch(
        "app.services.scrapers.github_trends.requests.get",
        return_value=mock_response,
    ) as mock_get:
        articles = fetch_github_trends(limit=10)

    assert len(articles) == 1
    assert articles[0].title == "acme/llm-kit"
    assert mock_get.call_count >= 1
