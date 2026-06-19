import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import ollama_client


@pytest.fixture(autouse=True)
def reset_ollama_model_cache():
    ollama_client._resolved_model = None
    yield
    ollama_client._resolved_model = None


@pytest.mark.asyncio
async def test_groq_non_retryable_400_raises_immediately(monkeypatch):
    monkeypatch.setattr(ollama_client, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ollama_client, "GROQ_MODEL", "llama-3.3-70b-versatile")

    response = MagicMock()
    response.status_code = 400
    response.headers = {}
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request",
        request=MagicMock(),
        response=response,
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            await ollama_client.groq_generate("hello")

    assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_ollama_generate_falls_back_to_ollama_when_groq_fails(monkeypatch):
    monkeypatch.setattr(ollama_client, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(ollama_client, "PROVIDER_UNIFIED", "groq")
    monkeypatch.setattr(ollama_client, "_ingest_was_cancelled", lambda: False)

    async def failing_groq(*args, **kwargs):
        raise RuntimeError("Groq down")

    async def resolve_model():
        return "gemma4:12b"

    ollama_response = MagicMock()
    ollama_response.raise_for_status = MagicMock()
    ollama_response.json.return_value = {"response": "ollama ok"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=ollama_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.ollama_client.groq_generate", side_effect=failing_groq):
        with patch("app.services.ollama_client.resolve_ollama_model", side_effect=resolve_model):
            with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
                result = await ollama_client.ollama_generate("prompt", step_name="unified")

    assert result == "ollama ok"
    mock_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_unload_ollama_model_sends_keep_alive_zero(monkeypatch):
    monkeypatch.setattr(ollama_client, "OLLAMA_URL", "http://localhost:11434/api/generate")

    async def resolve_model():
        return "gemma4:12b"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.ollama_client.resolve_ollama_model", side_effect=resolve_model):
        with patch("app.services.ollama_client.httpx.AsyncClient", return_value=mock_client):
            await ollama_client.unload_ollama_model()

    mock_client.post.assert_awaited_once()
    payload = mock_client.post.await_args.kwargs["json"]
    assert payload["keep_alive"] == 0
