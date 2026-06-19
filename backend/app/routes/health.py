from fastapi import APIRouter

from app.schemas import HealthResponse, PipelineConfigResponse, PipelineStepResponse
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
