import asyncio
import logging

import httpx

from app.config import get_settings
from app.services.llm.base import LLMClient, LLMResponse

logger = logging.getLogger(__name__)


class OllamaProvider(LLMClient):
    def __init__(self):
        settings = get_settings()
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model
        self._timeout = settings.llm_timeout
        self._retry_attempts = settings.llm_retry_attempts
        self._retry_backoff = settings.llm_retry_backoff

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        payload = {
            "model": self._model,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 2048,
            },
        }
        last_exc: Exception | None = None
        for attempt in range(self._retry_attempts):
            if attempt > 0:
                delay = self._retry_backoff ** attempt
                logger.warning("Ollama attempt %d/%d failed, retrying in %.1fs: %s", attempt, self._retry_attempts, delay, last_exc)
                await asyncio.sleep(delay)
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(f"{self._base_url}/api/generate", json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                return LLMResponse(
                    text=data.get("response", ""),
                    model=self._model,
                    prompt_tokens=data.get("prompt_eval_count", 0),
                    completion_tokens=data.get("eval_count", 0),
                )
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code >= 500:
                    last_exc = exc
                else:
                    raise
        raise RuntimeError(f"Ollama failed after {self._retry_attempts} attempts") from last_exc

    async def is_healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
