"""Endpoint de analytics pessoal."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_api_key
from app.schemas import AnalyticsResponse
from app.services.analytics import get_analytics

router = APIRouter(tags=["analytics"])


@router.get("/api/analytics", response_model=AnalyticsResponse, dependencies=[Depends(require_api_key)])
def analytics(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Métricas de uso pessoal — fontes, ingest por dia, pastas."""
    return get_analytics(db, days=days)
