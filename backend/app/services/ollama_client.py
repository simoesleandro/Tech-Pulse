import logging
import os

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_URL = os.getenv("OLLAMA_URL", f"{OLLAMA_BASE}/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
REQUEST_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "180"))

_resolved_model: str | None = None
PREFERRED_MODEL_PREFIXES = ("gemma4", "gemma3", "gemma2", "gemma", "llama3", "mistral")


async def resolve_ollama_model() -> str:
    global _resolved_model

    if _resolved_model:
        return _resolved_model

    if OLLAMA_MODEL:
        _resolved_model = OLLAMA_MODEL
        return _resolved_model

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE}/api/tags")
            response.raise_for_status()
            model_names = [item["name"] for item in response.json().get("models", [])]

        for prefix in PREFERRED_MODEL_PREFIXES:
            for name in model_names:
                if name.split(":")[0] == prefix or name.startswith(f"{prefix}:"):
                    _resolved_model = name
                    logger.info("Ollama model auto-detected: %s", name)
                    return name

        if model_names:
            _resolved_model = model_names[0]
            return model_names[0]
    except Exception as exc:
        logger.warning("Could not auto-detect Ollama model: %s", exc)

    _resolved_model = "gemma4:12b"
    return _resolved_model


async def ollama_generate(prompt: str, system: str | None = None) -> str:
    model = await resolve_ollama_model()
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        return response.json().get("response", "").strip()
