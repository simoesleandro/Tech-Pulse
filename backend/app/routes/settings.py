from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_api_key
from app.schemas import AppSettings
from app.services.settings import load_settings, save_settings

router = APIRouter(tags=["settings"])


@router.get("/api/settings", response_model=AppSettings)
def get_app_settings():
    return load_settings()


@router.post("/api/settings", response_model=AppSettings, dependencies=[Depends(require_api_key)])
def update_app_settings(settings: AppSettings):
    try:
        save_settings(settings.model_dump())
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao salvar settings: {exc}") from exc
    return settings
