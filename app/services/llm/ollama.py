import httpx
from app.services.llm.base import LLMClient, LLMResponse
from app.config import get_settings


class OllamaProvider(LLMClient):
    def __init__(self):
        settings = get_settings()
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model
        self._timeout = settings.llm_timeout

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

    async def is_healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False
