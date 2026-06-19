import threading

_lock = threading.Lock()
_active_job: str | None = None


def try_begin_pipeline_job(name: str) -> bool:
    """Adquire lock global para jobs SSE (ingest, export, backfill)."""
    global _active_job
    if not _lock.acquire(blocking=False):
        return False
    _active_job = name
    return True


def end_pipeline_job() -> None:
    """Libera lock de pipeline (idempotente)."""
    global _active_job
    if _lock.locked():
        _lock.release()
    _active_job = None


def active_pipeline_job() -> str | None:
    return _active_job if _lock.locked() else None


def pipeline_job_in_progress() -> bool:
    return _lock.locked()
