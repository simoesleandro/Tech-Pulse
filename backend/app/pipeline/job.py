import logging
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

ProgressEmitter = Callable[[dict], None]


class PipelineJob:
    """Contexto de job com cancelamento cooperativo e logging estruturado."""

    def __init__(self, name: str, cancel_event: threading.Event | None = None):
        self.job_id = uuid.uuid4().hex[:12]
        self.name = name
        self.cancel_event = cancel_event or threading.Event()
        self._step_started: float | None = None

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise InterruptedError(f"{self.name} cancelado.")

    def emit_step(
        self,
        emit: ProgressEmitter | None,
        step_id: str,
        status: str,
        detail: str | None = None,
        **extra: Any,
    ) -> None:
        if self._step_started is not None and status == "done":
            duration_ms = int((time.monotonic() - self._step_started) * 1000)
            logger.info(
                "pipeline step done job_id=%s name=%s step=%s duration_ms=%s",
                self.job_id,
                self.name,
                step_id,
                duration_ms,
            )
            self._step_started = None
        elif status == "active":
            self._step_started = time.monotonic()
            logger.info(
                "pipeline step active job_id=%s name=%s step=%s detail=%s",
                self.job_id,
                self.name,
                step_id,
                detail or "",
            )

        if emit is None:
            return
        event: dict[str, Any] = {
            "type": "step",
            "step_id": step_id,
            "status": status,
        }
        if detail:
            event["detail"] = detail
        event.update(extra)
        emit(event)
