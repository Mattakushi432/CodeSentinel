import httpx

from app.config import get_settings
from app.services.llm.base import LLMClient, LLMResponse


class GroqProvider(LLMClient):
    _BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.groq_api_key
        self._model = settings.groq_model
        self._timeout = 60  # Groq is fast; hard cap at 60s

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._BASE_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=choice,
            model=self._model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
