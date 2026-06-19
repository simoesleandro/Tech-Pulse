from fastapi import HTTPException

from app.deps.pipeline_lock import active_pipeline_job, try_begin_pipeline_job


def guard_pipeline_stream(job_name: str) -> None:
    if not try_begin_pipeline_job(job_name):
        active = active_pipeline_job() or "pipeline"
        raise HTTPException(
            status_code=409,
            detail=f"Job '{active}' em andamento. Aguarde ou cancele antes de iniciar '{job_name}'.",
        )
