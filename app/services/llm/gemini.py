import httpx

from app.services.llm.base import LLMClient, LLMResponse

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMClient):
    def __init__(self, api_key: str, model: str, timeout: int = 300):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    async def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        url = f"{_BASE}/{self._model}:generateContent?key={self._api_key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return LLMResponse(
            text=text,
            model=self._model,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
        )
