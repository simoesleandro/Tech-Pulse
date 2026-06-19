"""Compat: lock de ingest delegado ao lock global de pipeline."""

from app.deps.pipeline_lock import (
    active_pipeline_job,
    end_pipeline_job,
    pipeline_job_in_progress,
    try_begin_pipeline_job,
)


def try_begin_ingest() -> bool:
    return try_begin_pipeline_job("ingest")


def end_ingest() -> None:
    end_pipeline_job()


def ingest_in_progress() -> bool:
    return pipeline_job_in_progress()
