import os

from fastapi import Header, HTTPException

API_KEY = os.getenv("TECHPULSE_API_KEY", "").strip()


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Exige X-API-Key quando TECHPULSE_API_KEY está configurada."""
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida ou ausente")
