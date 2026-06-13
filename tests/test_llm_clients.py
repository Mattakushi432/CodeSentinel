"""Tests for app/services/llm/ (Ollama, Groq providers and factory)."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.llm import GroqProvider, OllamaProvider, get_llm_client
from app.services.llm.base import LLMResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(json_data, status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=json_data)
    return resp


def _async_client_ctx(response: MagicMock):
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=response)
    mock_client.post = AsyncMock(return_value=response)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, mock_client


# ---------------------------------------------------------------------------
# OllamaProvider.generate
# ---------------------------------------------------------------------------

_OLLAMA_GENERATE_RESPONSE = {
    "response": "Found 0 issues.",
    "model": "qwen2.5-coder:7b-instruct",
    "prompt_eval_count": 120,
    "eval_count": 30,
}


@pytest.mark.asyncio
async def test_ollama_generate_returns_llm_response():
    resp = _mock_response(_OLLAMA_GENERATE_RESPONSE)
    ctx, mock_client = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = OllamaProvider()
        result = await provider.generate("You are a reviewer", "Review this diff")

    assert isinstance(result, LLMResponse)
    assert result.text == "Found 0 issues."
    assert result.prompt_tokens == 120
    assert result.completion_tokens == 30


@pytest.mark.asyncio
async def test_ollama_generate_posts_to_correct_endpoint():
    resp = _mock_response(_OLLAMA_GENERATE_RESPONSE)
    ctx, mock_client = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = OllamaProvider()
        await provider.generate("system", "user")

    mock_client.post.assert_awaited_once()
    url = mock_client.post.call_args[0][0]
    assert url.endswith("/api/generate")


@pytest.mark.asyncio
async def test_ollama_generate_sends_correct_payload():
    resp = _mock_response(_OLLAMA_GENERATE_RESPONSE)
    ctx, mock_client = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = OllamaProvider()
        await provider.generate("sys prompt", "usr prompt")

    payload = mock_client.post.call_args[1]["json"]
    assert payload["system"] == "sys prompt"
    assert payload["prompt"] == "usr prompt"
    assert payload["stream"] is False


@pytest.mark.asyncio
async def test_ollama_generate_missing_counts_default_to_zero():
    resp = _mock_response({"response": "ok"})
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = OllamaProvider()
        result = await provider.generate("sys", "usr")

    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0


# ---------------------------------------------------------------------------
# OllamaProvider.is_healthy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ollama_is_healthy_returns_true_on_200():
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = OllamaProvider()
        healthy = await provider.is_healthy()

    assert healthy is True


@pytest.mark.asyncio
async def test_ollama_is_healthy_returns_false_on_connection_error():
    ctx = MagicMock()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = OllamaProvider()
        healthy = await provider.is_healthy()

    assert healthy is False


@pytest.mark.asyncio
async def test_ollama_is_healthy_returns_false_on_non_200():
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 503
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = OllamaProvider()
        healthy = await provider.is_healthy()

    assert healthy is False


# ---------------------------------------------------------------------------
# GroqProvider.generate
# ---------------------------------------------------------------------------

_GROQ_RESPONSE = {
    "choices": [
        {"message": {"content": "No critical issues found."}}
    ],
    "usage": {
        "prompt_tokens": 200,
        "completion_tokens": 50,
    },
}


@pytest.mark.asyncio
async def test_groq_generate_returns_llm_response():
    resp = _mock_response(_GROQ_RESPONSE)
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GroqProvider()
        result = await provider.generate("sys", "usr")

    assert isinstance(result, LLMResponse)
    assert result.text == "No critical issues found."
    assert result.prompt_tokens == 200
    assert result.completion_tokens == 50


@pytest.mark.asyncio
async def test_groq_generate_posts_to_groq_url():
    resp = _mock_response(_GROQ_RESPONSE)
    ctx, mock_client = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GroqProvider()
        await provider.generate("system", "user")

    url = mock_client.post.call_args[0][0]
    assert "groq.com" in url


@pytest.mark.asyncio
async def test_groq_generate_includes_bearer_auth():
    resp = _mock_response(_GROQ_RESPONSE)
    ctx, mock_client = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        with patch("app.services.llm.groq.get_settings") as mock_settings:
            settings = MagicMock()
            settings.groq_api_key = "gsk_test_key"
            settings.groq_model = "llama-3.3-70b-versatile"
            mock_settings.return_value = settings

            provider = GroqProvider()
            await provider.generate("sys", "usr")

    headers = mock_client.post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer gsk_test_key"


@pytest.mark.asyncio
async def test_groq_generate_sends_messages_format():
    resp = _mock_response(_GROQ_RESPONSE)
    ctx, mock_client = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GroqProvider()
        await provider.generate("be helpful", "check this code")

    payload = mock_client.post.call_args[1]["json"]
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "be helpful"
    assert payload["messages"][1]["role"] == "user"
    assert payload["messages"][1]["content"] == "check this code"


@pytest.mark.asyncio
async def test_groq_generate_missing_usage_defaults_to_zero():
    resp = _mock_response({
        "choices": [{"message": {"content": "ok"}}],
        # no "usage" key
    })
    ctx, _ = _async_client_ctx(resp)

    with patch("httpx.AsyncClient", return_value=ctx):
        provider = GroqProvider()
        result = await provider.generate("sys", "usr")

    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0


# ---------------------------------------------------------------------------
# get_llm_client factory
# ---------------------------------------------------------------------------

def test_get_llm_client_returns_ollama_by_default():
    with patch("app.services.llm.get_settings") as mock_settings:
        settings = MagicMock()
        settings.llm_provider = "ollama"
        mock_settings.return_value = settings

        client = get_llm_client()

    assert isinstance(client, OllamaProvider)


def test_get_llm_client_returns_groq_when_configured():
    with patch("app.services.llm.get_settings") as mock_settings:
        settings = MagicMock()
        settings.llm_provider = "groq"
        mock_settings.return_value = settings

        client = get_llm_client()

    assert isinstance(client, GroqProvider)


def test_get_llm_client_returns_ollama_for_unknown_provider():
    with patch("app.services.llm.get_settings") as mock_settings:
        settings = MagicMock()
        settings.llm_provider = "unknown-provider"
        mock_settings.return_value = settings

        client = get_llm_client()

    # Falls through to default OllamaProvider
    assert isinstance(client, OllamaProvider)
