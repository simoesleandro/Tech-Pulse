from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.pipeline_lock import active_pipeline_job, end_pipeline_job, pipeline_job_in_progress
from app.models import NewsItem, ScraperRun
from app.schemas import (
    HealthResponse,
    PipelineConfigResponse,
    PipelineStatusResponse,
    PipelineStepResponse,
    ScraperHealthResponse,
    SystemHealthResponse,
)
from app.services.pipeline_config import (
    get_backfill_pipeline_steps,
    get_ingest_pipeline_steps,
    steps_to_dict,
)

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", service="techpulse-api")


@router.get("/api/pipeline/steps", response_model=PipelineConfigResponse)
def get_pipeline_steps():
    return PipelineConfigResponse(
        ingest=[
            PipelineStepResponse(**step)
            for step in steps_to_dict(get_ingest_pipeline_steps())
        ],
        backfill=[
            PipelineStepResponse(**step)
            for step in steps_to_dict(get_backfill_pipeline_steps())
        ],
    )


@router.get("/api/pipeline/status", response_model=PipelineStatusResponse)
def get_pipeline_status():
    job = active_pipeline_job()
    return PipelineStatusResponse(busy=pipeline_job_in_progress(), active_job=job)


@router.post("/api/pipeline/reset", response_model=PipelineStatusResponse)
def reset_pipeline_lock():
    """Força liberação do lock de pipeline quando um job travar sem liberar."""
    end_pipeline_job()
    return PipelineStatusResponse(busy=False, active_job=None)


_ALL_SOURCES = ["dev.to", "Reddit", "GitHub Trends", "Hacker News", "RSS"]


@router.get("/api/system/health", response_model=SystemHealthResponse)
def system_health(db: Session = Depends(get_db)):
    """Estado de saúde por fonte — última coleta, erros, total de itens."""
    scrapers: list[ScraperHealthResponse] = []

    for source in _ALL_SOURCES:
        last_run = db.scalar(
            select(ScraperRun)
            .where(ScraperRun.source == source)
            .order_by(ScraperRun.started_at.desc())
            .limit(1)
        )
        last_success = db.scalar(
            select(ScraperRun)
            .where(ScraperRun.source == source)
            .where(ScraperRun.error.is_(None))
            .order_by(ScraperRun.started_at.desc())
            .limit(1)
        )

        if last_run is None:
            status = "never_run"
        elif last_run.error is not None:
            status = "error"
        else:
            status = "ok"

        scrapers.append(ScraperHealthResponse(
            source=source,
            last_run_at=last_run.started_at if last_run else None,
            last_success_at=last_success.started_at if last_success else None,
            last_items_found=last_run.items_found if last_run else 0,
            last_error=last_run.error if last_run else None,
            status=status,
        ))

    total_items = db.scalar(select(func.count()).select_from(NewsItem)) or 0
    relevant_items = db.scalar(
        select(func.count()).select_from(NewsItem).where(NewsItem.ai_relevance == "RELEVANTE")
    ) or 0

    return SystemHealthResponse(
        scrapers=scrapers,
        total_items=total_items,
        relevant_items=relevant_items,
    )
