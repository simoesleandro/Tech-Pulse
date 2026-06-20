import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

API_KEY = os.getenv("TECHPULSE_API_KEY", "").strip()

if not API_KEY:
    logger.warning(
        "TECHPULSE_API_KEY não configurada — todos os endpoints de mutação estão SEM autenticação. "
        "Defina a variável de ambiente antes de expor a API publicamente."
    )


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Exige X-API-Key quando TECHPULSE_API_KEY está configurada."""
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida ou ausente")
