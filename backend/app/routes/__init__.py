from fastapi import FastAPI

from app.lifespan import app_lifespan
from app.routes import backfill, digest, feed, health, ingest, news, obsidian, settings

__all__ = ["health", "news", "ingest", "obsidian", "settings", "backfill", "feed", "digest"]


def register_routes(app: FastAPI) -> None:
    app.include_router(health.router)
    app.include_router(news.router)
    app.include_router(ingest.router)
    app.include_router(obsidian.router)
    app.include_router(settings.router)
    app.include_router(backfill.router)
    app.include_router(feed.router)
    app.include_router(digest.router)
