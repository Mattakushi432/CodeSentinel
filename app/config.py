import logging
import secrets
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)
_WEAK_SECRET_KEYS = {"", "change-me-in-production"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/codesentinel.db"
    secret_key: str = "change-me-in-production"

    @model_validator(mode="after")
    def _ensure_secret_key(self) -> "Settings":
        if self.secret_key in _WEAK_SECRET_KEYS or len(self.secret_key) < 32:
            self.secret_key = secrets.token_hex(32)
            _logger.warning(
                "SECRET_KEY not set or too weak — generated a temporary key. "
                "Sessions will reset on restart. Set SECRET_KEY in your .env to persist sessions."
            )
        return self

    base_url: str = "http://localhost:8000"

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5-coder:7b-instruct"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    max_diff_lines: int = 500
    worker_poll_interval: int = 10
    llm_timeout: int = 300

    # Fernet key for encrypting access tokens at rest (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    encryption_key: str = ""

    # Set to true only in local development — enables /api/docs
    dev_mode: bool = False

    @model_validator(mode="after")
    def _ensure_encryption_key(self) -> "Settings":
        if not self.dev_mode and not self.encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY must be set in production. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        return self

    # Bearer token required to scrape /metrics. Leave empty to disable the endpoint.
    metrics_token: str = ""

    llm_retry_attempts: int = 3
    llm_retry_backoff: float = 2.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
