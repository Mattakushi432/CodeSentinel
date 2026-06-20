from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import get_settings
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import LLMClient, LLMResponse
from app.services.llm.gemini import GeminiProvider
from app.services.llm.groq import GroqProvider
from app.services.llm.ollama import OllamaProvider
from app.services.llm.openai_compat import OpenAICompatProvider

if TYPE_CHECKING:
    from app.models.organization import Organization

__all__ = [
    "LLMClient",
    "LLMResponse",
    "OllamaProvider",
    "GroqProvider",
    "OpenAICompatProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "get_llm_client",
    "PROVIDER_REGISTRY",
]

# provider_id -> {base_url (OpenAI-compat only), default_model, label}
PROVIDER_REGISTRY: dict[str, dict[str, str]] = {
    "ollama":      {"default_model": "qwen2.5-coder:7b-instruct",                         "label": "Ollama (self-hosted)"},
    "openai":      {"base_url": "https://api.openai.com/v1",                              "default_model": "gpt-4o",                    "label": "OpenAI (ChatGPT)"},
    "anthropic":   {"default_model": "claude-opus-4-8",                                   "label": "Anthropic (Claude)"},
    "gemini":      {"default_model": "gemini-2.0-flash",                                  "label": "Google Gemini"},
    "groq":        {"base_url": "https://api.groq.com/openai/v1",                         "default_model": "llama-3.3-70b-versatile",   "label": "Groq"},
    "deepseek":    {"base_url": "https://api.deepseek.com/v1",                            "default_model": "deepseek-coder",            "label": "DeepSeek"},
    "mistral":     {"base_url": "https://api.mistral.ai/v1",                              "default_model": "mistral-large-latest",      "label": "Mistral Le Chat"},
    "grok":        {"base_url": "https://api.x.ai/v1",                                   "default_model": "grok-3",                    "label": "Grok (xAI)"},
    "perplexity":  {"base_url": "https://api.perplexity.ai",                              "default_model": "sonar-pro",                 "label": "Perplexity"},
    "qwen":        {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",      "default_model": "qwen-plus",                 "label": "Qwen (Alibaba)"},
}


def _build_client(provider: str, api_key: str | None, model: str | None) -> LLMClient:
    settings = get_settings()
    entry = PROVIDER_REGISTRY.get(provider, {})
    resolved_model = model or entry.get("default_model", "")

    if provider == "ollama":
        return OllamaProvider()

    if provider == "anthropic":
        key = api_key or settings.anthropic_api_key
        return AnthropicProvider(api_key=key, model=resolved_model, timeout=settings.llm_timeout)

    if provider == "gemini":
        key = api_key or settings.gemini_api_key
        return GeminiProvider(api_key=key, model=resolved_model, timeout=settings.llm_timeout)

    # All remaining providers use the OpenAI-compatible wire format
    base_url = entry.get("base_url", "")
    if provider == "groq":
        key = api_key or settings.groq_api_key
    elif provider == "openai":
        key = api_key or settings.openai_api_key
    else:
        key = api_key or ""

    return OpenAICompatProvider(base_url=base_url, api_key=key, model=resolved_model, timeout=settings.llm_timeout)


def get_llm_client(org: Organization | None = None) -> LLMClient:
    if org and org.llm_provider_override:
        api_key = org.get_llm_api_key()
        return _build_client(org.llm_provider_override, api_key, org.llm_model_override)
    settings = get_settings()
    return _build_client(settings.llm_provider, api_key=None, model=None)
