import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.deps.auth import require_api_key
from app.deps.pipeline_guard import guard_pipeline_stream
from app.deps.pipeline_lock import end_pipeline_job
from app.repositories.news import get_news_by_ids
from app.schemas import (
    ObsidianConceptResponse,
    ObsidianExportRequest,
    ObsidianExportResult,
    ObsidianFormatResult,
    ObsidianFormattedItem,
    ObsidianStatusResponse,
)
from app.services.concepts import extract_obsidian_concepts
from app.services.obsidian import (
    build_obsidian_note,
    check_rest_connection,
    export_items_to_obsidian,
    format_items_for_obsidian,
    get_obsidian_config,
    _vault_is_configured,
)
from app.streaming import stream_sync_job

router = APIRouter(tags=["obsidian"])


@router.get("/api/obsidian/status", response_model=ObsidianStatusResponse)
def obsidian_status():
    config = get_obsidian_config()
    connected: bool | None = None
    message: str | None = None
    mode = config["mode"]

    if mode == "rest":
        connected, message = check_rest_connection()
    elif mode == "filesystem":
        connected = _vault_is_configured()
        message = (
            "Gravação direta no vault configurada."
            if connected
            else "OBSIDIAN_VAULT_PATH inválido ou inacessível."
        )
    elif mode == "hybrid":
        vault_ok = _vault_is_configured()
        rest_ok, rest_message = check_rest_connection()
        connected = vault_ok
        if vault_ok and rest_ok:
            message = "Vault local + REST API ativos (abrir nota após exportar disponível)."
        elif vault_ok:
            message = (
                "Gravação direta no vault ativa. REST offline — exportações funcionam; "
                "abrir nota automático indisponível até o Obsidian estar aberto."
            )
        else:
            message = f"OBSIDIAN_VAULT_PATH inválido. {rest_message or ''}".strip()

    if not config["configured"]:
        message = (
            "Configure OBSIDIAN_REST_API_KEY (plugin Local REST API) ou "
            "OBSIDIAN_VAULT_PATH no .env do backend."
        )

    return ObsidianStatusResponse(
        configured=config["configured"],
        mode=config["mode"],
        folder=config["folder"],
        connected=connected,
        message=message,
    )


@router.post("/api/obsidian/format", response_model=ObsidianFormatResult, dependencies=[Depends(require_api_key)])
async def format_obsidian_notes(payload: ObsidianExportRequest, db: Session = Depends(get_db)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="Nenhum item selecionado")

    items = get_news_by_ids(db, payload.ids)
    if not items:
        raise HTTPException(status_code=404, detail="Nenhuma notícia encontrada")

    formatted = await format_items_for_obsidian(items, use_agent=True)
    result_items = [
        ObsidianFormattedItem(
            id=item.id,
            markdown=build_obsidian_note(
                item,
                note.body,
                note_title=note.note_title,
                folder=note.folder,
                moc=note.moc,
            ),
        )
        for item, note in formatted
    ]
    combined = "\n---\n\n".join(entry.markdown for entry in result_items)
    return ObsidianFormatResult(items=result_items, markdown=combined)


@router.post("/api/obsidian/export", response_model=ObsidianExportResult, dependencies=[Depends(require_api_key)])
async def export_to_obsidian(payload: ObsidianExportRequest, db: Session = Depends(get_db)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="Nenhum item selecionado")

    items = get_news_by_ids(db, payload.ids)
    if not items:
        raise HTTPException(status_code=404, detail="Nenhuma notícia encontrada")

    try:
        result = await export_items_to_obsidian(items, emit=None, db=db)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if result["exported"] == 0 and result.get("skipped", 0) == 0:
        raise HTTPException(
            status_code=500,
            detail="Nenhuma nota exportada. " + "; ".join(result["errors"]),
        )

    return ObsidianExportResult(**result)


def _run_obsidian_export_job(items, emit) -> dict:
    db = SessionLocal()
    try:
        return asyncio.run(export_items_to_obsidian(items, emit=emit, db=db))
    finally:
        db.close()


@router.post("/api/obsidian/export/stream", dependencies=[Depends(require_api_key)])
async def export_to_obsidian_stream(
    payload: ObsidianExportRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="Nenhum item selecionado")

    items = get_news_by_ids(db, payload.ids)
    if not items:
        raise HTTPException(status_code=404, detail="Nenhuma notícia encontrada")

    guard_pipeline_stream("obsidian-export")

    def job(emit, cancel_event=None):
        try:
            return _run_obsidian_export_job(items, emit)
        except RuntimeError as exc:
            emit({"type": "error", "message": str(exc)})
            raise
        finally:
            end_pipeline_job()

    return stream_sync_job(job, request, job_name="obsidian-export", on_finished=end_pipeline_job)


@router.get("/api/obsidian/concepts", response_model=list[ObsidianConceptResponse])
def get_obsidian_concepts(db: Session = Depends(get_db)):
    return extract_obsidian_concepts(db)
