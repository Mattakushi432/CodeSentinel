from app.services.llm.base import LLMClient, LLMResponse
from app.services.llm.ollama import OllamaProvider
from app.services.llm.groq import GroqProvider
from app.config import get_settings

__all__ = ["LLMClient", "LLMResponse", "OllamaProvider", "GroqProvider", "get_llm_client"]


def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "groq":
        return GroqProvider()
    return OllamaProvider()
