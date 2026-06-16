from collections.abc import Callable
from typing import Any

ProgressEmitter = Callable[[dict[str, Any]], None]


def emit_step(
    on_progress: ProgressEmitter | None,
    step_id: str,
    status: str,
    detail: str | None = None,
    **extra: Any,
) -> None:
    if on_progress is None:
        return

    payload: dict[str, Any] = {
        "type": "step",
        "step_id": step_id,
        "status": status,
    }
    if detail:
        payload["detail"] = detail
    payload.update(extra)
    on_progress(payload)
