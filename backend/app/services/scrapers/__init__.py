from app.services.scrapers.devto import fetch_devto
from app.services.scrapers.github_trends import fetch_github_trends
from app.services.scrapers.reddit import fetch_reddit

__all__ = ["fetch_devto", "fetch_github_trends", "fetch_reddit"]
